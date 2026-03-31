import time
import os
import csv
from datetime import datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from common import clean_price, log_price_change, page_changed

def scrape(driver, vendor_key, vendor_name, config, product_index, page_cache, vendor_folder):
    for filename, url in config["categories"].items():
        print(f"\n--- Category: {filename} ---")

        products = []
        new_count = 0
        updated_count = 0

        driver.get(url)

        while True:
            try:
                btn = WebDriverWait(driver, 3).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, config["selectors"]["load_more"]))
                )
                btn.click()
                time.sleep(2)
            except:
                break

        html = driver.page_source

        if not page_changed(url, html, page_cache):
            print("⏭️ Category unchanged, skipping")
            continue

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(config["selectors"]["card"])

        for card in cards:
            title_tag = card.select_one(config["selectors"]["title"])
            name = title_tag.get_text(strip=True) if title_tag else "N/A"

            link_tag = card.select_one(config["selectors"]["link"])
            product_url = config["base_url"] + link_tag["href"] if link_tag else ""

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

        # ================= SAVE CSV =================

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
