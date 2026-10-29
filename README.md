# Ontario nearest municipal office map

How far Ontarians live from their nearest municipal office, as a Voronoi map: every point
on municipal land belongs to the zone of its nearest office.

- `index.html` is the story page: text on the left, one map on the right that moves as you
  scroll (province, Toronto, Niagara).
- `map.html` is the full explorer: three views (local offices, regional/single-tier offices,
  original municipal boundaries), cells shaded by tier, people served or average distance,
  search by office, town, postal code or address, "use my location", and a
  population-weighted distance summary.

Both are static pages that need internet for the map tiles and libraries (and for address search).

## Rebuild

    pip install -r requirements.txt
    python prepare_data.py "<Geocoded Cities of Ontario.xlsx>"                       # data/municipal_offices.csv
    python prepare_geometry.py "<Municipal_Boundary_-_Lower_and_Single_Tier.shp>"    # outline + boundaries (slow, a few minutes)
    python prepare_census.py "<2021_92-151_X.zip>"                                   # data/population_points.csv
    python build_site.py                                                             # map.html, data/office_checks.csv, data/sites.json, data/stats.json
    python build_story.py                                                            # index.html

- Offices come from the "Realised I needed tiers" sheet of the workbook.
- The map is clipped to the municipal boundary layer (Ontario lower and single tier).
- Population is the 2021 census (Geographic Attribute File), summed to dissemination areas.
- `data/office_checks.csv` lists offices that sit outside or in the wrong tier of municipality,
  and municipalities with no office (or several) inside them.
- The story text is in `templates/story.html`; its numbers are computed in `build_story.py`,
  which fails if a claim in the text stops being true (e.g. Toronto no longer the most populous zone).
- `make_map.py` is an earlier folium prototype.
