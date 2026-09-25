"""Make background-free vial images for product cards and product pages.

    pip install "rembg[cpu]" pillow        # one-off; not needed to build the site
    python3 tools/make_cutouts.py photo.png [more.png ...] --out public/assets/img/cutouts

Each input should be a large product photo named after the product slug
(e.g. bpc-157-10mg.png); the output is <slug>.webp. build.py uses a cut-out
whenever public/assets/img/cutouts/<slug>.webp exists, so a new product needs
one of these or its card falls back to the plain photo.

How: rembg's isnet-general-use model finds the vial, then holes inside the
mask are filled (the model tends to punch through white labels) and the edge
is softened slightly. Check the result on a dark background before shipping.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from rembg import new_session, remove


def cutout(src: Image.Image, session) -> Image.Image:
    src = src.convert("RGB")
    mask = remove(src, session=session, only_mask=True, post_process_mask=True).convert("L")
    solid = mask.point(lambda v: 255 if v > 40 else 0)
    # Flood the background in from a padded border; anything it can't reach
    # is inside the vial, so the holes become part of it.
    pad = Image.new("L", (solid.width + 2, solid.height + 2), 0)
    pad.paste(solid, (1, 1))
    ImageDraw.floodfill(pad, (0, 0), 128)
    filled = pad.crop((1, 1, solid.width + 1, solid.height + 1)).point(lambda v: 0 if v == 128 else 255)
    alpha = ImageChops.lighter(mask, filled.filter(ImageFilter.MinFilter(3))).filter(ImageFilter.GaussianBlur(0.8))
    out = src.convert("RGBA")
    out.putalpha(alpha)
    return out.crop(out.getbbox())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("photos", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=Path("public/assets/img/cutouts"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    session = new_session("isnet-general-use")
    for photo in args.photos:
        img = cutout(Image.open(photo), session)
        img.thumbnail((320, 740))   # cards and the product stage never show it larger
        target = args.out / f"{photo.stem}.webp"
        img.save(target, "WEBP", quality=80, method=6)
        print(f"{photo} -> {target} {img.size}")


if __name__ == "__main__":
    main()
