from __future__ import annotations
from pathlib import Path
from datetime import date, timedelta
from termcolor import colored
import cdsapi

# South East Texas / Gulf bounding box: [N, W, S, E] (Where hurricane Harvey hit)
AREA = [31.5, -98.5, 26.5, -93.0]

OUT_DIR = Path("data/era5_daily")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Fetch era5 data for single day
def fetch_day(d: date) -> Path:
    y, m, dd = d.strftime("%Y"), d.strftime("%m"), d.strftime("%d")
    out = OUT_DIR / f"era5_tp_daily_sum_{d.isoformat()}.nc"

    # Skip if already downloaded
    if out.exists() and out.stat().st_size > 0:
        print("Exists, skipping:", out.name)
        return out

    c = cdsapi.Client()

    request = {
        "product_type": "reanalysis",
        "variable": ["total_precipitation"],
        "year": y,
        "month": [m],
        "day": [dd],
        "daily_statistic": "daily_sum",
        "time_zone": "utc+00:00",
        "frequency": "1_hourly",
        "area": AREA,
        "format": "netcdf",
    }

    print("Requesting:", d.isoformat())
    c.retrieve("derived-era5-single-levels-daily-statistics", request, str(out))
    print("Saved:", out)
    return out

# Temporal bounds for Harvey timeframe
def fetch_range(start: str, end: str):
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    d = d0
    while d <= d1:
        fetch_day(d)
        d += timedelta(days=1)

if __name__ == "__main__":
    fetch_range("2017-08-25", "2017-09-01")
