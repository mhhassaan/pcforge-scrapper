import os
import csv
import json
import glob
import time
import re
from dotenv import load_dotenv
from openai import OpenAI
from db_utils import to_int, to_bool

# Load environment variables
load_dotenv(override=True)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("❌ DEEPSEEK_API not found in .env")

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")

# --- Configuration ---
FIELDS = [
    'case_form_factor', 'supported_motherboard_form_factors', 'max_gpu_length_mm',
    'max_cpu_cooler_height_mm', 'expansion_slots', 'internal_3_5_bays',
    'internal_2_5_bays', 'has_transparent_side_panel', 'side_panel_type',
    'supported_psu_form_factors', 'width_mm', 'height_mm', 'depth_mm'
]

def get_canonical_info(product_name):
    """
    Standardizes Case names and fulfills specs.
    """
    prompt = f"""
    You are a PC hardware database expert. Standardize the following PC Case listing to match PCPartPicker naming.
    
    Listing: "{product_name}"

    Return a JSON object with:
    1. "pcpp_name": The canonical name (e.g., "NZXT H5 Flow (2023) ATX Mid Tower Case"). 
       Remove vendor fluff, Pakistan-specific text, and price info.
    2. "specs": A JSON object containing these keys: {', '.join(FIELDS)}

    Guidelines for specs:
    - case_form_factor: 'ATX Mid Tower', 'ATX Full Tower', 'MicroATX Mini Tower', 'Mini ITX Tower', etc.
    - supported_motherboard_form_factors: list of strings (e.g., ["ATX", "Micro ATX", "Mini ITX"])
    - max_gpu_length_mm: integer
    - max_cpu_cooler_height_mm: integer
    - expansion_slots: integer
    - internal_3_5_bays: integer
    - internal_2_5_bays: integer
    - has_transparent_side_panel: boolean
    - side_panel_type: 'Tempered Glass', 'Acrylic', 'None'
    - supported_psu_form_factors: list of strings (e.g., ["ATX"])
    - width_mm: integer
    - height_mm: integer
    - depth_mm: integer

    Respond ONLY with the JSON object.
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
        data = json.loads(response.choices[0].message.content.strip())
        
        pcpp_name = data.get('pcpp_name', 'Unknown')
        specs = data.get('specs', {})
        
        # Clean fields
        cleaned_specs = {}
        for f in FIELDS:
            val = specs.get(f)
            if f == 'has_transparent_side_panel':
                cleaned_specs[f] = to_bool(val)
            elif f in ['max_gpu_length_mm', 'max_cpu_cooler_height_mm', 'expansion_slots', 'internal_3_5_bays', 'internal_2_5_bays', 'width_mm', 'height_mm', 'depth_mm']:
                cleaned_specs[f] = to_int(val)
            elif f in ['supported_motherboard_form_factors', 'supported_psu_form_factors']:
                if isinstance(val, list):
                    cleaned_specs[f] = val
                elif isinstance(val, str):
                    cleaned_specs[f] = [s.strip() for s in val.split(',')]
                else:
                    cleaned_specs[f] = []
            else:
                cleaned_specs[f] = val
        
        return pcpp_name, cleaned_specs
    except Exception as e:
        print(f"  ❌ LLM Error for {product_name}: {e}")
        return None, None

def main():
    scraped_files = glob.glob('scraped_data/**/case.csv', recursive=True)
    raw_listings = set()
    for file_path in scraped_files:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row['product_name'].strip()
                if name: raw_listings.add(name)

    print(f"Found {len(raw_listings)} unique Case listings. Normalizing and fulfilling specs...")

    final_data = {} 
    count = 0
    for raw_name in sorted(list(raw_listings)):
        count += 1
        print(f"[{count}/{len(raw_listings)}] Processing: {raw_name[:60]}...")
        
        pcpp_name, specs = get_canonical_info(raw_name)
        
        if pcpp_name:
            if pcpp_name not in final_data:
                manufacturer = pcpp_name.split()[0]
                final_data[pcpp_name] = {
                    'manufacturer': manufacturer,
                    'product_name': pcpp_name,
                    'specs': specs
                }
                print(f"    ✨ New Model: {pcpp_name}")
            else:
                print(f"    🔗 Map to: {pcpp_name}")
        
        time.sleep(0.4)

    if final_data:
        output_file = 'consolidated_cases_pcpp_style.csv'
        # Adjust for list fields by converting to string representation for CSV
        fieldnames = ['manufacturer', 'product_name'] + FIELDS
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for name, data in final_data.items():
                row = {'manufacturer': data['manufacturer'], 'product_name': data['product_name']}
                for f in FIELDS:
                    val = data['specs'].get(f)
                    if isinstance(val, list):
                        row[f] = "{" + ",".join([f'"{s}"' for s in val]) + "}" # Postgres array style
                    else:
                        row[f] = val
                writer.writerow(row)
        
        print(f"\n✅ Success! {len(final_data)} unique models saved to {output_file}")
    else:
        print("\n❌ No data processed.")

if __name__ == "__main__":
    main()
