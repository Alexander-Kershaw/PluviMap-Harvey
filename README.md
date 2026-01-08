# PluviMap — Hurricane Harvey (2017)

PluviMap is an interactive geospatial dashboard that explores the spatial and temporal evolution of extreme rainfall during Hurricane Harvey (August–September 2017) across Texas counties.

The project uses ERA5 reanalysis data to compute daily and multi-day rainfall accumulations, county-level zonal statistics, and animated raster overlays.

---

## Features

- ERA5 daily precipitation ingestion
- County-level zonal rainfall statistics (mean / max / p95)
- Daily and multi-day accumulation windows
- Interactive Streamlit dashboard
- Click-to-inspect county analytics
- Raster + vector overlays
- Animated daily rainfall GIF

---

## Data Sources

- **ERA5 Reanalysis (ECMWF / Copernicus)**
  - Total precipitation (daily sums)
- **US Census Bureau**
  - Cartographic boundary files (Texas counties)

---

## Methods

1. Download ERA5 daily precipitation for Aug 25 – Sep 1, 2017
2. Convert precipitation from meters to millimeters
3. Generate daily and multi-day accumulation rasters
4. Compute zonal statistics per county
5. Export rasters to portable PNG overlays
6. Visualize results in an interactive Streamlit app

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py

```

---

## Future additions

- Wind speed overlay (ERA5 hourly)
- Storm track overlay (NOAA track)