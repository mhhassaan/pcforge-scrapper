import re
import random
import hashlib
import time
from datetime import datetime
from urllib.parse import urljoin

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
]

def get_scrapling_fetcher(fetcher_type="stealth"):
    """
    Factory creating configured Scrapling fetcher instances.
    """
    from scrapling import Fetcher, DynamicFetcher
    
    if fetcher_type == "dynamic":
        return DynamicFetcher(
            headless=True,
            args=[
                "--headless=new",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu"
            ]
        )
    else:
        return Fetcher(
            headers={"User-Agent": random.choice(USER_AGENTS)}
        )

def extract_image_url(card_selector, base_url=""):
    """
    Inspects src, data-src, data-lazy-src, and srcset for valid HTTP image links.
    Returns None if missing, base64, or placeholder.
    """
    try:
        imgs = card_selector.css("img")
        if not imgs:
            return None
        img_tag = imgs[0]
            
        candidates = [
            img_tag.attrib.get("data-src"),
            img_tag.attrib.get("data-lazy-src"),
            img_tag.attrib.get("src"),
            img_tag.attrib.get("srcset")
        ]
        
        for cand in candidates:
            if not cand:
                continue
            # Extract first URL if srcset contains multiple resolution descriptors
            cand = cand.split(",")[0].split()[0].strip()
            
            # Skip base64 placeholders & blank trackers
            if cand.startswith("data:image/") or "placeholder" in cand.lower() or "blank.gif" in cand.lower():
                continue
                
            full_url = urljoin(base_url, cand) if base_url else cand
            if full_url.startswith("http://") or full_url.startswith("https://"):
                return full_url
    except Exception:
        pass
    return None

def clean_price(price_str):
    """
    Normalizes price strings like 'Rs. 140,000.00' to an integer (140000).
    """
    if not price_str:
        return 0
    cleaned = re.sub(r'[^\d]', '', str(price_str))
    return int(cleaned) if cleaned else 0

def log_price_change(vendor, product_name, old_price, new_price, url):
    """
    Appends price shift events to price_changes_v2.log.
    """
    log_file = "price_changes_v2.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{vendor}] {product_name} | Old: Rs.{old_price:,} -> New: Rs.{new_price:,} | {url}\n"
    print(f"  [PRICE CHANGE] {vendor} - {product_name}: {old_price} -> {new_price}")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"  [ERROR] Failed to write to log: {e}")

def page_changed(url, html, page_cache):
    """
    MD5 hash comparison to skip unmodified category pages.
    """
    current_hash = hashlib.md5(html.encode("utf-8", errors="replace")).hexdigest()
    if page_cache.get(url) == current_hash:
        return False
    page_cache[url] = current_hash
    return True
