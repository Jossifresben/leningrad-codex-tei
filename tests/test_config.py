"""Config loading."""

from __future__ import annotations

import tomllib
from pathlib import Path

from leningrad_codex_tei.config import load_config

ROOT = Path(__file__).parents[1]


def test_project_version_comes_from_pyproject():
    expected = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "version"
    ]
    assert load_config(ROOT / "config.yaml").project_version == expected
