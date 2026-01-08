from pathlib import Path
from datetime import date, timedelta
from PIL import Image

OUT_DIR = Path("outputs/rasters")
GIF_PATH = OUT_DIR / "harvey_daily_rainfall_2017-08-25_to_2017-09-01.gif"

def daterange(d0: date, d1: date):
    d = d0
    while d <= d1:
        yield d
        d += timedelta(days=1)

def main():
    start = date(2017, 8, 25)
    end = date(2017, 9, 1)

    frames = []
    for d in daterange(start, end):
        window_id = f"harvey_{d.isoformat()}_{d.isoformat()}"
        png = OUT_DIR / f"{window_id}_tp_mm.png"
        if not png.exists():
            raise FileNotFoundError(f"Missing: {png}")

        img = Image.open(png).convert("RGBA")
        frames.append(img)

    # duration is milliseconds per frame
    frames[0].save(
        GIF_PATH,
        save_all=True,
        append_images=frames[1:],
        duration=600,
        loop=0,
        disposal=2,
    )

    print("Wrote:", GIF_PATH.resolve())

if __name__ == "__main__":
    main()
