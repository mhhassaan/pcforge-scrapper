import os
import csv
import json
import glob
import time
import argparse
from dotenv import load_dotenv
from openai import OpenAI

from db_utils import to_int, to_bool
from config_categories import CATEGORIES
from init_db import get_db_connection

load_dotenv(dotenv_path="F:\\Code\\pc-forge-scraper-v1\\.env", override=True)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API")
client = None

if DEEPSEEK_API_KEY:
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

LOCAL_RAW_MAP_FILE = ".cache/raw_to_canonical.json"

def load_raw_map():
    """
    Loads raw-to-canonical mappings from PostgreSQL raw_mappings table if available,
    falling back to local JSON cache file.
    """
    raw_map = {}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT raw_name, pcpp_name, specs FROM raw_mappings;")
        rows = cur.fetchall()
        for r_name, p_name, specs in rows:
            raw_map[r_name] = {"pcpp_name": p_name, "specs": specs}
        cur.close()
        conn.close()
        print(f"  ✓ Loaded {len(raw_map)} LLM raw mappings from PostgreSQL 'raw_mappings' table.")
        return raw_map
    except Exception as e:
        print(f"  [INFO] DB raw_mappings read unavailable ({e}). Falling back to local cache.")

    os.makedirs(".cache", exist_ok=True)
    if os.path.exists(LOCAL_RAW_MAP_FILE):
        try:
            with open(LOCAL_RAW_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_raw_mapping_entry(raw_name, pcpp_name, specs, raw_map):
    """
    Persists a single raw-to-canonical entry into PostgreSQL and local JSON cache.
    """
    raw_map[raw_name] = {"pcpp_name": pcpp_name, "specs": specs}
    
    # 1. Save to Postgres
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO raw_mappings (raw_name, pcpp_name, specs)
            VALUES (%s, %s, %s)
            ON CONFLICT (raw_name) DO UPDATE SET 
                pcpp_name = EXCLUDED.pcpp_name, 
                specs = EXCLUDED.specs,
                updated_at = NOW();
        """, (raw_name, pcpp_name, json.dumps(specs)))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"  [WARNING] Could not save mapping to DB ({e}).")

    # 2. Save to local JSON backup
    try:
        os.makedirs(".cache", exist_ok=True)
        with open(LOCAL_RAW_MAP_FILE, "w", encoding="utf-8") as f:
            json.dump(raw_map, f, indent=2)
    except Exception:
        pass

def get_canonical_info_llm(product_name, category_key, cfg):
    """
    Standardizes names and fulfills specs using DeepSeek LLM.
    """
    if not client:
        print("[ERROR] DeepSeek client is not initialized. Check DEEPSEEK_API in .env")
        return None, None

    fields_desc = cfg["guidelines"]
    fields_list = cfg["fields"]
    category_desc = cfg["description"]

    prompt = f"""
    You are a PC hardware database expert. Standardize the following {category_desc} listing to match PCPartPicker naming conventions.
    
    Listing: "{product_name}"

    Return a JSON object with:
    1. "pcpp_name": The canonical name (e.g., "Corsair RM750e (2023) 750 W 80+ Gold Certified Fully Modular ATX Power Supply" or "Intel Core i5-12400F 2.5 GHz 6-Core Processor"). 
       Remove vendor fluff, Pakistan-specific text (like "in Pakistan", "price in PK", warranty info), and price information.
    2. "specs": A JSON object containing these keys: {', '.join(fields_list)}

    Guidelines for specs:
    {fields_desc}

    Respond ONLY with the JSON object. Do not include markdown code block syntax.
    """
    
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that returns only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={'type': 'json_object'},
            stream=False
        )
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()
            
        data = json.loads(content)
        
        pcpp_name = data.get('pcpp_name', 'Unknown').strip()
        specs = data.get('specs', {})
        
        cleaned_specs = {}
        for f in fields_list:
            val = specs.get(f)
            f_type = cfg["types"].get(f, "str")
            
            if f_type == "bool":
                cleaned_specs[f] = to_bool(val)
            elif f_type == "int":
                cleaned_specs[f] = to_int(val)
            elif f_type == "float":
                try:
                    cleaned_specs[f] = float(val) if val is not None else None
                except Exception:
                    cleaned_specs[f] = None
            elif f_type == "list":
                if isinstance(val, list):
                    cleaned_specs[f] = val
                elif isinstance(val, str):
                    cleaned_specs[f] = [s.strip() for s in val.split(',')]
                else:
                    cleaned_specs[f] = []
            else:
                cleaned_specs[f] = str(val).strip() if val is not None else None
        
        return pcpp_name, cleaned_specs
    except Exception as e:
        print(f"  ❌ LLM Error for '{product_name}': {e}")
        return None, None

def process_category(category_key):
    if category_key not in CATEGORIES:
        print(f"[ERROR] Category '{category_key}' is not defined.")
        return

    cfg = CATEGORIES[category_key]
    print(f"\n==========================================")
    print(f"[START] Consolidating Category: {category_key.upper()}")
    print(f"==========================================")

    # 1. Glob all raw files and map candidate images
    raw_listings = set()
    raw_images = {}
    
    for pattern in cfg["csv_patterns"]:
        files = glob.glob(pattern, recursive=True)
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    reader = csv.DictReader(f)
                    name_field = 'product_name' if 'product_name' in reader.fieldnames else 'component_name'
                    for row in reader:
                        name = row.get(name_field, '').strip()
                        img = row.get('image_url', '').strip()
                        if name:
                            raw_listings.add(name)
                            if img and name not in raw_images:
                                raw_images[name] = img
            except Exception as e:
                print(f"  [WARNING] Error reading {file_path}: {e}")

    print(f"Found {len(raw_listings)} unique raw listings.")
    
    # 2. Load map cache from DB / local
    raw_map = load_raw_map()
    
    # 3. Consolidate specifications
    final_data = {}
    count = 0
    new_llm_calls = 0
    
    for raw_name in sorted(list(raw_listings)):
        count += 1
        img_url = raw_images.get(raw_name)
        
        if raw_name in raw_map:
            pcpp_name = raw_map[raw_name]["pcpp_name"]
            specs = raw_map[raw_name]["specs"]
            if pcpp_name and pcpp_name != "Unknown":
                manufacturer = pcpp_name.split()[0]
                if pcpp_name not in final_data:
                    final_data[pcpp_name] = {
                        'manufacturer': manufacturer,
                        'product_name': pcpp_name,
                        'specs': specs,
                        'image_url': img_url
                    }
                elif not final_data[pcpp_name].get('image_url') and img_url:
                    final_data[pcpp_name]['image_url'] = img_url
        else:
            print(f"[{count}/{len(raw_listings)}] LLM Querying: {raw_name[:50]}...")
            pcpp_name, specs = get_canonical_info_llm(raw_name, category_key, cfg)
            new_llm_calls += 1
            
            if pcpp_name and pcpp_name != "Unknown":
                save_raw_mapping_entry(raw_name, pcpp_name, specs, raw_map)
                
                manufacturer = pcpp_name.split()[0]
                if pcpp_name not in final_data:
                    final_data[pcpp_name] = {
                        'manufacturer': manufacturer,
                        'product_name': pcpp_name,
                        'specs': specs,
                        'image_url': img_url
                    }
                print(f"    [NEW MODEL] {pcpp_name}")
            else:
                print(f"    [WARNING] Failed standardizing: {raw_name[:50]}")
                
            time.sleep(0.3)

    print(f"Fulfillment complete. Made {new_llm_calls} new LLM calls. Total unique models: {len(final_data)}")

    # 4. Save to master CSV
    if final_data:
        output_file = cfg["master_csv"]
        fieldnames = ['manufacturer', 'product_name', 'image_url'] + cfg["fields"]
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for name, data in final_data.items():
                    row = {
                        'manufacturer': data['manufacturer'],
                        'product_name': data['product_name'],
                        'image_url': data.get('image_url', '')
                    }
                    for field in cfg["fields"]:
                        val = data['specs'].get(field)
                        if cfg["types"].get(field) == "list" and isinstance(val, list):
                            row[field] = "{" + ",".join([f'"{s}"' for s in val]) + "}"
                        else:
                            row[field] = val
                    writer.writerow(row)
            print(f"[SUCCESS] Saved consolidated models to {output_file}")
        except Exception as e:
            print(f"[ERROR] Failed writing to {output_file}: {e}")
    else:
        print("[ERROR] No data processed.")

def main():
    parser = argparse.ArgumentParser(description="Consolidate and fulfill PC component specifications.")
    parser.add_argument(
        "--category", 
        type=str, 
        default="all", 
        choices=["all"] + list(CATEGORIES.keys()),
        help="Category to process (default: all)"
    )
    args = parser.parse_args()

    if args.category == "all":
        for cat in CATEGORIES.keys():
            process_category(cat)
    else:
        process_category(args.category)

if __name__ == "__main__":
    main()
