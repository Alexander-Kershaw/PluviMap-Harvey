from __future__ import annotations

from pathlib import Path
from datetime import date, timedelta

import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import branca.colormap as cm
from folium.features import GeoJsonTooltip
from folium.raster_layers import ImageOverlay

import matplotlib.pyplot as plt
from shapely.geometry import Point
import rasterio

import streamlit as st
from streamlit_folium import st_folium


# Define Paths and constants
COUNTIES_PATH = Path("data/boundaries/us_counties_tx_wgs84_simplified.gpkg")

OUT_STATS_DIR = Path("outputs/stats")
OUT_RASTERS_DIR = Path("outputs/rasters")

# storm Harvey dates
def harvey_daily_dates() -> list[str]:
    start = date(2017, 8, 25)
    end = date(2017, 9, 1)
    d = start
    out = []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out

# Basic window presets
WINDOW_PRESETS: dict[str, tuple[str, str] | None] = {
    "Daily (pick a date)": None,  # special case
    "3-day (2017-08-26 → 2017-08-28)": ("2017-08-26", "2017-08-28"),
    "7-day storm total (2017-08-25 → 2017-09-01)": ("2017-08-25", "2017-09-01"),
}


# Cached loaders
@st.cache_data
def load_counties() -> gpd.GeoDataFrame:
    gdf = gpd.read_file(COUNTIES_PATH)[["GEOID", "NAME", "geometry"]].copy()
    gdf["GEOID"] = gdf["GEOID"].astype(str)

    # Ensure WGS84 for folium + click logic
    if gdf.crs is None or str(gdf.crs).lower() != "epsg:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf


@st.cache_data
def load_stats(stats_csv: str) -> pd.DataFrame:
    df = pd.read_csv(stats_csv, dtype={"GEOID": "string"})

    # normalize to plain Python str
    df["GEOID"] = df["GEOID"].astype(str)

    keep = ["GEOID", "NAME", "mean_mm", "max_mm", "p95_mm"]
    cols = [c for c in keep if c in df.columns]
    return df[cols].copy()


@st.cache_data
def get_raster_bounds(tif_path: str) -> list[list[float]]:
    with rasterio.open(tif_path) as src:
        b = src.bounds
        # Folium expects [[south, west], [north, east]] format
        return [[b.bottom, b.left], [b.top, b.right]]


@st.cache_data
def load_png_as_rgba(png_path: str) -> np.ndarray:
    # Load PNG into (H, W, bands) uint8 array for Folium Image Overlay
    with rasterio.open(png_path) as src:
        img = src.read()  # (bands, H, W)
    img = np.moveaxis(img, 0, -1)  # (H, W, bands)
    if img.dtype != np.uint8:
        img = img.astype(np.uint8)
    return img


# Geo helpers
def find_county_by_click(gdf: gpd.GeoDataFrame, lat: float, lon: float):
    # Return first county polygon containing clicked point (lon/lat)
    pt = Point(lon, lat)
    hits = gdf[gdf.contains(pt)]
    if len(hits) == 0:
        return None
    return hits.iloc[0]


# Choropleth Map builder
def make_choropleth(
    gdf: gpd.GeoDataFrame,
    metric: str,
    show_raster: bool,
    tif_path: str,
    png_path: str,
    start: str,
    end: str,
):
    values = gdf[metric].dropna()
    vmin, vmax = float(values.min()), float(values.max())

    m = folium.Map(location=[29.6, -95.4], zoom_start=6, tiles="OpenStreetMap")

    # Optional raster overlay
    if show_raster:
        bounds = get_raster_bounds(tif_path)
        img = load_png_as_rgba(png_path)
        ImageOverlay(
            name=f"Rainfall raster (mm) {start}→{end}",
            image=img,
            bounds=bounds,
            opacity=0.60,
            zindex=1,
            interactive=False,
            cross_origin=False,
        ).add_to(m)

    colormap = cm.linear.YlGnBu_09.scale(vmin, vmax)
    colormap.caption = f"{metric} (mm) — Harvey {start} → {end}"

    def style_function(feature):
        val = feature["properties"].get(metric)
        if val is None:
            fill = "#00000000"
            opacity = 0.0
        else:
            fill = colormap(val)
            opacity = 0.75
        return {"fillColor": fill, "color": "black", "weight": 1, "fillOpacity": opacity}

    tooltip = GeoJsonTooltip(
        fields=["NAME", "mean_mm", "max_mm", "p95_mm"],
        aliases=["County", "Mean (mm)", "Max (mm)", "P95 (mm)"],
        localize=True,
        sticky=False,
        labels=True,
    )

    folium.GeoJson(
        gdf,
        name=f"County choropleth ({metric})",
        style_function=style_function,
        tooltip=tooltip,
    ).add_to(m)

    colormap.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)

    return m, (vmin, vmax)



