"""Crop a folio image into column pieces small enough for an agent to read.

Needs Pillow only. Run it in a throwaway env (no project dependency):

    uv run --no-project --with pillow python crop.py IMAGE --out-dir DIR [mode]

Modes (c1 is always the rightmost column, as the codex reads right to left):

    --auto [--columns N]     find the columns from the ink on the page.
                             N is the number of columns you expect; it
                             makes the search more reliable.
    --box x0,y0,x1,y1        cut this region into --columns equal strips
         [--columns N]       (default: the whole image, 1 column).
    --column-box N=x0,y0,x1,y1
                             set column N yourself (repeatable). With
                             --auto it replaces column N only. Without
                             --auto it gives the full list of columns.

Boxes are fractions of the full image (0-1), so they work on any image
size. Each column is split into --rows pieces. Each piece is scaled down
to at most --max-side pixels on its long side.

Besides the crops it writes DIR/crops.json: the image sha256, the box and
sha256 of every crop, and any warnings. ingest-folio requires this file.

It warns when ink touches the outer edge of a column's crops (text is
probably cut off) and when --columns does not match what it found. A
warning is not an error: look at the crops, then fix the box or accept it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

MANIFEST_VERSION = 1

ANALYSIS_WIDTH = 800
INK_FRACTION = 0.12  # the darkest 12% of pixels count as ink
X_PROFILE_ROWS = (0.12, 0.90)  # rows used to find columns (skips margin notes)
Y_LIMITS = (0.03, 0.97)  # rows used to find the text height (skips page edge)
RUN_THRESHOLDS = (0.25, 0.20, 0.30, 0.15, 0.35, 0.10, 0.40, 0.50)
MIN_COLUMN_WIDTH = 0.06
EDGE_LOW = 0.05  # grow a column edge while the profile is above this share
X_PAD = 0.01
Y_PAD = 0.01
Y_THRESHOLD = 0.08
EDGE_BAND = 0.012  # width of the band checked at each outer edge
# Band ink / interior ink above this is a warning. Cut-off text measured
# 0.48 and up; margin notes next to a column measured 0.14 and down.
EDGE_RATIO = 0.25
SUGGEST_STEP = 0.005
SUGGEST_MAX = 0.10

Box = tuple[float, float, float, float]


# --- ink analysis -----------------------------------------------------------


def ink_mask(im: Image.Image) -> Image.Image:
    """Small black/white copy of the page: white = ink."""
    gray = im.convert("L")
    gray.thumbnail((ANALYSIS_WIDTH, ANALYSIS_WIDTH * 2))
    hist = gray.histogram()
    total = sum(hist)
    seen = 0
    cut = 0
    for value, count in enumerate(hist):
        seen += count
        if seen >= total * INK_FRACTION:
            cut = value
            break
    if sum(hist[: cut + 1]) > total * 0.5:
        # Most of the page is as dark as the "ink" (a blank or flat image):
        # there is no ink to find.
        return Image.new("L", gray.size, 0)
    return gray.point(lambda v: 255 if v <= cut else 0)


def _px(mask: Image.Image, box: Box) -> tuple[int, int, int, int]:
    w, h = mask.size
    x0, y0 = int(round(box[0] * w)), int(round(box[1] * h))
    x1, y1 = int(round(box[2] * w)), int(round(box[3] * h))
    return x0, y0, max(x0 + 1, x1), max(y0 + 1, y1)


def density(mask: Image.Image, box: Box) -> float:
    """Share of ink (0-1) inside a box given as fractions."""
    region = mask.crop(_px(mask, box))
    return region.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0)) / 255


def _smooth(values: list[float], window: int) -> list[float]:
    window = max(1, window)
    half = window // 2
    out = []
    running = [0.0]
    for v in values:
        running.append(running[-1] + v)
    n = len(values)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        out.append((running[hi] - running[lo]) / (hi - lo))
    return out


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    start = None
    for i, on in enumerate(flags):
        if on and start is None:
            start = i
        elif not on and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(flags)))
    return out


def _x_profile(mask: Image.Image) -> list[float]:
    w, h = mask.size
    rows = mask.crop((0, int(h * X_PROFILE_ROWS[0]), w, int(h * X_PROFILE_ROWS[1])))
    return [v / 255 for v in rows.resize((w, 1), Image.Resampling.BOX).tobytes()]


def detect_columns(
    mask: Image.Image, expected: int | None
) -> list[tuple[float, float]]:
    """Column x-ranges (fractions), left to right."""
    w, _ = mask.size
    raw = _x_profile(mask)
    prof = _smooth(raw, w // 60)
    peak = max(prof, default=0)
    if peak <= 0:
        return []

    def segments(share: float) -> list[tuple[int, int]]:
        found = _runs([v > peak * share for v in prof])
        return [(s, e) for s, e in found if (e - s) / w >= MIN_COLUMN_WIDTH]

    chosen = segments(RUN_THRESHOLDS[0])
    if expected is not None:
        for share in RUN_THRESHOLDS:
            found = segments(share)
            if len(found) == expected:
                chosen = found
                break
    # Grow each edge outward while ink continues, up to the middle of the gap:
    # the left ends of Hebrew lines are ragged and the long lines run past a
    # dense core.
    fine = _smooth(raw, w // 200)
    low = max(fine, default=0) * EDGE_LOW
    grown = []
    for i, (s, e) in enumerate(chosen):
        left_limit = (chosen[i - 1][1] + s) // 2 if i > 0 else 0
        right_limit = (e + chosen[i + 1][0]) // 2 if i + 1 < len(chosen) else w
        while s > left_limit and fine[s - 1] > low:
            s -= 1
        while e < right_limit and fine[min(e, w - 1)] > low:
            e += 1
        grown.append((s, e))
    return [(s / w, e / w) for s, e in grown]


def detect_text_height(
    mask: Image.Image, x_lo: float, x_hi: float
) -> tuple[float, float]:
    w, h = mask.size
    strip = mask.crop((int(x_lo * w), 0, max(int(x_hi * w), int(x_lo * w) + 1), h))
    prof = _smooth(
        [v / 255 for v in strip.resize((1, h), Image.Resampling.BOX).tobytes()],
        h // 150,
    )
    lo, hi = int(Y_LIMITS[0] * h), int(Y_LIMITS[1] * h)
    window = prof[lo:hi]
    peak = max(window, default=0)
    on = [i + lo for i, v in enumerate(window) if v > peak * Y_THRESHOLD]
    if not on:
        return Y_LIMITS
    return on[0] / h, (on[-1] + 1) / h


def auto_columns(mask: Image.Image, expected: int | None) -> list[Box]:
    """Column boxes (fractions), c1 (rightmost) first."""
    spans = detect_columns(mask, expected)
    if not spans:
        return []
    y0, y1 = detect_text_height(mask, spans[0][0], spans[-1][1])
    boxes = [
        (
            max(0.0, s - X_PAD),
            max(0.0, y0 - Y_PAD),
            min(1.0, e + X_PAD),
            min(1.0, y1 + Y_PAD),
        )
        for s, e in spans
    ]
    return list(reversed(boxes))


def strip_columns(region: Box, count: int) -> list[Box]:
    """Equal vertical strips of a region, c1 (rightmost) first."""
    x0, y0, x1, y1 = region
    width = (x1 - x0) / count
    return [(x1 - (c + 1) * width, y0, x1 - c * width, y1) for c in range(count)]


# --- cropping ---------------------------------------------------------------


def piece_boxes(
    column: Box, size: tuple[int, int], rows: int, overlap: float
) -> list[tuple[int, int, int, int]]:
    """Pixel boxes of one column's pieces, top to bottom."""
    w, h = size
    cx0, cy0, cx1, cy1 = column[0] * w, column[1] * h, column[2] * w, column[3] * h
    cw, rh = cx1 - cx0, (cy1 - cy0) / rows
    out = []
    for r in range(rows):
        out.append(
            (
                max(0, int(cx0 - cw * overlap)),
                max(0, int(cy0 + r * rh - rh * overlap)),
                min(w, int(cx1 + cw * overlap)),
                min(h, int(cy0 + (r + 1) * rh + rh * overlap)),
            )
        )
    return out


