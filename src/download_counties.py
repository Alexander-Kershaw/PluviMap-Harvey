from pathlib import Path
import urllib.request
from termcolor import colored

URL = "https://www2.census.gov/geo/tiger/GENZ2022/shp/cb_2022_us_county_500k.zip"
OUT = Path("data/boundaries/cb_2022_us_county_500k.zip")

OUT.parent.mkdir(parents=True, exist_ok=True)

print(colored(f"Downloading: {URL}", "light_magenta"))
urllib.request.urlretrieve(URL, OUT)
print(colored(f"Saved to: {OUT} ({OUT.stat().st_size/1e6:.1f} MB)", "light_cyan"))
