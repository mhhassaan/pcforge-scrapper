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
MASTER_CSV = 'consolidated_cases_pcpp_style.csv'
VENDOR_DATA_PATH = 'scraped_data/**/case.csv'
CATEGORY = 'case'
SPEC_TABLE = 'case_specs'
FIELDS = [
    'case_form_factor', 'supported_motherboard_form_factors', 'max_gpu_length_mm',
    'max_cpu_cooler_height_mm', 'expansion_slots', 'internal_3_5_bays',
    'internal_2_5_bays', 'has_transparent_side_panel', 'side_panel_type',
    'supported_psu_form_factors', 'width_mm', 'height_mm', 'depth_mm'
]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def normalize_for_matching(name):
    if not name: return ""
    name = name.lower()
    # Explicit fixes
    name = name.replace("in pakistan | techmatched", "").replace("buy ", "")
    name = name.replace("pc case", "").replace("chassis", "").replace("gaming case", "").replace("gaming pc case", "")
    name = name.replace("mid tower", "").replace("full tower", "").replace("mini tower", "").replace("microatx", "matx")
    name = name.replace("tempered glass", "").replace("rgb", "").replace("argb", "").replace("mesh", "")
    name = name.replace("black", "").replace("white", "")
    name = name.replace("pre-installed", "").replace("fans", "").replace("fan", "")
    
    # Model specific fixes
    name = name.replace("gx 601s", "gx601").replace("gx 601", "gx601")
    
    # Remove all non-alphanumeric except spaces
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def token_match(canonical, vendor, manufacturer):
    c_tokens = set(canonical.lower().split())
    v_tokens = set(vendor.lower().split())
    
    if not c_tokens or not v_tokens: return False
    
    # Model Identification (e.g. H5, O11, 4000D, SN850X style)
    model_pattern = r'\b[a-z]*\d+[a-z]*\b'
    c_models = {t for t in c_tokens if re.match(model_pattern, t)}
    v_models = {t for t in v_tokens if re.match(model_pattern, t)}
    
    # Strong signal if model numbers match
    if c_models.intersection(v_models):
        m_lower = manufacturer.lower()
        v_norm = vendor.lower()
        if m_lower in v_tokens or m_lower in v_norm or m_lower == 'unknown' or m_lower == 'western':
            return True
        
        # Handle specific brand overlaps for cases (e.g. Thunder/Frozer/Boost)
        local_brands = {'thunder', 'frozer', 'boost', 'dragon', 'snowman', 'sonic', 'sama'}
        if m_lower in local_brands and any(b in v_norm for b in local_brands):
            return True

    # Standard match
    c_tokens_clean = {t for t in c_tokens if len(t) > 1}
    v_tokens_clean = {t for t in v_tokens if len(t) > 1}
    
    matches = c_tokens_clean.intersection(v_tokens_clean)
    score_c = len(matches) / len(c_tokens_clean) if c_tokens_clean else 0
    score_v = len(matches) / len(v_tokens_clean) if v_tokens_clean else 0
    
    m_lower = manufacturer.lower()
    has_manu = m_lower in v_tokens or m_lower in vendor or m_lower == 'unknown'
    if not has_manu: return False

    return score_v >= 0.75 or score_c >= 0.65

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
                continue

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
            columns = ", ".join(FIELDS)
            placeholders = ", ".join(["%s"] * len(FIELDS))
            
            values = []
            for f_name in FIELDS:
                val = row.get(f_name, '').strip()
                if not val or val.lower() == 'none' or val == '{}':
                    values.append(None)
                elif f_name in ['max_gpu_length_mm', 'max_cpu_cooler_height_mm', 'expansion_slots', 'internal_3_5_bays', 'internal_2_5_bays', 'width_mm', 'height_mm', 'depth_mm']:
                    values.append(to_int(val))
                elif f_name == 'has_transparent_side_panel':
                    values.append(to_bool(val))
                elif f_name in ['supported_motherboard_form_factors', 'supported_psu_form_factors']:
                    # CSV already has {item1,item2} style string
                    values.append(val)
                else:
                    values.append(val)
            
            sql = f"INSERT INTO {SPEC_TABLE} (product_id, {columns}) VALUES (%s, {placeholders}) ON CONFLICT (product_id) DO NOTHING"
            cur.execute(sql, [p_id] + values)

    conn.commit()
    print(f"  ✅ Master data synced. {len(model_to_info)} models ready.")

    print(f"\n🚀 Step 2: Linking Vendor Prices to Master {CATEGORY.upper()}...")
    
    vendor_files = glob.glob(VENDOR_DATA_PATH, recursive=True)
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