def edge_warnings(mask: Image.Image, union: Box, number: int) -> list[dict]:
    """Warn when ink touches the outer edge of a column's crops."""
    x0, y0, x1, y1 = union
    bw, bh = EDGE_BAND, EDGE_BAND
    interior = density(mask, (x0 + bw, y0 + bh, x1 - bw, y1 - bh))
    if interior <= 0:
        return []
    bands = {
        "left": (x0, y0, x0 + bw, y1),
        "right": (x1 - bw, y0, x1, y1),
        "top": (x0, y0, x1, y0 + bh),
        "bottom": (x0, y1 - bh, x1, y1),
    }
    at_page_edge = {
        "left": x0 <= 0,
        "right": x1 >= 1,
        "top": y0 <= 0,
        "bottom": y1 >= 1,
    }
    warnings = []
    for edge, band in bands.items():
        if at_page_edge[edge]:
            continue
        ratio = density(mask, band) / interior
        if ratio <= EDGE_RATIO:
            continue
        warnings.append(
            {
                "kind": "edge_ink",
                "column": number,
                "edge": edge,
                "ink_ratio": round(ratio, 3),
                "message": f"column {number}: ink at the {edge} edge of the crop; "
                f"text may be cut off",
                "suggestion": _suggest(mask, union, edge, interior),
            }
        )
    return warnings


