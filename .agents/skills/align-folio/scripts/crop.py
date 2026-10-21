"""Crop a folio image into pieces small enough for an agent to read.

Run with Pillow in a throwaway env (no project dependency):

    uv run --no-project --with pillow python crop.py IMAGE --out-dir DIR [options]

Boxes are fractions of the full image (0-1), so they work on any image size.
Each piece is scaled down to at most --max-side pixels on its long side.
Prints one line per piece: path and the pixel box it came from.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def _box(text: str) -> tuple[float, float, float, float]:
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4 or not all(0 <= p <= 1 for p in parts):
        raise argparse.ArgumentTypeError("box is x0,y0,x1,y1 as fractions 0-1")
    x0, y0, x1, y1 = parts
    if x0 >= x1 or y0 >= y1:
        raise argparse.ArgumentTypeError("box needs x0 < x1 and y0 < y1")
    return x0, y0, x1, y1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument(
        "--box",
        type=_box,
        default=(0.0, 0.0, 1.0, 1.0),
        help="Region to crop first, x0,y0,x1,y1 as fractions. Default: whole image.",
    )
    ap.add_argument(
        "--columns",
        type=int,
        default=1,
        help="Split the region into this many equal vertical strips.",
    )
    ap.add_argument(
        "--rows",
        type=int,
        default=1,
        help="Split each strip into this many equal horizontal pieces.",
    )
    ap.add_argument(
        "--overlap",
        type=float,
        default=0.03,
        help="Extra margin on each piece, as a fraction of the piece size.",
    )
    ap.add_argument("--max-side", type=int, default=1500)
    ap.add_argument("--prefix", default="crop")
    args = ap.parse_args()

    im = Image.open(args.image)
    w, h = im.size
    x0, y0, x1, y1 = args.box
    rx0, ry0, rx1, ry1 = x0 * w, y0 * h, x1 * w, y1 * h
    cw = (rx1 - rx0) / args.columns
    rh = (ry1 - ry0) / args.rows
    args.out_dir.mkdir(parents=True, exist_ok=True)
    # Hebrew reads right to left: c1 is the rightmost strip.
    for c in range(args.columns):
        for r in range(args.rows):
            left = rx1 - (c + 1) * cw - cw * args.overlap
            right = rx1 - c * cw + cw * args.overlap
            top = ry0 + r * rh - rh * args.overlap
            bottom = ry0 + (r + 1) * rh + rh * args.overlap
            box = (
                max(0, int(left)),
                max(0, int(top)),
                min(w, int(right)),
                min(h, int(bottom)),
            )
            piece = im.crop(box)
            piece.thumbnail((args.max_side, args.max_side))
            dest = args.out_dir / f"{args.prefix}-c{c + 1}-r{r + 1}.jpg"
            piece.convert("RGB").save(dest, quality=90)
            print(f"{dest}\t{box}")


if __name__ == "__main__":
    main()
