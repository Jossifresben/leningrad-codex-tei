"""Tests for the download-uxlc stage."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from leningrad_codex_tei.config import Config
from leningrad_codex_tei.schemas import UxlcEdition
from leningrad_codex_tei.stages.uxlc import (
    check_uxlc_edition,
    download_uxlc,
    edition_uxlc_stamps,
)

UXLC_URL = "https://example.invalid/Books/Tanach.xml.zip"


def _make_zip(entries: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, data in (entries or {"Genesis.xml": b"<foo/>"}).items():
            archive.writestr(name, data)
    return buf.getvalue()


def test_download_uxlc_extracts_and_cleans_up(config: Config) -> None:
    payload = _make_zip()
    calls: list[str] = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        return payload

    info = download_uxlc(config, fetcher=fetcher)

    assert (config.paths.uxlc / "Genesis.xml").read_bytes() == b"<foo/>"
    assert not list(config.paths.uxlc.glob("*.zip"))
    assert info["zip_sha256"] == hashlib.sha256(payload).hexdigest()
    assert info["files"] == 1
    assert info["zip_removed"] is True
    assert calls == [UXLC_URL]


def test_download_uxlc_creates_dir(config: Config) -> None:
    config.paths.uxlc = config.paths.uxlc / "nested" / "uxlc"
    download_uxlc(config, fetcher=lambda url: _make_zip())
    assert config.paths.uxlc.is_dir()


def test_download_uxlc_skips_directories_and_non_xml(config: Config) -> None:
    payload = _make_zip(
        {
            "Genesis.xml": b"<a/>",
            "Exodus.xml": b"<b/>",
            "dir/Joshua.xml": b"<c/>",
            "README.txt": b"hi",
        }
    )
    info = download_uxlc(config, fetcher=lambda url: payload)

    assert (config.paths.uxlc / "Genesis.xml").read_bytes() == b"<a/>"
    assert (config.paths.uxlc / "Exodus.xml").exists()
    assert (config.paths.uxlc / "Joshua.xml").read_bytes() == b"<c/>"
    assert not (config.paths.uxlc / "README.txt").exists()
    assert not (config.paths.uxlc / "dir").exists()
    assert info["files"] == 3


def test_download_uxlc_rejects_non_zip(config: Config) -> None:
    with pytest.raises(ValueError, match="not a zip archive"):
        download_uxlc(config, fetcher=lambda url: b"{not a zip")

    assert not list(config.paths.uxlc.iterdir())


def test_download_uxlc_writes_to_explicit_out_dir(
    config: Config, tmp_path: Path
) -> None:
    out = tmp_path / "custom"
    download_uxlc(config, fetcher=lambda url: _make_zip(), out_dir=out)
    assert (out / "Genesis.xml").read_bytes() == b"<foo/>"


def _book(version: str, build: str) -> bytes:
    return (
        '<Tanach xmlns:t="x"><teiHeader><fileDesc><editionStmt><edition>'
        f"<version>{version}</version><build>{build}</build>"
        "</edition></editionStmt></fileDesc></teiHeader></Tanach>"
    ).encode()


def _write_folio(out_dir: Path, name: str, stamp: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.xml").write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt>'
        '<respStmt xml:id="source-uxlc"><resp>Base biblical text from the '
        f"Unicode/XML Leningrad Codex (UXLC) ({stamp}) "
        '<ptr target="https://example.invalid/"/></resp></respStmt>'
        "</titleStmt></fileDesc></teiHeader></TEI>",
        encoding="utf-8",
    )


def test_edition_uxlc_stamps_reads_folio_headers(config: Config) -> None:
    out = config.paths.output
    _write_folio(out, "001B", "version UXLC 2.5, build 27.6, 1 Apr 2026")
    _write_folio(out, "002A", "version UXLC 2.5")
    (out / "index.xml").write_text("<index/>", encoding="utf-8")

    assert edition_uxlc_stamps(out) == {("UXLC 2.5", "27.6"), ("UXLC 2.5", None)}


def test_download_uxlc_accepts_edition_version(config: Config) -> None:
    _write_folio(config.paths.output, "001B", "version UXLC 2.5, build 27.6")
    payload = _make_zip({"Books/Genesis.xml": _book("UXLC 2.5", "27.6")})

    info = download_uxlc(config, fetcher=lambda url: payload)

    assert (config.paths.uxlc / "Genesis.xml").exists()
    assert (info["version"], info["build"]) == ("UXLC 2.5", "27.6")


def test_download_uxlc_rejects_other_version(config: Config) -> None:
    _write_folio(config.paths.output, "001B", "version UXLC 2.5, build 27.6")
    payload = _make_zip({"Books/Genesis.xml": _book("UXLC 2.6", "27.7")})

    with pytest.raises(ValueError, match=r"UXLC 2\.6 \(build 27\.7\).*UXLC 2\.5"):
        download_uxlc(config, fetcher=lambda url: payload)

    assert not list(config.paths.uxlc.iterdir())


def test_download_uxlc_rejects_zip_without_version(config: Config) -> None:
    _write_folio(config.paths.output, "001B", "version UXLC 2.5, build 27.6")

    with pytest.raises(ValueError, match="UXLC is an unknown version"):
        download_uxlc(config, fetcher=lambda url: _make_zip())


def test_check_uxlc_edition_rejects_mixed_folios(config: Config) -> None:
    out = config.paths.output
    _write_folio(out, "001B", "version UXLC 2.5, build 27.6")
    _write_folio(out, "002A", "version UXLC 2.6, build 27.7")

    with pytest.raises(ValueError, match="mix UXLC versions"):
        check_uxlc_edition(UxlcEdition(version="UXLC 2.5", build="27.6"), out)


def test_check_uxlc_edition_ignores_build_when_unstamped(config: Config) -> None:
    _write_folio(config.paths.output, "001B", "version UXLC 2.5")
    check_uxlc_edition(
        UxlcEdition(version="UXLC 2.5", build="27.6"), config.paths.output
    )
