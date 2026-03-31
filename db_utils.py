import re

def to_int(val):
    if val is None: return None
    if isinstance(val, int): return val
    try:
        # Extract digits from string (e.g., "1,200" -> 1200)
        s = re.sub(r'[^\d]', '', str(val))
        return int(s) if s else None
    except:
        return None

def to_bool(val):
    if val is None: return False
    if isinstance(val, bool): return val
    s = str(val).lower().strip()
    return s in ['true', '1', 'yes', 'y', 't', 'modular', 'rgb']

def clean_price(price_str):
    if not price_str: return 0
    try:
        # "Rs. 120,000" -> 120000
        s = re.sub(r'[^\d]', '', str(price_str))
        return int(s) if s else 0
    except:
        return 0
