import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    
    # Try to find enum values
    try:
        cur.execute("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'product_category';")
        rows = cur.fetchall()
        print("Enum values for 'product_category':")
        for r in rows:
            print(f"  - {r[0]}")
    except Exception as e:
        print(f"Could not find enum 'product_category': {e}")
    
    # Also check existing categories in products table
    cur.execute("SELECT DISTINCT category FROM products;")
    rows = cur.fetchall()
    print("\nExisting categories in 'products' table:")
    for r in rows:
        print(f"  - {r[0]}")
        
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