# Streamlit
def main():
    st.set_page_config(page_title="PluviMap — Hurricane Harvey", layout="wide")

    st.title("PluviMap — Hurricane Harvey (2017)")
    st.write("Texas county rainfall impact explorer using ERA5 daily precipitation and zonal statistics.")

    # Sidebar controls
    metrics = {
        "Mean rainfall (mm)": "mean_mm",
        "Max rainfall (mm)": "max_mm",
        "95th percentile rainfall (mm)": "p95_mm",
    }

    with st.sidebar:
        st.header("Controls")

        # Window selection
        st.subheader("Window")
        mode = st.selectbox("Mode", list(WINDOW_PRESETS.keys()), index=0)

        if mode == "Daily (pick a date)":
            day = st.selectbox("Date", harvey_daily_dates(), index=2)  # defaults around Aug 27
            start, end = day, day
        else:
            start, end = WINDOW_PRESETS[mode]  # type: ignore[misc]

        window_id = f"harvey_{start}_{end}"

        # Metric selection
        st.subheader("Metric")
        metric_label = st.selectbox("Metric to map", list(metrics.keys()), index=2)
        metric = metrics[metric_label]

        top_n = st.slider("Top N counties", min_value=5, max_value=50, value=10, step=1)
        show_raster = st.checkbox("Show rainfall raster overlay", value=False)

    # Dynamic paths for chosen window
    stats_csv = OUT_STATS_DIR / f"{window_id}_county_stats.csv"
    tif_path = OUT_RASTERS_DIR / f"{window_id}_tp_mm.tif"
    png_path = OUT_RASTERS_DIR / f"{window_id}_tp_mm.png"

    missing = [p for p in [stats_csv, tif_path, png_path] if not p.exists()]
    if missing:
        st.error(
            "Missing files for selected window. Build them first:\n\n"
            + "\n".join([f"- {p}" for p in missing])
        )
        st.stop()

    st.subheader(f"Accumulation window: {start} → {end}")

    # Load/merge data
    counties = load_counties()
    stats = load_stats(str(stats_csv))

    # Avoid duplicate NAME column on merge
    if "NAME" in stats.columns:
        stats = stats.drop(columns=["NAME"])

    # Hard enforcing merge key dtypes due to streamlit cache issues
    counties["GEOID"] = counties["GEOID"].astype(str)
    stats["GEOID"] = stats["GEOID"].astype(str)

    gdf = counties.merge(stats, on="GEOID", how="left")

    # Layout
    left, right = st.columns([2, 1])

    # Display raster gif showing evolution of storm
    st.subheader("Daily rainfall overlay animation (8 days)")
    gif_path = Path("outputs/rasters/harvey_daily_rainfall_2017-08-25_to_2017-09-01.gif")
    if gif_path.exists():
        st.image(str(gif_path), caption="ERA5 daily rainfall overlay (mm), Aug 25 → Sep 1, 2017")
    else:
        st.info("GIF not found yet. Run: python src/make_raster_gif.py")

    with left:
        st.subheader("Map")

        m, (vmin, vmax) = make_choropleth(
            gdf=gdf,
            metric=metric,
            show_raster=show_raster,
            tif_path=str(tif_path),
            png_path=str(png_path),
            start=start,
            end=end,
        )

        st.caption(f"Scale: {vmin:.2f} → {vmax:.2f} mm")

        map_state = st_folium(m, width=900, height=650)

    with right:
        # Selected county panel
        st.subheader("Selected County")
        clicked = map_state.get("last_clicked") or map_state.get("last_object_clicked")

        selected = None
        if clicked and "lat" in clicked and "lng" in clicked:
            selected = find_county_by_click(gdf, clicked["lat"], clicked["lng"])

        if selected is None:
            st.info("Click a county on the map to see details here.")
        else:
            st.write(f"**{selected['NAME']}**  (GEOID: {selected['GEOID']})")

            mean_v = float(selected["mean_mm"]) if pd.notna(selected["mean_mm"]) else float("nan")
            max_v = float(selected["max_mm"]) if pd.notna(selected["max_mm"]) else float("nan")
            p95_v = float(selected["p95_mm"]) if pd.notna(selected["p95_mm"]) else float("nan")

            st.write(
                f"- Mean: **{mean_v:.2f} mm**\n"
                f"- P95: **{p95_v:.2f} mm**\n"
                f"- Max: **{max_v:.2f} mm**"
            )

            # Bar chart
            fig = plt.figure()
            labels = ["mean_mm", "p95_mm", "max_mm"]
            values = [mean_v, p95_v, max_v]
            plt.bar(labels, values)
            plt.ylabel("mm")
            plt.title(f"Rainfall stats ({start} → {end})")
            st.pyplot(fig, clear_figure=True)

        # Leaderboard
        st.subheader(f"Leaderboard (Top {top_n})")
        table = gdf[["GEOID", "NAME", "mean_mm", "max_mm", "p95_mm"]].copy()
        table = table.sort_values(metric, ascending=False).head(top_n)

        for c in ["mean_mm", "max_mm", "p95_mm"]:
            table[c] = table[c].round(2)

        st.dataframe(table, use_container_width=True)

        st.download_button(
            "Download table as CSV",
            data=table.to_csv(index=False).encode("utf-8"),
            file_name=f"{window_id}_top_{top_n}_{metric}.csv",
            mime="text/csv",
        )

    st.markdown("---")
    st.subheader("Notes")
    st.write(
        "- Boundaries: US Census cartographic county boundaries (TX), simplified to WGS84.\n"
        "- Rainfall: ERA5 total precipitation daily sums, converted to mm.\n"
        "- Windows: daily (Aug 25 → Sep 1, 2017) plus preset multi-day windows.\n"
        "- Analytics: zonal stats per county (mean, max, p95).\n"
        "- Raster overlay: portable PNG overlay derived from GeoTIFF (no tile server)."
    )


if __name__ == "__main__":
    main()
