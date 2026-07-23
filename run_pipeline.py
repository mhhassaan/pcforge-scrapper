import subprocess
import argparse
import sys

def run_command(cmd):
    print(f"\n[RUNNING] {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Command failed with error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="PC Forge Scrapling & ETL Pipeline local & cloud orchestrator.")
    parser.add_argument(
        "--stage",
        type=str,
        default="all",
        choices=["all", "init", "scrape", "fulfill", "sync"],
        help="Stage to run (default: all)"
    )
    parser.add_argument(
        "--category",
        type=str,
        default="all",
        help="Target category to run for fulfill and sync (default: all)"
    )
    parser.add_argument(
        "--vendor",
        type=str,
        default="all",
        help="Specific vendor to scrape (default: all)"
    )
    args = parser.parse_args()

    success = True

    # 0. Schema Init Stage
    if args.stage in ["all", "init"]:
        print("\n=== STAGE 0: INITIALIZE DATABASE SCHEMA ===")
        success = run_command([sys.executable, "init_db.py"])
        if not success:
            print("[WARNING] Database schema initialization failed. Aborting pipeline.")
            sys.exit(1)

    # 1. Scrape Stage
    if args.stage in ["all", "scrape"]:
        print("\n=== STAGE 1: SCRAPLING VENDOR EXTRACTION ===")
        success = run_command([sys.executable, "scraper_v2.py", "--vendor", args.vendor])
        if not success:
            print("[WARNING] Scraping stage failed. Aborting pipeline.")
            sys.exit(1)

    # 2. Consolidation & Fulfillment Stage
    if args.stage in ["all", "fulfill"]:
        print("\n=== STAGE 2: CONSOLIDATE & LLM SPEC FULFILLMENT ===")
        success = run_command([sys.executable, "consolidate_and_fulfill.py", "--category", args.category])
        if not success:
            print("[WARNING] Consolidation stage failed. Aborting pipeline.")
            sys.exit(1)

    # 3. Database Synchronization Stage
    if args.stage in ["all", "sync"]:
        print("\n=== STAGE 3: DATABASE BACKUP & SYNC (UPSERT) ===")
        success = run_command([sys.executable, "push_final.py", "--category", args.category])
        if not success:
            print("[WARNING] Database synchronization stage failed.")
            sys.exit(1)

    print("\n[SUCCESS] Pipeline execution completed successfully!")

if __name__ == "__main__":
    main()
