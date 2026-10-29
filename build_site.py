import json
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.strtree import STRtree

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "templates" / "nearest_office_map.html"
OFFICES_PATH = ROOT / "data" / "municipal_offices.csv"
OUTLINE_PATH = ROOT / "data" / "ontario_outline.json"
BOUNDARIES_PATH = ROOT / "data" / "municipal_boundaries.json"
POPULATION_PATH = ROOT / "data" / "population_points.csv"
CHECKS_PATH = ROOT / "data" / "office_checks.csv"
OUTPUT_PATH = ROOT / "map.html"  # the explorer; index.html is the story page (build_story.py)
SITES_PATH = ROOT / "data" / "sites.json"  # offices with their stats, for the story page
STATS_PATH = ROOT / "data" / "stats.json"

# Each view is the set of tiers whose offices compete for "nearest".
VIEWS = {
    "local": ["Lower Tier", "Single Tier"],
    "upper": ["Upper Tier", "Single Tier"],
}
# Site fields that hold each view's population served and average distance (km).
VIEW_FIELDS = {"local": ("pl", "dl"), "upper": ("pr", "dr")}

ONTARIO_POPULATION_2021 = 14_223_942
NEAR_MUNICIPALITY_KM = 3  # an office this close to its municipality still gets its name
THRESHOLDS_KM = (10, 25, 50)

# Same Lambert conformal conic the page uses, so "nearest" matches what the map draws.
to_lcc = Transformer.from_crs(
    "EPSG:4326", "+proj=lcc +lat_1=44.5 +lat_2=54 +lat_0=49 +lon_0=-85 +datum=NAD83 +units=m", always_xy=True
)


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


def name_municipalities(sites, boundaries):
    """Set each site's municipality (`m`) from the boundary layer; return a list of problems.

    A point is inside a feature when an odd number of its rings contain it (the page
    draws the rings with the same even-odd rule, so holes work).
    """
    rings, owner = [], []
    for i, feature in enumerate(boundaries):
        for ring in feature["r"]:
            rings.append(shapely.make_valid(Polygon(ring)))
            owner.append(i)
    tree = STRtree(rings)

    problems = []
    offices_in = {}
    for site in sites:
        point = Point(site["lon"], site["lat"])
        hits = np.bincount([owner[j] for j in tree.query(point, predicate="intersects")], minlength=len(boundaries))
        inside = np.flatnonzero(hits % 2 == 1)
        site["m"], site["fl"] = "", ""
        if len(inside):
            feature = boundaries[inside[0]]
            site["m"] = feature["n"]
            if site["t"] != "Upper Tier":
                offices_in.setdefault((feature["n"], feature["t"]), []).append(site)
                if feature["t"] != site["t"]:
                    site["fl"] = "tier"
                    problems.append((site, f"listed as {site['t']} but sits in {feature['t']} {feature['n']}"))
            continue
        # Not inside any polygon: use the nearest one if it is close, and flag the office.
        j = tree.nearest(point)
        km = point.distance(rings[j]) * 85  # degrees to km, good enough at Ontario latitudes
        if km <= NEAR_MUNICIPALITY_KM:
            site["m"] = boundaries[owner[j]]["n"]
        site["fl"] = "outside"
        problems.append((site, f"{km:.1f} km outside the nearest municipality ({boundaries[owner[j]]['n']})"))

    # Islands are separate features with the same name, so count offices per name and tier.
    for name, tier in sorted({(f["n"], f["t"]) for f in boundaries}):
        count = len(offices_in.get((name, tier), []))
        if count != 1:
            problems.append((None, f"{name} ({tier}) has {count} offices inside it"))

    for site in sites:
        # Lower and single tier offices are named after their municipality; regional offices after their area.
        site["n"] = (site["m"] or site["c"]) if site["t"] != "Upper Tier" else f"{site['a']} – regional office"
    return problems


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    h = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(h))


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(cumulative, q * cumulative[-1])])


