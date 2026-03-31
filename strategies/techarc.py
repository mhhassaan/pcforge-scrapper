import time
import os
import csv
import re
import hashlib
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from common import clean_price, log_price_change, page_changed


def scrape(vendor_key, vendor_name, config, product_index, page_cache, vendor_folder):
    print(f"-> Inside '{vendor_key}' scraper. Using requests/BeautifulSoup.")

    base_site_url = config.get("base_url", "").rstrip("/")  # ✅ base site url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    for filename, url in config["categories"].items():
        print(f"\n--- Category: {filename} ---")

        products = []
        new_count = 0
        updated_count = 0
        page = 1
        seen_html_hashes = set()

        while True:
            page_url = f"{url}page/{page}/"
            print(f"   - Fetching {page_url}")

            try:
                response = requests.get(page_url, headers=headers, timeout=15, allow_redirects=True)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"   - Error fetching page: {e}")
                break

            # ✅ REDIRECT CHECK (skip category if redirected to homepage)
            final_url = response.url.rstrip("/")

            # ✅ If redirected to homepage → stop pagination (NOT category)
            if base_site_url and final_url == base_site_url:
                print("⛔ Redirected to base URL. No more pages in this category.")
                break


            html = response.text

            # 🔁 Duplicate page content check
            html_hash = hashlib.md5(html.encode()).hexdigest()
            if html_hash in seen_html_hashes:
                print("   - Duplicate page content detected. Ending category.")
                break
            seen_html_hashes.add(html_hash)

            # ⏭️ Page unchanged check
            if not page_changed(page_url, html, page_cache):
                print("⏭️ Page unchanged since last run, skipping remaining pages.")
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select(config["selectors"]["card"])

            if not cards:
                print("   - No more products found on page. Ending category.")
                break

            for card in cards:
                title_tag = card.select_one(config["selectors"]["title"])
                name = title_tag.get_text(strip=True) if title_tag else "N/A"

                link_tag = card.select_one(config["selectors"]["link"])
                product_url = link_tag["href"] if link_tag else ""

                price_tag = card.select_one(config["selectors"]["price"])
                price = clean_price(price_tag.get_text(strip=True)) if price_tag else 0.0

                old = product_index[vendor_key].get(product_url)

                if not old:
                    new_count += 1
                elif old["price"] != price:
                    updated_count += 1
                    log_price_change(vendor_name, name, old["price"], price, product_url)
                else:
                    continue

                product_index[vendor_key][product_url] = {
                    "name": name,
                    "price": price,
                    "last_seen": datetime.now().isoformat(),
                }

                products.append([
                    len(products) + 1,
                    name,
                    vendor_name,
                    price,
                    product_url,
                    True,
                ])

            page += 1
            time.sleep(1)

        if not products:
            print("⚠️ No new or updated products found in this category.")
            continue

        output_file = os.path.join(vendor_folder, filename)
        file_exists = os.path.exists(output_file)

        with open(output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["id", "component_name", "vendor", "price", "url", "in_stock"])
            writer.writerows(products)

        print(f"✅ New: {new_count}, Updated: {updated_count} → {filename}")
