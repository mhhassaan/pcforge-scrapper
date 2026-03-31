import os
import csv
import psycopg2
import uuid
import glob
import re
from dotenv import load_dotenv
from psycopg2.extras import execute_batch, RealDictCursor
from db_utils import to_int, to_bool

# Load environment variables
load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL not found in .env")

# --- Configuration ---
MASTER_CSV = 'consolidated_storage_pcpp_style.csv'
VENDOR_DATA_PATTERNS = ['scraped_data/**/ssd.csv', 'scraped_data/**/hdd.csv', 'scraped_data/**/nvme.csv']
CATEGORY = 'ssd'
SPEC_TABLE = 'storage_specs'
FIELDS = ['storage_type', 'capacity_gb', 'form_factor', 'interface', 'nvme']

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def normalize_for_matching(name):
    if not name: return ""
    name = name.lower()
    # Manual spelling / merge fixes
    name = name.replace("nvme m.2", "m.2 nvme").replace("gen4x4", "gen4 x4").replace("gen3x4", "gen3 x4")
    name = name.replace("transcent", "transcend")
    name = name.replace("western digital", "wd").replace("western", "wd")
    
    # Explicit fixes/Normalizations
    name = name.replace("in pakistan | techmatched", "").replace("buy ", "")
    name = name.replace("solid state drive", "ssd").replace("internal hard drive", "hdd")
    name = name.replace("series", "").replace("edition", "")
    
    # Standardize capacity: '1tb' -> '1 tb'
    name = re.sub(r'(\d+)\s?tb\b', r'\1 tb', name)
    name = re.sub(r'(\d+)\s?gb\b', r'\1 gb', name)
    
    # Remove all non-alphanumeric except spaces
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def token_match(canonical, vendor, manufacturer):
    c_tokens = set(canonical.split())
    v_tokens = set(vendor.split())
    
    if not c_tokens or not v_tokens: return False
    
    # Model Number Extraction (e.g. 980, 990 Pro, SN850X)
    model_pattern = r'\b[a-z]*\d+[a-z]*\b'
    c_models = {t for t in c_tokens if re.match(model_pattern, t)}
    v_models = {t for t in v_tokens if re.match(model_pattern, t)}
    
    if c_models.intersection(v_models):
        m_lower = manufacturer.lower().replace("western digital", "wd").replace("western", "wd")
        v_norm = vendor.lower()
        if m_lower in v_tokens or m_lower in v_norm or m_lower == 'unknown' or (m_lower == 'wd' and 'wd' in v_norm):
            # Check capacity match to avoid matching 500GB model to 1TB listing
            cap_pattern = r'\b\d+\s?(?:gb|tb)\b'
            c_caps = set(re.findall(cap_pattern, canonical))
            v_caps = set(re.findall(cap_pattern, vendor))
            if c_caps and v_caps and not c_caps.intersection(v_caps):
                return False
            return True

    # Standard token match
    c_tokens_clean = {t for t in c_tokens if len(t) > 1}
    v_tokens_clean = {t for t in v_tokens if len(t) > 1}
    
    matches = c_tokens_clean.intersection(v_tokens_clean)
    score_c = len(matches) / len(c_tokens_clean) if c_tokens_clean else 0
    score_v = len(matches) / len(v_tokens_clean) if v_tokens_clean else 0
    
    m_lower = manufacturer.lower()
    has_manu = m_lower in v_tokens or m_lower in vendor or m_lower == 'unknown'
    if not has_manu: return False

    return score_v >= 0.8 or score_c >= 0.7

def main():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print(f"🚀 Step 1: Pushing Master {CATEGORY.upper()} and Specs...")
    model_to_info = {}
    
    if not os.path.exists(MASTER_CSV):
        print(f"❌ {MASTER_CSV} not found. Run consolidation script first.")
        return

    with open(MASTER_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p_name = row.get('product_name', '').strip()
            manu = row.get('manufacturer', '').strip()
            
            if not p_name or manu.isdigit():
                print(f"  ⚠️ Skipping invalid row: {p_name}")
                continue

            # Check if product exists
            cur.execute("SELECT product_id FROM products WHERE product_name = %s", (p_name,))
            existing = cur.fetchone()
            
            if existing:
                p_id = existing['product_id']
            else:
                p_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO products (product_id, manufacturer, product_name, category) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    (p_id, manu, p_name, CATEGORY)
                )
            
            model_to_info[p_name] = {'id': p_id, 'manufacturer': manu}
            
            # Specs
            capacity = row.get('capacity_gb', '').strip()
            s_type = row.get('storage_type', '').strip()
            if not capacity or not s_type or capacity.lower() == 'none':
                print(f"  ⚠️ Skipping specs for {p_name}: missing capacity or type")
                continue

            columns = ", ".join(FIELDS)
            placeholders = ", ".join(["%s"] * len(FIELDS))
            
            values = []
            for f_name in FIELDS:
                val = row.get(f_name, '').strip()
                if val == '' or val.lower() == 'none':
                    values.append(None)
                elif f_name == 'capacity_gb':
                    values.append(to_int(val))
                elif f_name == 'nvme':
                    values.append(to_bool(val))
                else:
                    values.append(val)
            
            sql = f"INSERT INTO {SPEC_TABLE} (product_id, {columns}) VALUES (%s, {placeholders}) ON CONFLICT (product_id) DO NOTHING"
            cur.execute(sql, [p_id] + values)

    conn.commit()
    print(f"  ✅ Master data synced. {len(model_to_info)} models ready.")

    print(f"\n🚀 Step 2: Linking Vendor Prices to Master {CATEGORY.upper()}...")
    
    vendor_files = []
    for p in VENDOR_DATA_PATTERNS:
        vendor_files.extend(glob.glob(p, recursive=True))

    price_entries = []
    skipped_names = []

    sorted_canonical = sorted(model_to_info.items(), key=lambda x: len(x[0]), reverse=True)

    for file_path in vendor_files:
        vendor_name = os.path.basename(os.path.dirname(file_path)).lower()
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_name = row['product_name']
                norm_vendor = normalize_for_matching(raw_name)
                
                matched_ids = []
                for canonical_name, info in sorted_canonical:
                    norm_canonical = normalize_for_matching(canonical_name)
                    
                    if norm_canonical in norm_vendor or token_match(norm_canonical, norm_vendor, info['manufacturer']):
                        matched_ids.append(info['id'])
                
                if matched_ids:
                    try:
                        price = int(float(row['price']))
                        if price > 0:
                            for mid in matched_ids:
                                price_entries.append((vendor_name, mid, price, row['url']))
                    except:
                        continue
                else:
                    if row['price'] and float(row['price']) > 0:
                        skipped_names.append(f"[{vendor_name}] {raw_name}")

    if price_entries:
        sql = """
            INSERT INTO vendor_prices (vendor, product_id, price, url, last_updated) 
            VALUES (%s, %s, %s, %s, NOW()) 
            ON CONFLICT (vendor, product_id) DO UPDATE SET 
                price = EXCLUDED.price, 
                url = EXCLUDED.url, 
                last_updated = NOW()
        """
        execute_batch(cur, sql, price_entries)
        conn.commit()
        print(f"  ✅ Successfully linked {len(price_entries)} prices across vendors.")
    
    if skipped_names:
        print(f"\n⚠️ Skipped {len(set(skipped_names))} unique listings that couldn't be matched:")
        for name in sorted(list(set(skipped_names))):
            print(f"  - {name}")

    cur.close()
    conn.close()
    print("\n✨ All Done!")

if __name__ == "__main__":
    main()
