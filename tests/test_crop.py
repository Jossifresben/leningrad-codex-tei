"""Tests for the align-folio skill's crop.py, on a synthetic page."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

CROP_PY = (
    Path(__file__).parents[1]
    / ".agents"
    / "skills"
    / "align-folio"
    / "scripts"
    / "crop.py"
)
spec = importlib.util.spec_from_file_location("align_folio_crop", CROP_PY)
crop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crop)

W, H = 1200, 1500
# x ranges of three columns, left to right, as fractions of the page width
COLUMNS = [(0.15, 0.35), (0.40, 0.60), (0.65, 0.85)]
TOP, BOTTOM, LINES = 0.15, 0.80, 24


@pytest.fixture
def page(tmp_path: Path) -> Path:
    """Light page, three columns of ink lines with ragged left ends."""
    im = Image.new("RGB", (W, H), (235, 225, 210))
    draw = ImageDraw.Draw(im)
    step = (BOTTOM - TOP) * H / LINES
    for x0, x1 in COLUMNS:
        for i in range(LINES):
            y = TOP * H + i * step
            ragged = (i % 5) * 0.004 * W  # some lines run further left
            draw.rectangle(
                [x0 * W - ragged, y, x1 * W, y + step * 0.55], fill=(0, 0, 0)
            )
    path = tmp_path / "page.jpg"
    im.save(path, quality=100, subsampling=0)
    return path


def run(capsys, *argv: str) -> tuple[dict, str]:
    assert crop.main([str(a) for a in argv]) == 0
    err = capsys.readouterr().err
    out_dir = Path(argv[argv.index("--out-dir") + 1])
    return json.loads((out_dir / "crops.json").read_text()), err


def test_auto_finds_the_columns(page: Path, tmp_path: Path, capsys) -> None:
    out = tmp_path / "work"
    m, err = run(
        capsys, page, "--out-dir", out, "--auto", "--columns", "3", "--rows", "2"
    )
    assert m["tool"] == "crop.py"
    assert m["image_sha256"] == hashlib.sha256(page.read_bytes()).hexdigest()
    assert m["warnings"] == [], err
    assert len(m["columns"]) == 3
    # c1 is the rightmost column, and every box holds its whole column
    for number, (x0, x1) in enumerate(reversed(COLUMNS), start=1):
        box = m["columns"][number - 1]["box"]
        assert box[0] <= x0 and box[2] >= x1, (number, box)
        assert box[1] <= TOP and box[3] >= BOTTOM
        assert len(m["columns"][number - 1]["crops"]) == 2
    for column in m["columns"]:
        for item in column["crops"]:
            assert (
                hashlib.sha256((out / item["file"]).read_bytes()).hexdigest()
                == item["sha256"]
            )


def test_tight_box_warns_about_cut_off_text(page: Path, tmp_path: Path, capsys) -> None:
    # the right edge of the box runs through the right column
    m, err = run(
        capsys,
        page,
        "--out-dir",
        tmp_path / "w",
        "--box",
        "0.10,0.17,0.78,0.80",
        "--columns",
        "3",
    )
    kinds = {(w["column"], w["edge"]) for w in m["warnings"] if w["kind"] == "edge_ink"}
    assert (1, "left") in kinds or (1, "right") in kinds
    assert (1, "top") in kinds  # the first line starts above y=0.17
    assert "WARNING" in err and "text may be cut off" in err


def test_warning_suggests_a_wider_box(page: Path, tmp_path: Path, capsys) -> None:
    m, _ = run(
        capsys,
        page,
        "--out-dir",
        tmp_path / "w",
        "--column-box",
        "1=0.60,0.10,0.80,0.80",  # ends 0.05 short of the column on the right
    )
    warning = next(w for w in m["warnings"] if w["edge"] == "right")
    assert warning["suggestion"] is not None
    assert warning["suggestion"][2] >= 0.85


def test_column_box_replaces_one_auto_column(
    page: Path, tmp_path: Path, capsys
) -> None:
    box = "0.30,0.10,0.62,0.85"
    m, _ = run(
        capsys,
        page,
        "--out-dir",
        tmp_path / "w",
        "--auto",
        "--columns",
        "3",
        "--column-box",
        f"2={box}",
    )
    assert m["columns"][1]["box"] == [0.3, 0.1, 0.62, 0.85]
    assert m["columns"][0]["box"][0] <= 0.65  # c1 was still found by --auto


def test_columns_mismatch_is_a_warning(page: Path, tmp_path: Path, capsys) -> None:
    m, _ = run(capsys, page, "--out-dir", tmp_path / "w", "--auto", "--columns", "2")
    assert any(w["kind"] == "column_count" for w in m["warnings"])


def test_blank_page_has_no_columns(tmp_path: Path) -> None:
    blank = tmp_path / "blank.jpg"
    Image.new("RGB", (400, 500), (235, 225, 210)).save(blank)
    with pytest.raises(SystemExit):
        crop.main([str(blank), "--out-dir", str(tmp_path / "w"), "--auto"])
