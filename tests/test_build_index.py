"""Tests for the build-index stage."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from leningrad_codex_tei.stages.index import build_index

TEI = "http://www.tei-c.org/ns/1.0"


def _tei(folio: str, verse_range: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<TEI xmlns="{TEI}">'
        f"<teiHeader><fileDesc><titleStmt><title>{verse_range}</title></titleStmt></fileDesc></teiHeader>"
        f'<text><body><pb n="{folio}"/></body></text>'
        "</TEI>"
    )


def test_build_index_lists_each_folio(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "001B.xml").write_text(_tei("001B", "Genesis 1:1 – 2:2"), encoding="utf-8")
    (out / "002A.xml").write_text(_tei("002A", "Genesis 1:26 – 2:19"), encoding="utf-8")

    index_xml = build_index(out)
    root = etree.fromstring(index_xml.encode())

    assert root.tag.split("}", 1)[-1] == "index"
    entries = root.findall("entry")
    assert len(entries) == 2
    assert [(e.get("folio"), e.get("href")) for e in entries] == [
        ("001B", "001B.xml"),
        ("002A", "002A.xml"),
    ]
    titles = [e.findtext("title") for e in entries]
    assert titles == ["Genesis 1:1 – 2:2", "Genesis 1:26 – 2:19"]


def test_build_index_empty_dir(tmp_path: Path) -> None:
    out = tmp_path / "empty"
    out.mkdir()
    index_xml = build_index(out)
    root = etree.fromstring(index_xml.encode())
    assert root.findall("entry") == []


def test_build_index_records_edition_version(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "001B.xml").write_text(_tei("001B", "Genesis 1:1 – 2:2"), encoding="utf-8")

    root = etree.fromstring(build_index(out, "1.2.3").encode())
    app = root.find("appInfo/application")
    assert app.get("ident") == "leningrad-codex-tei"
    assert app.get("version") == "1.2.3"
    assert app.find("ptr").get("target").endswith("/releases/tag/v1.2.3")
    assert len(root.findall("entry")) == 1


def test_build_index_omits_app_info_without_version(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    assert etree.fromstring(build_index(out).encode()).find("appInfo") is None


def _tei_with_contributor(folio: str, verse_range: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<TEI xmlns="{TEI}">'
        "<teiHeader><fileDesc><titleStmt>"
        f"<title>{verse_range}</title>"
        '<respStmt xml:id="leningrad-codex-tei"><resp>created by</resp>'
        "<name>leningrad-codex-tei</name></respStmt>"
        '<respStmt xml:id="contrib-test-scribe">'
        "<resp>TEI encoding and alignment</resp>"
        '<persName ref="mailto:scribe@example.org">Test Scribe</persName>'
        "</respStmt></titleStmt></fileDesc>"
        "<revisionDesc>"
        '<change when="2026-09-12T00:00:01+00:00" who="#leningrad-codex-tei">'
        "Aligned folio.</change>"
        '<change when="2026-09-12T00:00:03+00:00" who="#contrib-test-scribe">'
        "Encoded by Test Scribe.</change>"
        "</revisionDesc></teiHeader>"
        f'<text><body><pb n="{folio}"/></body></text>'
        "</TEI>"
    )


def test_build_index_includes_contributor_and_date(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "001B.xml").write_text(
        _tei_with_contributor("001B", "Genesis 1:1 – 2:2"), encoding="utf-8"
    )
    (out / "002A.xml").write_text(_tei("002A", "Genesis 1:26 – 2:19"), encoding="utf-8")

    entries = etree.fromstring(build_index(out).encode()).findall("entry")
    assert entries[0].get("contributor") == "Test Scribe"
    assert entries[0].get("when") == "2026-09-12T00:00:03+00:00"
    assert entries[0].findtext("persName") == "Test Scribe"
    assert entries[0].find("persName").get("ref") == "mailto:scribe@example.org"
    assert entries[0].find("date").get("when") == "2026-09-12T00:00:03+00:00"
    # folio without a contributor keeps title/href and carries no names
    assert entries[1].get("contributor") is None
    assert entries[1].find("persName") is None
