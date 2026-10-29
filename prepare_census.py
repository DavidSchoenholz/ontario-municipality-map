import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
OUTPUT_PATH = ROOT / "data" / "population_points.csv"

# Usage: python prepare_census.py "<2021_92-151_X.zip>"
# The 2021 Geographic Attribute File has population per dissemination block (DB) but
# coordinates only per dissemination area (DA), so blocks are summed up to their DA.
zip_path = Path(sys.argv[1])

COLUMNS = {
    "PRUID_PRIDU": "province",
    "DAUID_ADIDU": "da",
    "DARPLAT_ADLAT": "latitude",
    "DARPLONG_ADLONG": "longitude",
    "DBPOP2021_IDPOP2021": "population",
}

chunks = []
for chunk in pd.read_csv(zip_path, usecols=list(COLUMNS), encoding="latin-1", chunksize=500_000):
    chunk = chunk.rename(columns=COLUMNS)
    chunks.append(chunk[chunk["province"] == 35])
blocks = pd.concat(chunks)

das = (
    blocks.groupby("da")
    .agg(population=("population", "sum"), latitude=("latitude", "first"), longitude=("longitude", "first"))
    .reset_index()
)
das["population"] = das["population"].astype(int)

das.to_csv(OUTPUT_PATH, index=False)
print(f"Wrote {len(das)} dissemination areas ({das['population'].sum():,} people) to {OUTPUT_PATH}")