def _suggest(
    mask: Image.Image, union: Box, edge: str, interior: float
) -> list[float] | None:
    """The same box with one edge moved out until it is clear of ink."""
    box = list(union)
    index = {"left": 0, "top": 1, "right": 2, "bottom": 3}[edge]
    sign = -1 if edge in ("left", "top") else 1
    moved = 0.0
    while moved < SUGGEST_MAX:
        moved += SUGGEST_STEP
        value = min(1.0, max(0.0, union[index] + sign * moved))
        trial = list(box)
        trial[index] = value
        x0, y0, x1, y1 = trial
        band = {
            "left": (x0, y0, x0 + EDGE_BAND, y1),
            "right": (x1 - EDGE_BAND, y0, x1, y1),
            "top": (x0, y0, x1, y0 + EDGE_BAND),
            "bottom": (x0, y1 - EDGE_BAND, x1, y1),
        }[edge]
        if density(mask, band) / interior <= EDGE_RATIO:
            box[index] = value
            return [round(v, 3) for v in box]
        if value in (0.0, 1.0):
            break
    return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- command line -----------------------------------------------------------


def _box(text: str) -> Box:
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4 or not all(0 <= p <= 1 for p in parts):
        raise argparse.ArgumentTypeError("box is x0,y0,x1,y1 as fractions 0-1")
    x0, y0, x1, y1 = parts
    if x0 >= x1 or y0 >= y1:
        raise argparse.ArgumentTypeError("box needs x0 < x1 and y0 < y1")
    return x0, y0, x1, y1


def _column_box(text: str) -> tuple[int, Box]:
    number, _, box = text.partition("=")
    if not number.isdigit() or int(number) < 1 or not box:
        raise argparse.ArgumentTypeError("use N=x0,y0,x1,y1 (N is 1 or more)")
    return int(number), _box(box)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument(
        "--auto", action="store_true", help="Find the columns from the ink."
    )
    ap.add_argument("--box", type=_box, default=None, help="Region to cut into strips.")
    ap.add_argument(
        "--column-box",
        type=_column_box,
        action="append",
        default=[],
        help="N=x0,y0,x1,y1. Set column N yourself (repeatable).",
    )
    ap.add_argument(
        "--columns",
        type=int,
        default=None,
        help="Number of columns (strips with --box; expected count with --auto).",
    )
    ap.add_argument("--rows", type=int, default=1, help="Pieces per column.")
    ap.add_argument(
        "--overlap",
        type=float,
        default=0.03,
        help="Extra margin on each piece, as a fraction of the piece size.",
    )
    ap.add_argument("--max-side", type=int, default=1500)
    ap.add_argument("--prefix", default="crop")
    return ap


