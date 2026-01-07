from pathlib import Path
import geopandas as gpd

# Path to US country boundaries ZIP and output directory
ZIP = Path("data/boundaries/cb_2022_us_county_500k.zip")
OUT = Path("data/boundaries/us_counties_tx_wgs84_simplified.gpkg")

# Storm Harvey is relevant to Texas counties (STATEFP == "48")
# everything kepy in WGS84 for mapping and consistency with ERA5
def main():
    # Read directly from zip
    gdf = gpd.read_file(f"zip://{ZIP}")

    # Keep only counties (STATEFP, COUNTYFP, GEOID, NAME, geometry)
    keep = ["STATEFP", "COUNTYFP", "GEOID", "NAME", "geometry"]
    gdf = gdf[keep]

    # Filter for Texas
    gdf_tx = gdf[gdf["STATEFP"] == "48"].copy()

    # Reproject to WGS84 (lat/lon)
    gdf_tx = gdf_tx.to_crs(epsg=4326)

    # simplification for web performance
    gdf_tx["geometry"] = gdf_tx.geometry.simplify(0.01, preserve_topology=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf_tx.to_file(OUT, driver="GPKG")

    print("Saved:", OUT)
    print("Rows (TX counties):", len(gdf_tx))
    print("CRS:", gdf_tx.crs)

if __name__ == "__main__":
    main()
