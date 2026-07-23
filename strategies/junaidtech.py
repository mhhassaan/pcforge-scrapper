import time
import os
import csv
from datetime import datetime
from urllib.parse import urljoin
from scrapling import Selector

from common import clean_price, log_price_change, page_changed, get_scrapling_fetcher, extract_image_url

def scrape(vendor_key, vendor_name, config, product_index, page_cache, vendor_folder):
    print(f"-> Scraping '{vendor_key}' (JunaidTech Scrapling DynamicFetcher Playwright)")
    
    fetcher = get_scrapling_fetcher("dynamic")
    
    try:
        for filename, category_url in config["categories"].items():
            print(f"\n--- Category: {filename} ---")
            print(f"   Fetching via DynamicFetcher: {category_url}")
            
            try:
                response = fetcher.fetch(category_url)
            except Exception as e:
                print(f"   Error fetching {category_url}: {e}")
                continue
                
            html = response.text if hasattr(response, "text") else response.content.decode("utf-8", errors="replace")
            
            if not page_changed(category_url, html, page_cache):
                print("   Page unchanged since last run. Skipping category.")
                continue
                
            selector = Selector(html)
            cards = selector.css(config["selectors"]["card"])
            if not cards:
                print("   No product cards found.")
                continue
                
            products = []
            new_count = 0
            updated_count = 0
            seen_products = set()
            
            for card in cards:
                titles = card.css(config["selectors"]["title"])
                prices = card.css(config["selectors"]["price"])
                
                if not titles:
                    continue
                title_tag = titles[0]
                price_tag = prices[0] if prices else None
                
                name = title_tag.text.strip()
                href = title_tag.attrib.get("href")
                if not href or not name:
                    continue
                    
                product_url = urljoin(category_url, href)
                
                if product_url in seen_products:
                    continue
                seen_products.add(product_url)
                
                price = clean_price(price_tag.text.strip()) if price_tag else 0
                card_text = card.text.lower()
                in_stock = "out of stock" not in card_text
                image_url = extract_image_url(card, category_url)
                
                old = product_index[vendor_key].get(product_url)
                
                if not old:
                    new_count += 1
                elif old["price"] != price:
                    updated_count += 1
                    log_price_change(vendor_name, name, old["price"], price, product_url)
                else:
                    product_index[vendor_key][product_url]["last_seen"] = datetime.now().isoformat()
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
                    in_stock,
                    image_url or ""
                ])
                
            if not products:
                print("  [WARNING] No new or updated products.")
                continue
                
            output_file = os.path.join(vendor_folder, filename)
            file_exists = os.path.exists(output_file)
            
            with open(output_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["id", "component_name", "vendor", "price", "url", "in_stock", "image_url"])
                writer.writerows(products)
                
            print(f"  [OK] New: {new_count}, Updated: {updated_count} -> {filename}")
    finally:
        if hasattr(fetcher, "close"):
            try:
                fetcher.close()
            except Exception:
                pass
