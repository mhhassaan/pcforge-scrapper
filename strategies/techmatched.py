import time
import os
import csv
import hashlib
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from common import clean_price, log_price_change, page_changed


def scrape(vendor_key, vendor_name, config, product_index, page_cache, vendor_folder):
    print(f"-> Scraping '{vendor_key}' (TechMatched WooCommerce scraper)")

    base_site_url = config.get("base_url", "").rstrip("/")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for filename, base_url in config["categories"].items():
        print(f"\n--- Category: {filename} ---")

        products = []
        new_count = 0
        updated_count = 0
        page = 1
        seen_products = set()
        seen_hashes = set()

        while True:
            page_url = f"{base_url}page/{page}/"
            print(f"   Fetching: {page_url}")

            try:
                res = requests.get(page_url, headers=headers, timeout=15, allow_redirects=True)
                res.raise_for_status()
            except Exception as e:
                print(f"   Error: {e}")
                break

            final_url = res.url.rstrip("/")
            requested_url = page_url.rstrip("/")
            category_url = base_url.rstrip("/")

            # ✅ Allow redirect for page 1 (WooCommerce behavior)
            if page > 1 and final_url == category_url:
                print("⛔ Reached last page of category (redirect detected).")
                break

            # ✅ Stop if redirected to homepage (real error)
            if base_site_url and final_url == base_site_url:
                print("🚫 Redirected to homepage. Stopping category.")
                break


            html = res.text

            # 🔁 Stop if page repeats
            html_hash = hashlib.md5(html.encode()).hexdigest()
            if html_hash in seen_hashes:
                print("   Duplicate page detected. Stop pagination.")
                break
            seen_hashes.add(html_hash)

            # ⏭️ Stop if unchanged since last run
            if not page_changed(page_url, html, page_cache):
                print("   Page unchanged. Stop pagination.")
                break

            soup = BeautifulSoup(html, "html.parser")

            # ✅ WooCommerce product cards
            cards = soup.select("ul.products > li.product")

            if not cards:
                print("   No products found. End category.")
                break

            for card in cards:
                title_tag = card.select_one(".woocommerce-loop-product__title")
                link_tag = card.select_one("a.woocommerce-LoopProduct-link")
                price_tag = card.select_one(".price .woocommerce-Price-amount")

                name = title_tag.get_text(strip=True) if title_tag else "N/A"
                product_url = urljoin(base_url, link_tag["href"]) if link_tag else ""

                # ✅ Deduplicate products
                if product_url in seen_products:
                    continue
                seen_products.add(product_url)

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
                    "last_seen": datetime.now().isoformat()
                }

                products.append([
                    len(products) + 1,
                    name,
                    vendor_name,
                    price,
                    product_url,
                    True
                ])

            page += 1
            time.sleep(1)

        if not products:
            print("⚠️ No new or updated products.")
            continue

        output_file = os.path.join(vendor_folder, filename)
        file_exists = os.path.exists(output_file)

        with open(output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["id", "component_name", "vendor", "price", "url", "in_stock"])
            writer.writerows(products)

        print(f"✅ New: {new_count}, Updated: {updated_count} → {filename}")
