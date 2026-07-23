import os
import time
import psycopg2
from dotenv import load_dotenv

load_dotenv(dotenv_path="F:\\Code\\pc-forge-scraper-v1\\.env", override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection(retries=3, delay=2):
    """
    Connects to Railway Postgres with auto-retry and sslmode fallback.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("[ERROR] DATABASE_URL environment variable is missing.")

    for attempt in range(1, retries + 1):
        try:
            # Ensure sslmode=require for cloud Postgres connections if not present
            conn_str = db_url
            if "sslmode=" not in conn_str:
                conn_str += "?sslmode=require" if "?" not in conn_str else "&sslmode=require"
            
            conn = psycopg2.connect(conn_str)
            return conn
        except Exception as e:
            print(f"[WARNING] DB connection attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                raise

def init_db():
    """
    Idempotently creates all database ENUMs and tables in PostgreSQL.
    """
    print("\n[INFO] Initializing Railway PostgreSQL Schema...")
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # 1. Custom Category ENUM
        cur.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'product_category') THEN
                    CREATE TYPE product_category AS ENUM (
                        'cpu', 'gpu', 'motherboard', 'ram', 'psu', 'storage', 'case'
                    );
                END IF;
            END $$;
        """)

        # 2. Master Products Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id UUID PRIMARY KEY,
                manufacturer TEXT NOT NULL,
                product_name TEXT NOT NULL UNIQUE,
                category product_category NOT NULL,
                image_url TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 3. Persistent LLM Raw Mappings Cache Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_mappings (
                raw_name TEXT PRIMARY KEY,
                pcpp_name TEXT NOT NULL,
                specs JSONB NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 4. Live Vendor Prices Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vendor_prices (
                id BIGSERIAL PRIMARY KEY,
                vendor TEXT NOT NULL,
                product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
                price INTEGER NOT NULL,
                url TEXT NOT NULL,
                in_stock BOOLEAN DEFAULT TRUE,
                last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(vendor, product_id)
            );
            ALTER TABLE vendor_prices ADD COLUMN IF NOT EXISTS in_stock BOOLEAN DEFAULT TRUE;
        """)

        # 5. Price History Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id BIGSERIAL PRIMARY KEY,
                product_id UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
                vendor TEXT NOT NULL,
                price INTEGER NOT NULL,
                recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

        # 6. Category Specification Tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS case_specs (
                product_id UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
                case_form_factor TEXT,
                supported_motherboard_form_factors TEXT[],
                max_gpu_length_mm INTEGER,
                max_cpu_cooler_height_mm INTEGER,
                expansion_slots INTEGER,
                internal_3_5_bays INTEGER,
                internal_2_5_bays INTEGER,
                has_transparent_side_panel BOOLEAN,
                side_panel_type TEXT,
                supported_psu_form_factors TEXT[],
                width_mm INTEGER,
                height_mm INTEGER,
                depth_mm INTEGER
            );

            CREATE TABLE IF NOT EXISTS psu_specs (
                product_id UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
                wattage INTEGER,
                form_factor TEXT,
                efficiency_rating TEXT,
                modular BOOLEAN,
                length_mm INTEGER,
                fanless BOOLEAN,
                atx_24_pin INTEGER,
                eps_8_pin INTEGER,
                pcie_6_plus_2_pin INTEGER,
                pcie_12vhpwr INTEGER,
                sata_connectors INTEGER,
                molex_connectors INTEGER
            );

            CREATE TABLE IF NOT EXISTS storage_specs (
                product_id UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
                storage_type TEXT,
                capacity_gb INTEGER,
                form_factor TEXT,
                interface TEXT,
                nvme BOOLEAN
            );

            CREATE TABLE IF NOT EXISTS cpu_specs (
                product_id UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
                socket TEXT,
                cores INTEGER,
                threads INTEGER,
                base_clock_ghz FLOAT,
                boost_clock_ghz FLOAT,
                tdp_watts INTEGER,
                integrated_graphics TEXT,
                lithography TEXT
            );

            CREATE TABLE IF NOT EXISTS gpu_specs (
                product_id UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
                chipset_manufacturer TEXT,
                chipset TEXT,
                vram_gb INTEGER,
                memory_type TEXT,
                core_base_clock_mhz INTEGER,
                core_boost_clock_mhz INTEGER,
                memory_bus_bit INTEGER,
                interface TEXT,
                length_mm INTEGER,
                slot_width INTEGER,
                tdp_watts INTEGER,
                pcie_6_pin INTEGER,
                pcie_8_pin INTEGER,
                pcie_12vhpwr INTEGER,
                cooling TEXT,
                hdmi_2_1 INTEGER,
                displayport_2_1 INTEGER,
                displayport_2_1a INTEGER
            );

            CREATE TABLE IF NOT EXISTS motherboard_specs (
                product_id UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
                socket TEXT,
                chipset TEXT,
                form_factor TEXT,
                ram_type TEXT,
                ram_slots INTEGER,
                max_ram_gb INTEGER,
                pcie_x16_slots INTEGER,
                pcie_x1_slots INTEGER,
                m2_slots INTEGER,
                sata_6gb_ports INTEGER,
                onboard_ethernet_gbps FLOAT,
                ecc_support BOOLEAN,
                raid_support BOOLEAN
            );

            CREATE TABLE IF NOT EXISTS ram_specs (
                product_id UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
                ram_type TEXT,
                total_capacity_gb INTEGER,
                module_count INTEGER,
                module_capacity_gb INTEGER,
                speed_mhz INTEGER,
                cas_latency INTEGER,
                ecc BOOLEAN,
                registered BOOLEAN,
                form_factor TEXT,
                voltage FLOAT,
                rgb BOOLEAN,
                heat_spreader BOOLEAN
            );
        """)

        conn.commit()
        print("[SUCCESS] Railway PostgreSQL schema initialized successfully!")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to initialize schema: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    init_db()
