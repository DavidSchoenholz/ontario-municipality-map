import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
OUTPUT_PATH = ROOT / "data" / "municipal_offices.csv"
SHEET = "Realised I needed tiers"

# Usage: python prepare_data.py "<Geocoded Cities of Ontario.xlsx>"
xlsx_path = Path(sys.argv[1])

raw = pd.read_excel(xlsx_path, sheet_name=SHEET)

# Keep the manually grabbed address fields plus the geocoded coordinates;
# everything else in the sheet is dropped.
df = pd.DataFrame(
    {
        "tier": raw["Municipal status"],
        "region": raw["Geographic area"],
        "address": raw["original_AI PULLED"],
        "city": raw["original_city"].fillna(raw["city"]),
        "postal_code": raw["original_postal code"],
        "latitude": raw["lat"],
        "longitude": raw["lon"],
        "confidence": raw["confidence"],
    }
)

df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
print(f"Wrote {len(df)} rows to {OUTPUT_PATH}")
print(df["tier"].value_counts().to_string())
print(df.isna().sum().to_string())
