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
MASTER_CSV = 'consolidated_psu_pcpp_style.csv'
VENDOR_DATA_PATH = 'scraped_data/**/psu.csv'
CATEGORY = 'psu'
SPEC_TABLE = 'psu_specs'
FIELDS = [
    'wattage', 'form_factor', 'efficiency_rating', 'modular', 'length_mm',
    'fanless', 'atx_24_pin', 'eps_8_pin', 'pcie_6_plus_2_pin', 'pcie_12vhpwr',
    'sata_connectors', 'molex_connectors'
]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def normalize_for_matching(name):
    if not name: return ""
    name = name.lower()
    # Manual spelling / merge fixes
    name = name.replace("corereactor", "core reactor")
    name = name.replace("hx1000i", "hx1000 i").replace("hx1500i", "hx1500 i")
    name = name.replace("rm1000e", "rm1000 e").replace("rm850e", "rm850 e").replace("rm750e", "rm750 e")
    name = name.replace("rm1000x", "rm1000 x").replace("rm850x", "rm850 x")
    
    # Explicit fixes/Normalizations
    name = name.replace("in pakistan | techmatched", "").replace("buy ", "")
    name = name.replace("power supply", "").replace("psu", "").replace("unit", "")
    name = name.replace("series", "").replace("edition", "").replace("fully modular", "").replace("modular", "")
    name = name.replace("compatible with", "").replace("certification", "").replace("certified", "")
    name = name.replace("80 plus", "80+").replace("80plus", "80+")
    
    # Standardize wattage: '750w' -> '750 w'
    name = re.sub(r'(\d+)\s?w\b', r'\1 w', name)
    
    # Remove excessive fluff
    name = name.replace("low-noise", "").replace("dual eps12v connectors", "").replace("105°c-rated capacitors", "")
    name = name.replace("modern standby support", "").replace("ultra-stable", "").replace("smart fan", "")
    name = name.replace("premium heat dissipation", "").replace("active pfc", "")
    name = name.replace("(uk)", "").replace("black", "").replace("white", "")
    
    # Remove all non-alphanumeric except spaces
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

def token_match(canonical, vendor, manufacturer):
    c_tokens = set(canonical.split())
    v_tokens = set(vendor.split())
    
    if not c_tokens or not v_tokens: return False
    
    # Model Number Extraction (e.g. RM1000x, CX650, PK750D)
    # Look for alphanumeric tokens that contain digits and letters
    model_pattern = r'\b[a-z]+\d+[a-z]*\b'
    c_models = {t for t in c_tokens if re.match(model_pattern, t)}
    v_models = {t for t in v_tokens if re.match(model_pattern, t)}
    
    # If they share a specific model number, it's a very strong signal
    if c_models.intersection(v_models):
        # Still need manufacturer or very high token match to avoid wrong brand same model
        m_lower = manufacturer.lower()
        if m_lower in v_tokens or m_lower in vendor or m_lower == 'unknown':
            return True

    # Standard token match logic
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
            wattage = row.get('wattage', '').strip()
            if not wattage or wattage.lower() == 'none':
                print(f"  ⚠️ Skipping specs for {p_name}: missing wattage")
                continue

            columns = ", ".join(FIELDS)
            placeholders = ", ".join(["%s"] * len(FIELDS))
            
            values = []
            for f_name in FIELDS:
                val = row.get(f_name, '').strip()
                if val == '' or val.lower() == 'none':
                    values.append(None)
                elif f_name in ['wattage', 'length_mm', 'atx_24_pin', 'eps_8_pin', 'pcie_6_plus_2_pin', 'pcie_12vhpwr', 'sata_connectors', 'molex_connectors']:
                    values.append(to_int(val))
                elif f_name in ['modular', 'fanless']:
                    values.append(to_bool(val))
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
