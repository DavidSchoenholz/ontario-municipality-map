import json
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import shapely
import xyzservices.providers as xyz
from pyproj import Transformer
from shapely.geometry import MultiPoint, MultiPolygon, Point, Polygon, box, mapping
from shapely.ops import voronoi_diagram
from shapely.strtree import STRtree

ROOT = Path(__file__).parent
CSV_PATH = ROOT / "data" / "municipal_offices.csv"
OUTLINE_PATH = ROOT / "data" / "ontario_outline.json"
OUTPUT_PATH = ROOT / "ontario_map.html"

# Same tier colours as the nearest-office example map.
TIER_COLORS = {
    "Upper Tier": "#d62728",
    "Lower Tier": "#1f77b4",
    "Single Tier": "#2ca02c",
}

# Each view is the set of tiers whose offices compete for "nearest".
VIEWS = {
    "Local offices (Lower + Single Tier)": ["Lower Tier", "Single Tier"],
    "Regional offices (Upper + Single Tier)": ["Upper Tier", "Single Tier"],
}

# Lambert conformal conic for Canada, so Voronoi distances are close to real ones.
to_lcc = Transformer.from_crs("EPSG:4326", "+proj=lcc +lat_1=44.5 +lat_2=54 +lat_0=49 +lon_0=-85 +datum=NAD83 +units=m", always_xy=True)
to_lonlat = Transformer.from_crs(to_lcc.target_crs, "EPSG:4326", always_xy=True)


def reproject(geom, transformer):
    return shapely.transform(geom, lambda xy: np.column_stack(transformer.transform(xy[:, 0], xy[:, 1])))


def load_land():
    """Ontario land outline as one shapely geometry (rings after the first are holes)."""
    polygons = [Polygon(rings[0], rings[1:]) for rings in json.loads(OUTLINE_PATH.read_text())]
    return shapely.make_valid(MultiPolygon(polygons))


def voronoi_cells(offices, land_lcc):
    """Return [(office rows sharing a point, cell clipped to land, in lon/lat)]."""
    # Offices at identical coordinates share one cell.
    by_point = {}
    for row in offices.itertuples():
        x, y = to_lcc.transform(row.longitude, row.latitude)
        by_point.setdefault((round(x, 1), round(y, 1)), []).append(row)

    points = [Point(xy) for xy in by_point]
    envelope = box(*land_lcc.buffer(100_000).bounds)
    raw_cells = voronoi_diagram(MultiPoint(points), envelope=envelope).geoms
    tree = STRtree(points)

    result = []
    for cell in raw_cells:
        idx = tree.query(cell, predicate="contains")
        if len(idx) != 1:
            continue
        clipped = cell.intersection(land_lcc)
        # Clipping can leave stray lines/points next to the polygons; keep polygons only.
        polygons = [g for g in shapely.get_parts(clipped) if isinstance(g, Polygon) and not g.is_empty]
        if not polygons:
            continue
        clipped = reproject(MultiPolygon(polygons), to_lonlat)
        result.append((by_point[list(by_point)[idx[0]]], clipped.simplify(0.003)))
    return result


def cell_feature(rows, geom):
    first = rows[0]
    label = f"{first.city} ({first.tier})"
    if len(rows) > 1:
        label += " + " + ", ".join(r.city for r in rows[1:])
    return {
        "type": "Feature",
        "geometry": mapping(geom),
        "properties": {"label": label, "tier": first.tier},
    }


df = pd.read_csv(CSV_PATH)

land = load_land()
land_lcc = reproject(land, to_lcc)

ontario_map = folium.Map(location=[46, -81], zoom_start=6, tiles=xyz.Esri.WorldStreetMap)

# Voronoi layers first so the office dots draw on top. Only one view shows at a time.
for i, (view_name, tiers) in enumerate(VIEWS.items()):
    cells = voronoi_cells(df[df["tier"].isin(tiers)], land_lcc)
    features = [cell_feature(rows, geom) for rows, geom in cells]
    group = folium.FeatureGroup(name=view_name, overlay=False, show=(i == 0))
    folium.GeoJson(
        {"type": "FeatureCollection", "features": features},
        style_function=lambda f: {
            "fillColor": TIER_COLORS[f["properties"]["tier"]],
            "fillOpacity": 0.3,
            "color": "#282828",
            "weight": 0.8,
        },
        highlight_function=lambda f: {"fillOpacity": 0.55, "weight": 2.5, "color": "#000"},
        tooltip=folium.GeoJsonTooltip(fields=["label"], aliases=["Nearest office:"], sticky=True),
    ).add_to(group)
    group.add_to(ontario_map)

# One feature group of office dots per tier so each tier can be toggled.
dots = {
    tier: folium.FeatureGroup(name=f"{tier} offices ({(df['tier'] == tier).sum()})").add_to(ontario_map)
    for tier in TIER_COLORS
}

for row in df.itertuples():
    popup = (
        f"<b>{row.city}</b><br>{row.tier} &middot; {row.region}<br>"
        f"{row.address}, {row.postal_code}"
    )
    if row.confidence < 0.9:
        popup += f"<br><small>Geocode confidence: {row.confidence} (location may be approximate)</small>"
    folium.CircleMarker(
        location=[row.latitude, row.longitude],
        radius=4,
        color="#111",
        weight=1,
        fill=True,
        fill_color=TIER_COLORS[row.tier],
        fill_opacity=1,
        popup=folium.Popup(popup, max_width=300),
    ).add_to(dots[row.tier])

folium.LayerControl(collapsed=False).add_to(ontario_map)

ontario_map.save(OUTPUT_PATH)
print(f"Saved {len(df)} offices to {OUTPUT_PATH}")
