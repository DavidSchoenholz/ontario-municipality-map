from pathlib import Path

import pandas as pd

CSV_PATH = Path(__file__).parent / "data" / "city_halls_sample.csv"

df = pd.read_csv(CSV_PATH)

print(df)
print()
print(df.dtypes)
print()
print(f"{len(df)} rows, {len(df.columns)} columns")
