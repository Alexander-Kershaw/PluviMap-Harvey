from __future__ import annotations

from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd
import geopandas as gpd
import xarray as xr
import rioxarray 
import rasterio
import matplotlib.pyplot as plt
from rasterstats import zonal_stats

COUNTIES_PATH = Path("data/boundaries/us_counties_tx_wgs84_simplified.gpkg") # Path to extracted Texas county boundaries
DAILY_DIR = Path("data/era5_daily") # Path to era5 daily data

OUT_RASTERS = Path("outputs/rasters") # Out directory for raster overlays
OUT_STATS = Path("outputs/stats") # Out directory  for weather statistics

# Establish date range
def daterange(d0: date, d1: date):
    d = d0
    while d <= d1:
        yield d
        d += timedelta(days=1)

# Load daily precipitation data
def load_daily_tp_mm(nc_path: Path) -> xr.DataArray:
    ds = xr.open_dataset(nc_path)

    if "tp" in ds.data_vars:
        da = ds["tp"]
    elif "total_precipitation" in ds.data_vars:
        da = ds["total_precipitation"]
    else:
        raise ValueError(f"tp not found in {nc_path.name}. Vars: {list(ds.data_vars)}")

    # meters -> mm (more convensional unit measure for total precipitation)
    da_mm = (da * 1000.0).rename("tp_mm")
    da_mm.attrs["units"] = "mm"

    # normalize coords
    rename = {}
    if "longitude" in da_mm.coords: rename["longitude"] = "x"
    if "latitude" in da_mm.coords:  rename["latitude"] = "y"
    if "lon" in da_mm.coords:       rename["lon"] = "x"
    if "lat" in da_mm.coords:       rename["lat"] = "y"
    da_mm = da_mm.rename(rename)

    if "time" in da_mm.dims:
        da_mm = da_mm.isel(time=0)

    # y should be north->south
    if da_mm.y[0] < da_mm.y[-1]:
        da_mm = da_mm.sortby("y", ascending=False)

    da_mm = da_mm.rio.set_spatial_dims(x_dim="x", y_dim="y").rio.write_crs("EPSG:4326")
    return da_mm


def export_geotiff(da_mm: xr.DataArray, out_tif: Path):
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    da_mm.rio.to_raster(out_tif)


def choose_png_vmax_from_raster(tif_path: Path) -> float:
    """
    Display vmax that makes the static PNG readable:
    Using 99th percentile with a small buffer, bounded to a sensible range.
    """
    with rasterio.open(tif_path) as src:
        arr = src.read(1, masked=True).compressed()
        if arr.size == 0:
            return 50.0
        p99 = float(np.percentile(arr, 99))
        vmax = p99 * 1.2  # Some headroom
        # Clamped so tiny-rain days still show some contrast, and huge outliers don't overpower everything else
        return float(np.clip(vmax, 30.0, 300.0))


def export_png_from_tif(tif_path: Path, png_path: Path, vmin=0.0, vmax=120.0):
    png_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(tif_path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)

    # Transparent where near-zero rain
    alpha = np.where(np.isfinite(arr) & (arr > 1.0), 1.0, 0.0)

    scaled = (arr - vmin) / (vmax - vmin)
    scaled = np.clip(scaled, 0, 1)

    fig = plt.figure(figsize=(6, 6), dpi=200)
    ax = plt.axes([0, 0, 1, 1])
    ax.set_axis_off()

    im = ax.imshow(scaled, interpolation="nearest", vmin=0, vmax=1, alpha=alpha)
    im.set_cmap("viridis")

    plt.savefig(png_path, transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def compute_county_stats(counties_path: Path, raster_path: Path, out_csv: Path):
    gdf = gpd.read_file(counties_path)[["GEOID", "NAME", "geometry"]]

    stats = zonal_stats(
        vectors=gdf,
        raster=raster_path,
        stats=["mean", "max", "percentile_95"],
        nodata=None,
        geojson_out=False,
    )

    df = pd.DataFrame(stats).rename(
        columns={"mean": "mean_mm", "max": "max_mm", "percentile_95": "p95_mm"}
    )

    out = pd.concat([gdf[["GEOID", "NAME"]].reset_index(drop=True), df], axis=1)
    out = out.sort_values("max_mm", ascending=False)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_csv, index=False)

# Build for singular daily window
def build_one_day(d: date):
    nc = DAILY_DIR / f"era5_tp_daily_sum_{d.isoformat()}.nc"
    if not nc.exists():
        raise FileNotFoundError(f"Missing daily file: {nc}")

    window_id = f"harvey_{d.isoformat()}_{d.isoformat()}"
    out_tif = OUT_RASTERS / f"{window_id}_tp_mm.tif"
    out_png = OUT_RASTERS / f"{window_id}_tp_mm.png"
    out_csv = OUT_STATS / f"{window_id}_county_stats.csv"

    # Skip if everything exists already
    if out_tif.exists() and out_png.exists() and out_csv.exists():
        print("Exists, skipping:", window_id)
        return

    da_mm = load_daily_tp_mm(nc)
    export_geotiff(da_mm, out_tif)

    vmax = choose_png_vmax_from_raster(out_tif)
    export_png_from_tif(out_tif, out_png, vmin=0.0, vmax=vmax)

    compute_county_stats(COUNTIES_PATH, out_tif, out_csv)

    print(f"Built {window_id} (png vmax ~ {vmax:.1f} mm)")


def main():
    OUT_RASTERS.mkdir(parents=True, exist_ok=True)
    OUT_STATS.mkdir(parents=True, exist_ok=True)

    start = date.fromisoformat("2017-08-25")
    end = date.fromisoformat("2017-09-01")

    for d in daterange(start, end):
        build_one_day(d)


if __name__ == "__main__":
    main()
