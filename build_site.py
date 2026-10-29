import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "templates" / "nearest_office_map.html"
OFFICES_PATH = ROOT / "data" / "municipal_offices.csv"
OUTLINE_PATH = ROOT / "data" / "ontario_outline.json"
BOUNDARIES_PATH = ROOT / "data" / "municipal_boundaries.json"
OUTPUT_PATH = ROOT / "index.html"  # GitHub Pages serves index.html from the repo root


def office_sites(df):
    """Offices as the page's SITES list; same-tier offices at identical coordinates are merged.

    The Voronoi diagram needs unique points, so the first office at a location
    is kept and the others are listed in its `also` field. Offices in different
    tiers stay separate because each view only draws some of the tiers.
    """
    sites = {}
    for row in df.itertuples():
        key = (row.tier, round(row.latitude, 5), round(row.longitude, 5))
        if key in sites:
            sites[key]["also"].append(f"{row.city}, {row.address}")
            continue
        sites[key] = {
            "n": row.city,
            "t": row.tier,
            "a": row.region,
            "ad": row.address,
            "c": row.city,
            "pc": row.postal_code,
            "lat": round(row.latitude, 6),
            "lon": round(row.longitude, 6),
            "cf": row.confidence,
            "also": [],
        }
    return list(sites.values())


def as_js(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


sites = office_sites(pd.read_csv(OFFICES_PATH))

html = TEMPLATE_PATH.read_text(encoding="utf-8")
html = html.replace("__SITES__", as_js(sites))
html = html.replace("__BOUNDS_DATA__", BOUNDARIES_PATH.read_text(encoding="utf-8"))
html = html.replace("__OUTLINE__", OUTLINE_PATH.read_text(encoding="utf-8"))

OUTPUT_PATH.write_text(html, encoding="utf-8")
print(f"Wrote {len(sites)} offices to {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1e6:.1f} MB)")
