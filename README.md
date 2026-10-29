# Ontario nearest municipal office map

Hover anywhere in Ontario to see the nearest municipal office. Open `index.html`
in a browser (it is a single self-contained page; it needs internet for the map
tiles and libraries).

## Rebuild

    pip install -r requirements.txt
    python prepare_data.py "<Geocoded Cities of Ontario.xlsx>" "<example map .html>"   # data/*.csv, data/*.json
    python build_site.py                                                               # index.html

`prepare_data.py` reads the "Realised I needed tiers" sheet for the offices and
takes the Ontario land outline and municipal boundaries from the example map.
`make_map.py` is an earlier folium prototype.