def plan_columns(args: argparse.Namespace, mask: Image.Image) -> tuple[str, list[Box]]:
    """Choose the column boxes for the mode in args."""
    if args.auto:
        if args.box is not None:
            raise SystemExit("error: --auto and --box cannot be used together")
        boxes = auto_columns(mask, args.columns)
        if not boxes:
            raise SystemExit(
                "error: no columns found. Use --column-box N=x0,y0,x1,y1 for each column."
            )
        for number, box in args.column_box:
            if number > len(boxes):
                raise SystemExit(
                    f"error: --column-box {number}, but --auto found {len(boxes)} columns"
                )
            boxes[number - 1] = box
        return "auto", boxes
    if args.column_box:
        if args.box is not None:
            raise SystemExit("error: --column-box and --box cannot be used together")
        numbers = sorted(n for n, _ in args.column_box)
        if numbers != list(range(1, len(numbers) + 1)):
            raise SystemExit(
                "error: --column-box numbers must be 1, 2, 3 ... with no gaps"
            )
        return "column-box", [b for _, b in sorted(args.column_box)]
    region = args.box or (0.0, 0.0, 1.0, 1.0)
    return "box", strip_columns(region, args.columns or 1)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.rows < 1 or (args.columns is not None and args.columns < 1):
        raise SystemExit("error: --rows and --columns must be 1 or more")

    im = Image.open(args.image)
    mask = ink_mask(im)
    mode, columns = plan_columns(args, mask)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[dict] = []
    if args.columns is not None and len(columns) != args.columns:
        warnings.append(
            {
                "kind": "column_count",
                "message": f"expected {args.columns} columns but the plan has {len(columns)}; "
                f"use --column-box N=x0,y0,x1,y1 for each column",
            }
        )

    manifest_columns = []
    for number, column in enumerate(columns, start=1):
        pieces = piece_boxes(column, im.size, args.rows, args.overlap)
        crops = []
        for row, box in enumerate(pieces, start=1):
            piece = im.crop(box)
            piece.thumbnail((args.max_side, args.max_side))
            dest = args.out_dir / f"{args.prefix}-c{number}-r{row}.jpg"
            piece.convert("RGB").save(dest, quality=90)
            crops.append(
                {"file": dest.name, "box": list(box), "sha256": sha256_file(dest)}
            )
            print(f"{dest}\t{box}")
        union = (
            pieces[0][0] / im.size[0],
            pieces[0][1] / im.size[1],
            pieces[0][2] / im.size[0],
            pieces[-1][3] / im.size[1],
        )
        warnings.extend(edge_warnings(mask, union, number))
        manifest_columns.append(
            {
                "column": number,
                "box": [round(v, 4) for v in column],
                "crops": crops,
            }
        )

    manifest = {
        "tool": "crop.py",
        "version": MANIFEST_VERSION,
        "created": datetime.now(timezone.utc).isoformat(),
        "image": str(args.image),
        "image_sha256": sha256_file(args.image),
        "image_size": list(im.size),
        "mode": mode,
        "expected_columns": args.columns,
        "rows": args.rows,
        "columns": manifest_columns,
        "warnings": warnings,
    }
    manifest_path = args.out_dir / "crops.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    for warning in warnings:
        line = f"WARNING: {warning['message']}"
        if warning.get("suggestion"):
            x0, y0, x1, y1 = warning["suggestion"]
            line += f" (try --column-box {warning['column']}={x0},{y0},{x1},{y1})"
        print(line, file=sys.stderr)
    print(f"manifest: {manifest_path} ({len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
