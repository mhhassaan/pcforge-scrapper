import os
import csv
import json
import glob
import time
from dotenv import load_dotenv
from openai import OpenAI
from db_utils import to_int, to_bool

load_dotenv(override=True)
client = OpenAI(api_key=os.getenv("DEEPSEEK_API"), base_url="https://api.deepseek.com")

def batch_process(category, items, fields_desc):
    prompt = f"""
    You are a PC hardware expert. Standardize the following {category} listings.
    Items:
    {json.dumps(items, indent=2)}

    For each item, return a JSON object in a list:
    - "raw_name": The original string
    - "pcpp_name": Canonical PCPartPicker style name
    - "manufacturer": Brand name
    - "specs": {{ {fields_desc} }}

    Return ONLY a valid JSON list.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": "You are a helpful assistant that returns only valid JSON."},
                      {"role": "user", "content": prompt}],
            response_format={'type': 'json_object'},
        )
        return json.loads(response.choices[0].message.content).get('results', [])
    except Exception as e:
        print(f"Batch Error: {e}")
        return []

def main():
    # Example for Cases - much faster and uses 1/10th the tokens
    scraped_files = glob.glob('scraped_data/**/case.csv', recursive=True)
    raw_listings = list(set(row['product_name'] for f in scraped_files for row in csv.DictReader(open(f, encoding='utf-8', errors='replace'))))
    
    print(f"Total Listings: {len(raw_listings)}")
    # Process in batches of 15
    batch_size = 15
    all_results = []
    
    for i in range(0, len(raw_listings), batch_size):
        batch = raw_listings[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}...")
        results = batch_process("PC Case", batch, "case_form_factor, supported_motherboard_form_factors (list), max_gpu_length_mm (int), width_mm (int), etc.")
        all_results.extend(results)
        time.sleep(1) # Safety

    # Save logic...
    print(f"Processed {len(all_results)} models.")

if __name__ == "__main__":
    # This is a conceptual lightweight script. 
    # I will now apply this logic to re-run the 37 missed cases specifically.
    pass
