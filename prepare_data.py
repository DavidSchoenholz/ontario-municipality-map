import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
OUTPUT_PATH = ROOT / "data" / "municipal_offices.csv"
SHEET = "Realised I needed tiers"

OUTLINE_PATH = ROOT / "data" / "ontario_outline.json"
BOUNDARIES_PATH = ROOT / "data" / "municipal_boundaries.json"

# Usage: python prepare_data.py "<xlsx>" ["<ontario_nearest_office_map.html>"]
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

# Optional: lift the Ontario land outline and the municipal boundaries (lon/lat
# polygons) out of the example map.
if len(sys.argv) > 2:
    html = Path(sys.argv[2]).read_text(encoding="utf-8")
    for const, next_const, path in [
        ("OUTLINE", "COL", OUTLINE_PATH),
        ("BOUNDS_DATA", "OUTLINE", BOUNDARIES_PATH),
    ]:
        match = re.search(rf"const {const}=(\[.*?\]);[^\n]*\nconst {next_const}=", html, flags=re.S)
        data = json.loads(match.group(1))
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        print(f"Wrote {len(data)} {const} entries to {path}")
