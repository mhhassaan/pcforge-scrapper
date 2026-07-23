import os
import json
import argparse
import strategies.junaidtech
import strategies.techarc
import strategies.techmatched
import strategies.walistech
import strategies.zahcomputers

CONFIG_FILE = "scraper_config.json"
CACHE_DIR = ".cache"
PAGE_CACHE_FILE = os.path.join(CACHE_DIR, "page_cache.json")
PRODUCT_INDEX_FILE = os.path.join(CACHE_DIR, "product_index.json")
OUTPUT_DIR = "scraped_data"

def main():
    parser = argparse.ArgumentParser(description="PC Forge Scrapling Vendor Scraper Driver.")
    parser.add_argument(
        "--vendor",
        type=str,
        default="all",
        choices=["all", "junaidtech", "techarc", "techmatched", "walistech", "zahcomputers"],
        help="Specific vendor to scrape (default: all)"
    )
    args = parser.parse_args()

    if not os.path.exists(CONFIG_FILE):
        print(f"[ERROR] Config file '{CONFIG_FILE}' not found.")
        return
        
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config_data = json.load(f)
        
    if args.vendor != "all":
        if args.vendor in config_data:
            config_data = {args.vendor: config_data[args.vendor]}
        else:
            print(f"[ERROR] Vendor '{args.vendor}' not found in configuration.")
            return

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    if os.path.exists(PAGE_CACHE_FILE):
        try:
            with open(PAGE_CACHE_FILE, "r", encoding="utf-8") as f:
                page_cache = json.load(f)
        except Exception:
            page_cache = {}
    else:
        page_cache = {}
        
    if os.path.exists(PRODUCT_INDEX_FILE):
        try:
            with open(PRODUCT_INDEX_FILE, "r", encoding="utf-8") as f:
                product_index = json.load(f)
        except Exception:
            product_index = {}
    else:
        product_index = {}

    for vendor_key, vendor_config in config_data.items():
        print(f"\n==========================================")
        print(f"[START] Scrapling Vendor: {vendor_key.upper()}")
        print(f"==========================================")
        
        vendor_folder = os.path.join(OUTPUT_DIR, vendor_key)
        os.makedirs(vendor_folder, exist_ok=True)
        
        if vendor_key not in product_index:
            product_index[vendor_key] = {}
            
        vendor_name = vendor_key
        
        try:
            if vendor_key == "junaidtech":
                strategies.junaidtech.scrape(
                    vendor_key, vendor_name, vendor_config,
                    product_index, page_cache, vendor_folder
                )
            elif vendor_key == "techarc":
                strategies.techarc.scrape(
                    vendor_key, vendor_name, vendor_config,
                    product_index, page_cache, vendor_folder
                )
            elif vendor_key == "techmatched":
                strategies.techmatched.scrape(
                    vendor_key, vendor_name, vendor_config,
                    product_index, page_cache, vendor_folder
                )
            elif vendor_key == "walistech":
                strategies.walistech.scrape(
                    vendor_key, vendor_name, vendor_config,
                    product_index, page_cache, vendor_folder
                )
            elif vendor_key == "zahcomputers":
                strategies.zahcomputers.scrape(
                    vendor_key, vendor_name, vendor_config,
                    product_index, page_cache, vendor_folder
                )
        except Exception as e:
            print(f"[ERROR] Strategy execution failed for {vendor_key}: {e}")

    print("\n[INFO] Saving Scrapling caches...")
    try:
        with open(PAGE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(page_cache, f, indent=2)
            
        with open(PRODUCT_INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(product_index, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save caches: {e}")
        
    print("[SUCCESS] Scraping complete!")

if __name__ == "__main__":
    main()
