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
FIELDS = ['storage_type', 'capacity_gb', 'form_factor', 'interface', 'nvme']

def get_canonical_info(product_name):
    """
    Standardizes Storage names and fulfills specs.
    """
    prompt = f"""
    You are a PC hardware database expert. Standardize the following Storage (SSD/HDD/NVMe) listing to match PCPartPicker naming.
    
    Listing: "{product_name}"

    Return a JSON object with:
    1. "pcpp_name": The canonical name (e.g., "Samsung 980 Pro 1 TB M.2-2280 PCIe 4.0 X4 NVME Solid State Drive" or "Seagate Barracuda Compute 2 TB 3.5" 7200 RPM Internal Hard Drive"). 
       Remove vendor fluff, Pakistan-specific text, and price info.
    2. "specs": A JSON object containing these keys: {', '.join(FIELDS)}

    Guidelines for specs:
    - storage_type: 'SSD' or 'HDD'
    - capacity_gb: integer (e.g., 250, 500, 1000, 2000, 4000). Note: 1TB = 1000, 2TB = 2000.
    - form_factor: 'M.2-2280', '2.5"', '3.5"', 'mSATA'
    - interface: 'PCIe 4.0 x4', 'PCIe 3.0 x4', 'SATA 6.0 Gb/s', 'PCIe 5.0 x4'
    - nvme: boolean (True if it's an NVMe drive, False for SATA SSDs and HDDs)

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
            if f == 'nvme':
                cleaned_specs[f] = to_bool(val)
            elif f == 'capacity_gb':
                cleaned_specs[f] = to_int(val)
            else:
                cleaned_specs[f] = val
        
        return pcpp_name, cleaned_specs
    except Exception as e:
        print(f"  ❌ LLM Error for {product_name}: {e}")
        return None, None

def main():
    # Target multiple storage-related CSVs
    patterns = ['scraped_data/**/ssd.csv', 'scraped_data/**/hdd.csv', 'scraped_data/**/nvme.csv']
    scraped_files = []
    for p in patterns:
        scraped_files.extend(glob.glob(p, recursive=True))
        
    raw_listings = set()
    for file_path in scraped_files:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row['product_name'].strip()
                if name: raw_listings.add(name)

    print(f"Found {len(raw_listings)} unique Storage listings. Normalizing and fulfilling specs...")

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
        output_file = 'consolidated_storage_pcpp_style.csv'
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
