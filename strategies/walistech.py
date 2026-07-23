import os
import csv
from datetime import datetime
from urllib.parse import urljoin
from scrapling import Selector

from common import clean_price, log_price_change, page_changed, get_scrapling_fetcher, extract_image_url

def scrape(vendor_key, vendor_name, config, product_index, page_cache, vendor_folder):
    print(f"-> Scraping '{vendor_key}' (Wali's Tech Scrapling StealthyFetcher)")
    
    fetcher = get_scrapling_fetcher(config.get("fetcher_type", "stealth"))
    
    for filename, base_category_url in config["categories"].items():
        print(f"\n--- Category: {filename} ---")
        
        products = []
        new_count = 0
        updated_count = 0
        page = 1
        seen_products = set()
        
        while True:
            page_url = f"{base_category_url}?sort=0&page={page}"
            print(f"   Fetching: {page_url}")
            
            try:
                response = fetcher.get(page_url)
            except Exception as e:
                print(f"   Error fetching page {page}: {e}. Ending category.")
                break
                
            html = getattr(response, "html_content", None) or getattr(response, "text", "")
            
            if not page_changed(page_url, html, page_cache):
                print("   Page unchanged or duplicate. Stopping pagination.")
                break
                
            cards = response.css(config["selectors"]["card"]) if hasattr(response, "css") else Selector(html).css(config["selectors"]["card"])
            if not cards:
                print("   No product cards found on page. Ending category.")
                break
                
            page_has_valid_items = False
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
                    
                product_url = urljoin(base_category_url, href)
                
                if product_url in seen_products:
                    continue
                seen_products.add(product_url)
                page_has_valid_items = True
                
                price_text = price_tag.text.strip() if price_tag else "0"
                price = clean_price(price_text)
                
                card_text = card.text.lower()
                in_stock = "out of stock" not in card_text
                
                image_url = extract_image_url(card, base_category_url)
                
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
                
            if not page_has_valid_items:
                print("   No new valid items on page. Ending category.")
                break
                
            page += 1
            
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