def add_population(sites, outline, population):
    """Assign each populated area to its nearest office and add people/distance figures.

    Only areas inside the map's outline count, so the numbers describe what the map shows.
    Returns the summary stats the page shows for each view.
    """
    land = shapely.make_valid(MultiPolygon([Polygon(rings[0], rings[1:]) for rings in outline]))
    shapely.prepare(land)
    population = population[shapely.contains_xy(land, population["longitude"], population["latitude"])]
    lat, lon, people = (population[c].to_numpy() for c in ("latitude", "longitude", "population"))
    px, py = to_lcc.transform(lon, lat)

    stats = {}
    for view, tiers in VIEWS.items():
        members = [s for s in sites if s["t"] in tiers]
        site_lat = np.array([s["lat"] for s in members])
        site_lon = np.array([s["lon"] for s in members])
        sx, sy = to_lcc.transform(site_lon, site_lat)
        nearest = np.argmin((px[:, None] - sx[None, :]) ** 2 + (py[:, None] - sy[None, :]) ** 2, axis=1)
        km = haversine_km(lat, lon, site_lat[nearest], site_lon[nearest])

        served = np.bincount(nearest, weights=people, minlength=len(members))
        distance_sum = np.bincount(nearest, weights=people * km, minlength=len(members))
        pop_field, dist_field = VIEW_FIELDS[view]
        for i, site in enumerate(members):
            site[pop_field] = int(served[i])
            site[dist_field] = round(distance_sum[i] / served[i], 1) if served[i] else 0

        regions = []
        serving_region = np.array([members[j]["a"] for j in nearest])
        for region in sorted(set(serving_region)):
            mask = serving_region == region
            if people[mask].sum():
                regions.append(
                    {
                        "r": region,
                        "pop": int(people[mask].sum()),
                        "mean": round(float(np.average(km[mask], weights=people[mask])), 1),
                        "max": round(float(km[mask & (people > 0)].max()), 1),
                    }
                )
        stats[view] = {
            "people": int(people.sum()),
            "coverage": round(100 * people.sum() / ONTARIO_POPULATION_2021, 1),
            "mean": round(float(np.average(km, weights=people)), 1),
            "median": round(weighted_quantile(km, people, 0.5), 1),
            "p90": round(weighted_quantile(km, people, 0.9), 1),
            "max": round(float(km[people > 0].max()), 1),
            "within": {str(t): round(100 * people[km <= t].sum() / people.sum(), 1) for t in THRESHOLDS_KM},
            "regions": sorted(regions, key=lambda r: -r["mean"]),
        }
    return stats


def as_js(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def write_checks(problems):
    rows = [
        {
            "office": site["c"] if site else "",
            "tier": site["t"] if site else "",
            "address": site["ad"] if site else "",
            "issue": issue,
        }
        for site, issue in problems
    ]
    pd.DataFrame(rows, columns=["office", "tier", "address", "issue"]).to_csv(CHECKS_PATH, index=False)


sites = office_sites(pd.read_csv(OFFICES_PATH))
boundaries = json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))
outline = json.loads(OUTLINE_PATH.read_text(encoding="utf-8"))

problems = name_municipalities(sites, boundaries)
write_checks(problems)
stats = add_population(sites, outline, pd.read_csv(POPULATION_PATH))

html = TEMPLATE_PATH.read_text(encoding="utf-8")
html = html.replace("__SITES__", as_js(sites))
html = html.replace("__STATS__", as_js(stats))
html = html.replace("__BOUNDS_DATA__", as_js(boundaries))
html = html.replace("__OUTLINE__", as_js(outline))

OUTPUT_PATH.write_text(html, encoding="utf-8")
SITES_PATH.write_text(as_js(sites), encoding="utf-8")
STATS_PATH.write_text(as_js(stats), encoding="utf-8")
print(f"Wrote {len(sites)} offices to {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1e6:.1f} MB)")
print(f"{len(problems)} possible data issues written to {CHECKS_PATH}")
for view, s in stats.items():
    print(f"{view}: {s['people']:,} people ({s['coverage']}%), mean {s['mean']} km, median {s['median']} km, p90 {s['p90']} km, max {s['max']} km")
