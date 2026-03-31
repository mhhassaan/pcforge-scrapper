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
    'wattage', 'form_factor', 'efficiency_rating', 'modular', 'length_mm',
    'fanless', 'atx_24_pin', 'eps_8_pin', 'pcie_6_plus_2_pin', 'pcie_12vhpwr',
    'sata_connectors', 'molex_connectors'
]

def get_canonical_info(product_name):
    """
    Standardizes PSU names and fulfills specs.
    """
    prompt = f"""
    You are a PC hardware database expert. Standardize the following PSU (Power Supply Unit) listing to match PCPartPicker naming.
    
    Listing: "{product_name}"

    Return a JSON object with:
    1. "pcpp_name": The canonical name (e.g., "Corsair RM750e (2023) 750 W 80+ Gold Certified Fully Modular ATX Power Supply"). 
       Remove vendor fluff, Pakistan-specific text, and price info.
    2. "specs": A JSON object containing these keys: {', '.join(FIELDS)}

    Guidelines for specs:
    - wattage: integer (e.g., 550, 650, 750, 850, 1000)
    - form_factor: 'ATX', 'SFX', 'SFX-L', 'TFX'
    - efficiency_rating: '80+ White', '80+ Bronze', '80+ Silver', '80+ Gold', '80+ Platinum', '80+ Titanium'
    - modular: boolean (True if Fully or Semi Modular, False if Non-Modular)
    - length_mm: integer (e.g., 140, 150, 160)
    - fanless: boolean
    - atx_24_pin: integer (usually 1)
    - eps_8_pin: integer (e.g., 1, 2)
    - pcie_6_plus_2_pin: integer (e.g., 2, 4, 6)
    - pcie_12vhpwr: integer (e.g., 0, 1)
    - sata_connectors: integer (e.g., 6, 8, 12)
    - molex_connectors: integer (e.g., 2, 4)

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
            if f in ['modular', 'fanless']:
                cleaned_specs[f] = to_bool(val)
            elif f in ['wattage', 'length_mm', 'atx_24_pin', 'eps_8_pin', 'pcie_6_plus_2_pin', 'pcie_12vhpwr', 'sata_connectors', 'molex_connectors']:
                cleaned_specs[f] = to_int(val)
            else:
                cleaned_specs[f] = val
        
        return pcpp_name, cleaned_specs
    except Exception as e:
        print(f"  ❌ LLM Error for {product_name}: {e}")
        return None, None

def main():
    scraped_files = glob.glob('scraped_data/**/psu.csv', recursive=True)
    raw_listings = set()
    for file_path in scraped_files:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row['product_name'].strip()
                if name: raw_listings.add(name)

    print(f"Found {len(raw_listings)} unique PSU listings. Normalizing and fulfilling specs...")

    final_data = {} 
    count = 0
    for raw_name in sorted(list(raw_listings)):
        count += 1
        print(f"[{count}/{len(raw_listings)}] Processing: {raw_name[:60]}...")
        
        pcpp_name, specs = get_canonical_info(raw_name)
        
        if pcpp_name:
            if pcpp_name not in final_data:
                # Basic manufacturer guess
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
        output_file = 'consolidated_psu_pcpp_style.csv'
        fieldnames = ['manufacturer', 'product_name'] + FIELDS
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for name, data in final_data.items():
                row = {'manufacturer': data['manufacturer'], 'product_name': data['product_name']}
                row.update(data['specs'])
                writer.writerow(row)
        
        print(f"\n✅ Success! {len(final_data)} unique models saved to {output_file}")
    else:
        print("\n❌ No data processed.")

if __name__ == "__main__":
    main()
