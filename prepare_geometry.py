import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import shapely
from shapely.geometry import Polygon

ROOT = Path(__file__).parent
OUTLINE_PATH = ROOT / "data" / "ontario_outline.json"
BOUNDARIES_PATH = ROOT / "data" / "municipal_boundaries.json"

# Statistics Canada Lambert conformal conic; metres, so tolerances below are in metres.
METRIC_CRS = "EPSG:3347"

OUTLINE_SIMPLIFY_M = 100
OUTLINE_MIN_PART_KM2 = 0.05
SLIVER_CLOSE_M = 10
PRE_SIMPLIFY_M = 25
BOUNDARY_SIMPLIFY_M = 150
BOUNDARY_MIN_PART_KM2 = 0.05

SMALL_WORDS = {"of", "the", "and"}

# Usage: python prepare_geometry.py "<Municipal_Boundary_-_Lower_and_Single_Tier.shp>"
municipal_path = Path(sys.argv[1])


def polygon_parts(geom, min_area_m2):
    """Polygons of a geometry larger than min_area_m2 (drops lines/points left by cleaning)."""
    return [p for p in shapely.get_parts(geom) if isinstance(p, Polygon) and p.area >= min_area_m2]


def rings_lonlat(polygons):
    """[(exterior, *holes)] per polygon as lon/lat lists, rounded to ~10 m."""
    to_lonlat = gpd.GeoSeries(polygons, crs=METRIC_CRS).to_crs("EPSG:4326")
    return [
        [[[round(x, 4), round(y, 4)] for x, y in ring.coords] for ring in (p.exterior, *p.interiors)]
        for p in to_lonlat
    ]


def title_case(name):
    """'TOWN OF NIAGARA-ON-THE-LAKE' -> 'Town of Niagara-On-The-Lake' (capital after - and /, and after O' / D')."""
    words = name.lower().split()
    words = [w if i and w in SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words)]
    return re.sub(r"(?<=[-/])[a-z]|(?<=\b[A-Za-z]')[a-z]", lambda m: m.group().upper(), " ".join(words))


# Municipal boundaries (lower and single tier), for the "Original municipal boundaries" view.
# The shapefile truncates column names to 10 characters.
municipal = gpd.read_file(municipal_path).to_crs(METRIC_CRS)

# The map is clipped to the municipalities themselves: dissolve the whole layer into one
# outline. The tiny buffer in and out closes hairline slivers between neighbours.
# Simplify each municipality first: buffering the full-resolution layer takes far too long.
light = [shapely.make_valid(g).simplify(PRE_SIMPLIFY_M) for g in municipal.geometry.values]
land = shapely.union_all(light)
land = shapely.make_valid(land.buffer(SLIVER_CLOSE_M).buffer(-SLIVER_CLOSE_M).simplify(OUTLINE_SIMPLIFY_M))
outline = rings_lonlat(polygon_parts(land, OUTLINE_MIN_PART_KM2 * 1e6))
OUTLINE_PATH.write_text(json.dumps(outline, separators=(",", ":")), encoding="utf-8")
print(f"Wrote {len(outline)} outline polygons to {OUTLINE_PATH} ({OUTLINE_PATH.stat().st_size / 1e6:.1f} MB)")

boundaries = []
for row in municipal.itertuples():
    geom = shapely.make_valid(row.geometry).simplify(BOUNDARY_SIMPLIFY_M)
    parts = polygon_parts(geom, BOUNDARY_MIN_PART_KM2 * 1e6)
    if not parts:
        continue
    upper = row.UPPER_TI_1 if isinstance(row.UPPER_TI_1, str) else ""
    boundaries.append(
        {
            "n": title_case(row.MUNICIPA_2),
            "t": "Lower Tier" if row.MUNICIPAL_.startswith("Lower") else "Single Tier",
            "u": title_case(upper),
            "r": [ring for poly in rings_lonlat(parts) for ring in poly],
        }
    )
BOUNDARIES_PATH.write_text(json.dumps(boundaries, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
print(f"Wrote {len(boundaries)} boundaries to {BOUNDARIES_PATH} ({BOUNDARIES_PATH.stat().st_size / 1e6:.1f} MB)")
