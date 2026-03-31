# PC Forge Scraper & Data Pipeline

A high-performance ETL (Extract, Transform, Load) pipeline designed to aggregate PC hardware data from major Pakistani online retailers. This project scrapes product listings, standardizes names using LLMs, fulfills technical specifications, and synchronizes the data with a cloud-hosted PostgreSQL database.

## Key Features

- **Multi-Vendor Scraping:** Supports concurrent scraping of JS-heavy and static sites using `Crawl4AI` and `BeautifulSoup4`.
- **LLM-Powered Normalization:** Automatically standardizes messy vendor listings (e.g., "Intel Core i5 12th Gen 12400F") into canonical PCPartPicker-style names using DeepSeek/GPT.
- **Automated Spec Fulfillment:** Fetches deep technical details (TDP, VRM phases, clock speeds, dimensions) directly from product strings via LLM agents.
- **Relational Cloud Integration:** Synchronizes data with **Neon (Serverless PostgreSQL)** using robust "Smart Push" logic and native UUIDs.
- **Greedy Matching:** Intelligently maps vague vendor prices to specific master models to ensure maximum price coverage.

---

## Architecture

The pipeline follows a 4-stage process:

1.  **Scraping:** Raw product names, prices, and URLs are extracted into vendor-specific CSVs.
2.  **Consolidation:** Raw data is merged into a master listing with unique product identifiers.
3.  **Technical Fulfillment:** LLM agents analyze listings to generate canonical names and technical specs.
4.  **Database Synchronization:** Data is pushed to the production database using UPSERT logic to maintain price history and inventory.

---

## 🛠️ Tech Stack

- **Core:** Python 3.10+
- **Scraping:** Crawl4AI, BeautifulSoup4, Requests
- **Data Science:** Pandas, Pydantic (Validation), FuzzyWuzzy
- **AI/LLM:** DeepSeek (via OpenAI SDK)
- **Database:** Neon PostgreSQL, Psycopg2
- **Environment:** Dotenv for secret management

---

## Setup

### Prerequisites
- Python 3.x installed.
- A Neon PostgreSQL database instance.
- DeepSeek (or OpenAI) API key for spec fulfillment.

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/pc-forge-scraper-v1.git
   cd pc-forge-scraper-v1
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables in a `.env` file:
   ```env
   DATABASE_URL=postgres://user:password@endpoint/dbname
   DEEPSEEK_API=your_api_key_here
   ```

---

## Usage

Follow these steps in order to perform a full pipeline update:

### 1. Scrape & Consolidate
Run the high-performance scraper and merge the raw results.
```bash
python scraper_v2.py
python consolidate_data.py
```

### 2. Standardize & Fulfill Specs (Category-Specific)
Run the fulfillment scripts for the categories you wish to update. This uses LLMs to clean data and fetch specs.
```bash
python consolidate_and_fulfill_cpus.py
python consolidate_and_fulfill_gpus.py
python consolidate_and_fulfill_motherboards.py
# ... and so on
```

### 3. Synchronize to Cloud Database
Push the normalized models and their respective vendor prices to the database.
```bash
python push_final_cases.py
python push_final_psu.py
# ... etc
```

---

## Directory Structure

- `scraped_data/`: Contains raw CSV outputs organized by vendor.
- `strategies/`: Vendor-specific scraping logic.
- `db_utils.py`: Shared utilities for price cleaning and type casting.
---

## Development Conventions

- **Clean Types:** Use `db_utils.to_int()`, `to_bool()`, and `clean_price()` to maintain data integrity.
- **Schema Safety:** All `product_id` fields must use native UUIDs.
- **LLM JSON Mode:** Fulfillment scripts are configured to use JSON response formats for reliable parsing.
- **Error Handling:** Pipeline scripts log warnings and skip malformed rows to ensure continuous execution.

---

## Project Status

| Category | Master Models | Linked Prices | Price Coverage |
| :--- | :--- | :--- | :--- |
| **CPU** | 66 | 137 | ~99% |
| **GPU** | 179 | 1,103 | ~98% |
| **RAM** | 75 | 460 | ~99% |
| **MB** | 233 | 919 | ~99% |

*Data as of February 25, 2026.*
