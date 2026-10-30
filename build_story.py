import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "templates" / "story.html"
SITES_PATH = ROOT / "data" / "sites.json"
STATS_PATH = ROOT / "data" / "stats.json"
OFFICES_PATH = ROOT / "data" / "municipal_offices.csv"
CHECKS_PATH = ROOT / "data" / "office_checks.csv"
OUTPUT_PATH = ROOT / "index.html"  # the site's landing page; the explorer is map.html

sites = json.loads(SITES_PATH.read_text(encoding="utf-8"))
stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))


def find(name, tier):
    return next(s for s in sites if s["n"] == name and s["t"] == tier)


toronto = find("City of Toronto", "Single Tier")
niagara_regional = find("Niagara – regional office", "Upper Tier")
niagara_local = [s for s in sites if s["t"] == "Lower Tier" and s["a"] == "Niagara"]
niagara_local_pop = sum(s["pl"] for s in niagara_local)
niagara_local_dist = sum(s["pl"] * s["dl"] for s in niagara_local) / niagara_local_pop

# The text says Toronto's zone is the most populous in both views and that Niagara has twelve local offices.
for pop_field in ("pl", "pr"):
    biggest = max((s for s in sites if pop_field in s), key=lambda s: s[pop_field])
    assert biggest is toronto, f"{biggest['n']} has the most people in {pop_field}, not Toronto"
assert len(niagara_local) == 12, f"Niagara has {len(niagara_local)} local offices, not 12"

# Count from the office list itself: sites.json merges offices that share coordinates.
offices = pd.read_csv(OFFICES_PATH)
total = len(offices)
low_confidence = int((offices["confidence"] < 0.9).sum())
checks = len(pd.read_csv(CHECKS_PATH))
fmt = "{:,}".format

# Where the map looks at each step: view, shade, centre/zoom and which office's zone to outline.
GTA = {"center": [43.75, -79.5], "zoom": 9.5}
NIAGARA = {"center": [43.1, -79.3], "zoom": 10}
steps = {
    "province": ({"view": "local", "shade": "tier", "center": [47, -81], "zoom": 5.5, "highlight": ""},
                 "Local offices, coloured by tier"),
    "distance": ({"view": "local", "shade": "dist", "center": [47, -81], "zoom": 5.5, "highlight": ""},
                 "Local offices, shaded by average distance to the office"),
    "toronto-local": ({"view": "local", "shade": "tier", **GTA, "highlight": toronto["n"]},
                      "Local offices; Toronto's zone outlined"),
    "toronto-regional": ({"view": "upper", "shade": "tier", **GTA, "highlight": toronto["n"]},
                         "Regional and single-tier offices; Toronto's zone outlined"),
    "toronto-people": ({"view": "upper", "shade": "pop", **GTA, "highlight": toronto["n"]},
                       "Regional and single-tier offices, shaded by people served"),
    "niagara-local": ({"view": "local", "shade": "tier", **NIAGARA, "highlight": ""},
                      "Local offices, coloured by tier"),
    "niagara-regional": ({"view": "upper", "shade": "tier", **NIAGARA, "highlight": niagara_regional["n"]},
                         "Regional and single-tier offices; Niagara's zone outlined"),
    "niagara-boundaries": ({"view": "bound", "shade": "tier", **NIAGARA, "highlight": ""},
                           "Local offices with the original municipal boundaries on top"),
}

values = {
    "TOTAL": fmt(total),
    "LOCAL_MEAN": stats["local"]["mean"],
    "LOCAL_MEDIAN": stats["local"]["median"],
    "LOCAL_P90": stats["local"]["p90"],
    "LOCAL_MAX": stats["local"]["max"],
    "LOCAL_WITHIN10": round(stats["local"]["within"]["10"]),
    "REGIONAL_WITHIN10": round(stats["upper"]["within"]["10"]),
    "REGIONAL_MEAN": stats["upper"]["mean"],
    "COVERAGE": stats["local"]["coverage"],
    "T_LOCAL_POP": fmt(toronto["pl"]),
    "T_LOCAL_DIST": toronto["dl"],
    "T_REG_POP": fmt(toronto["pr"]),
    "T_REG_DIST": toronto["dr"],
    "N_LOCAL_POP": fmt(round(niagara_local_pop, -3)),
    "N_LOCAL_DIST": f"{niagara_local_dist:.1f}",
    "N_REG_POP": fmt(niagara_regional["pr"]),
    "N_REG_DIST": niagara_regional["dr"],
    "N_FACTOR": f"{niagara_regional['dr'] / niagara_local_dist:.1f}",
    "LOW_CONF": low_confidence,
    "CHECKS": checks,
}

html = TEMPLATE_PATH.read_text(encoding="utf-8")
for key, value in values.items():
    html = html.replace(f"__{key}__", str(value))
html = html.replace(
    "__STEPS__",
    json.dumps({k: {"state": state, "caption": caption} for k, (state, caption) in steps.items()}, ensure_ascii=False),
)
assert "__" not in html.replace("__STEPS__", ""), "unfilled placeholder in story template"

OUTPUT_PATH.write_text(html, encoding="utf-8")
print(f"Wrote {OUTPUT_PATH}")
for key, value in values.items():
    print(f"  {key} = {value}")
