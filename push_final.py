import os
import csv
import re
import uuid
import glob
from datetime import datetime
import argparse
import psycopg2
from psycopg2.extras import execute_batch, RealDictCursor

from db_utils import to_int, to_bool
from config_categories import CATEGORIES
from init_db import get_db_connection

BACKUP_DIR = ".backups"

def backup_tables(conn, category_key, spec_table):
    """
    Backs up database tables into local CSV files before editing them.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    current_backup_dir = os.path.join(BACKUP_DIR, f"db_{timestamp}")
    os.makedirs(current_backup_dir, exist_ok=True)
    
    tables_to_backup = ["products", "vendor_prices", "price_history", spec_table]
    print(f"\n[BACKUP] Backing up tables to: {current_backup_dir}")
    
    cur = conn.cursor()
    for table in tables_to_backup:
        try:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = %s
                );
            """, (table,))
            exists = cur.fetchone()[0]
            if not exists:
                continue
                
            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
            headers = [row[0] for row in cur.fetchall()]
            
            backup_file = os.path.join(current_backup_dir, f"{table}.csv")
            with open(backup_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            print(f"  [OK] Backed up '{table}' ({len(rows)} rows)")
        except Exception as e:
            print(f"  [ERROR] Error backing up table '{table}': {e}")
    cur.close()

def normalize_for_matching(name, category):
    if not name:
        return ""
    name = name.lower()
    
    if category == "psu":
        name = name.replace("corereactor", "core reactor")
        name = name.replace("hx1000i", "hx1000 i").replace("hx1500i", "hx1500 i")
        name = name.replace("rm1000e", "rm1000 e").replace("rm850e", "rm850 e").replace("rm750e", "rm750 e")
        name = name.replace("rm1000x", "rm1000 x").replace("rm850x", "rm850 x")
        name = re.sub(r'(\d+)\s?w\b', r'\1 w', name)
        name = name.replace("power supply", "").replace("psu", "").replace("unit", "")
        name = name.replace("series", "").replace("edition", "").replace("fully modular", "").replace("modular", "")
        name = name.replace("80 plus", "80+").replace("80plus", "80+")
    elif category == "storage":
        name = name.replace("nvme m.2", "m.2 nvme").replace("gen4x4", "gen4 x4").replace("gen3x4", "gen3 x4")
        name = name.replace("transcent", "transcend")
        name = name.replace("western digital", "wd").replace("western", "wd")
        name = name.replace("solid state drive", "ssd").replace("internal hard drive", "hdd")
    elif category == "case":
        name = name.replace("gx 601s", "gx601").replace("gx 601", "gx601")
        name = name.replace("pc case", "").replace("chassis", "").replace("gaming case", "").replace("gaming pc case", "")
        name = name.replace("mid tower", "").replace("full tower", "").replace("mini tower", "").replace("microatx", "matx")
        name = name.replace("tempered glass", "").replace("mesh", "")
        name = name.replace("pre-installed", "").replace("fans", "").replace("fan", "")

    name = name.replace("in pakistan | techmatched", "").replace("buy ", "")
    name = name.replace("rgb", "").replace("argb", "")
    name = name.replace("black", "").replace("white", "")
    
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def token_match(canonical, vendor, manufacturer, category):
    c_tokens = set(canonical.split())
    v_tokens = set(vendor.split())
    
    if not c_tokens or not v_tokens:
        return False
        
    model_pattern = r'\b[a-z]*\d+[a-z]*\b'
    c_models = {t for t in c_tokens if re.match(model_pattern, t)}
    v_models = {t for t in v_tokens if re.match(model_pattern, t)}
    
    if c_models.intersection(v_models):
        m_lower = manufacturer.lower()
        if m_lower in v_tokens or m_lower in vendor or m_lower == 'unknown' or m_lower == 'western':
            return True
        if category == "case":
            local_brands = {'thunder', 'frozer', 'boost', 'dragon', 'snowman', 'sonic', 'sama'}
            if m_lower in local_brands and any(b in vendor for b in local_brands):
                return True

    c_tokens_clean = {t for t in c_tokens if len(t) > 1 or t == 'w'}
    c_tokens_clean = {t for t in c_tokens_clean if not (re.match(r'^\(?20[12]\d\)?$', t))}
    
    v_tokens_clean = {t for t in v_tokens if len(t) > 1 or t == 'w'}
    v_tokens_clean = {t for t in v_tokens_clean if not (re.match(r'^\(?20[12]\d\)?$', t))}
    
    matches = c_tokens_clean.intersection(v_tokens_clean)
    score_c = len(matches) / len(c_tokens_clean) if c_tokens_clean else 0
    score_v = len(matches) / len(v_tokens_clean) if v_tokens_clean else 0
    
    m_lower = manufacturer.lower()
    has_manu = m_lower in v_tokens or m_lower in vendor or m_lower == 'unknown'
    if not has_manu and m_lower == 'silverstone' and 'silvertone' in vendor:
        has_manu = True
        
    if not has_manu:
        return False

    return score_v >= 0.75 or score_c >= 0.65

def sync_category(category_key):
    if category_key not in CATEGORIES:
        print(f"[ERROR] Category '{category_key}' is not defined.")
        return
        
    cfg = CATEGORIES[category_key]
    spec_table = cfg["spec_table"]
    master_csv = cfg["master_csv"]
    
    if not os.path.exists(master_csv):
        print(f"[ERROR] Master CSV '{master_csv}' not found. Run consolidation script first.")
        return
        
    print(f"\n==========================================")
    print(f"[START] Database Sync: {category_key.upper()}")
    print(f"==========================================")
    
    conn = get_db_connection()
    backup_tables(conn, category_key, spec_table)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Step 1: Master Models, Specs & Single-Source Images
    print("\n[STEP 1] Pushing Master Models, Specs & Single-Source Images...")
    model_to_info = {}
    
    with open(master_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_name = row.get('product_name', '').strip()
            manu = row.get('manufacturer', '').strip()
            img_url = row.get('image_url', '').strip() or None
            
            if not p_name or manu.isdigit():
                continue
                
            cur.execute("SELECT product_id FROM products WHERE product_name = %s", (p_name,))
            existing = cur.fetchone()
            
            if existing:
                p_id = existing['product_id']
                # Update image_url only if currently NULL (First-Write-Wins)
                if img_url:
                    cur.execute(
                        "UPDATE products SET image_url = %s WHERE product_id = %s AND image_url IS NULL",
                        (img_url, p_id)
                    )
            else:
                p_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO products (product_id, manufacturer, product_name, category, image_url)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (product_name) DO UPDATE 
                    SET image_url = EXCLUDED.image_url 
                    WHERE products.image_url IS NULL
                    """,
                    (p_id, manu, p_name, category_key, img_url)
                )
                
            model_to_info[p_name] = {'id': p_id, 'manufacturer': manu}
            
            # Specs Sync
            columns = ", ".join(cfg["fields"])
            placeholders = ", ".join(["%s"] * len(cfg["fields"]))
            
            values = []
            for f_name in cfg["fields"]:
                val = row.get(f_name, '').strip()
                f_type = cfg["types"].get(f_name, "str")
                
                if val == '' or val.lower() == 'none' or val == '{}':
                    parsed_val = None
                elif f_type == "int":
                    parsed_val = to_int(val)
                elif f_type == "float":
                    try:
                        parsed_val = float(val)
                    except Exception:
                        parsed_val = None
                elif f_type == "bool":
                    parsed_val = to_bool(val)
                elif f_type == "list":
                    parsed_val = val
                else:
                    parsed_val = val
                    
                # Fallback for wattage constraint if missing
                if f_name == "wattage" and parsed_val is None:
                    w_match = re.search(r'(\d+)\s?w\b', p_name.lower())
                    if w_match:
                        parsed_val = int(w_match.group(1))
                    else:
                        parsed_val = 0
                        
                values.append(parsed_val)
                    
            sql = f"INSERT INTO {spec_table} (product_id, {columns}) VALUES (%s, {placeholders}) ON CONFLICT (product_id) DO NOTHING"
            cur.execute(sql, [p_id] + values)
            
    conn.commit()
    print(f"  [OK] Master models and specs synced ({len(model_to_info)} models ready).")
    
    # Step 2: Vendor Price Spokes & Stock Status
    print(f"\n[STEP 2] Linking Vendor Prices & Stock status to master {category_key.upper()}...")
    
    price_entries = []
    skipped_names = []
    
    sorted_canonical = sorted(model_to_info.items(), key=lambda x: len(x[0]), reverse=True)
    scraped_files = []
    for pattern in cfg["csv_patterns"]:
        scraped_files.extend(glob.glob(pattern, recursive=True))
        
    for file_path in scraped_files:
        vendor_name = os.path.basename(os.path.dirname(file_path)).lower()
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                name_field = 'product_name' if 'product_name' in reader.fieldnames else 'component_name'
                for row in reader:
                    raw_name = row.get(name_field, '').strip()
                    if not raw_name:
                        continue
                        
                    norm_vendor = normalize_for_matching(raw_name, category_key)
                    in_stock = to_bool(row.get('in_stock', 'true'))
                    
                    matched_ids = []
                    for canonical_name, info in sorted_canonical:
                        norm_canonical = normalize_for_matching(canonical_name, category_key)
                        
                        if norm_canonical in norm_vendor or token_match(norm_canonical, norm_vendor, info['manufacturer'], category_key):
                            matched_ids.append(info['id'])
                            
                    if matched_ids:
                        try:
                            price = clean_price(row.get('price', 0))
                            url_val = row.get('url', '')
                            if price > 0 and url_val:
                                for mid in matched_ids:
                                    price_entries.append((vendor_name, mid, price, url_val, in_stock))
                        except Exception:
                            continue
                    else:
                        if row.get('price') and float(row['price']) > 0:
                            skipped_names.append(f"[{vendor_name}] {raw_name}")
        except Exception as e:
            print(f"  [WARNING] Error reading vendor file {file_path}: {e}")
            
    if price_entries:
        sql = """
            INSERT INTO vendor_prices (vendor, product_id, price, url, in_stock, last_updated) 
            VALUES (%s, %s, %s, %s, %s, NOW()) 
            ON CONFLICT (vendor, product_id) DO UPDATE SET 
                price = EXCLUDED.price, 
                url = EXCLUDED.url, 
                in_stock = EXCLUDED.in_stock,
                last_updated = NOW()
        """
        execute_batch(cur, sql, price_entries)
        
        history_entries = [(entry[1], entry[0], entry[2]) for entry in price_entries]
        history_sql = """
            INSERT INTO price_history (product_id, vendor, price, recorded_at)
            VALUES (%s, %s, %s, NOW())
        """
        execute_batch(cur, history_sql, history_entries)
        
        conn.commit()
        print(f"  [OK] Linked {len(price_entries)} prices and logged history across vendors.")
        
    if skipped_names:
        print(f"\n[WARNING] Skipped {len(set(skipped_names))} unique listings that couldn't be matched:")
        for name in sorted(list(set(skipped_names)))[:15]:
            print(f"  - {name}")
            
    cur.close()
    conn.close()
    print("[SUCCESS] Sync complete!")

def main():
    parser = argparse.ArgumentParser(description="Push canonical products and price spokes to PostgreSQL.")
    parser.add_argument(
        "--category", 
        type=str, 
        default="all", 
        choices=["all"] + list(CATEGORIES.keys()),
        help="Category to push (default: all)"
    )
    args = parser.parse_args()

    if args.category == "all":
        for cat in CATEGORIES.keys():
            sync_category(cat)
    else:
        sync_category(args.category)

if __name__ == "__main__":
    main()
