"""build-index stage: emit a minimal index over the generated folio TEI files."""

from __future__ import annotations

from pathlib import Path

from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
REPO_URL = "https://github.com/charlesLoder/leningrad-codex-tei"
XML_ID = "http://www.w3.org/XML/1998/namespace"


def _local(el: etree._Element) -> str:
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def _contributors_and_date(
    root_element: etree._Element,
) -> tuple[list[dict], str | None]:
    """Human contributors plus the contributor date from a folio TEI header.

    Contributors are ``titleStmt/respStmt`` entries other than the pipeline
    one and the static source credits (``source-*``); the date is the latest
    ``revisionDesc/change`` whose ``who``
    points at such a contributor, falling back to the latest change.
    """
    contributors: list[dict] = []
    for el in root_element.iter():
        if _local(el) != "respStmt":
            continue
        xml_id = el.get(f"{{{XML_ID}}}id")
        if not xml_id or xml_id == "leningrad-codex-tei":
            continue
        if xml_id.startswith("source-"):
            continue
        pers = next((c for c in el.iter() if _local(c) == "persName"), None)
        if pers is None:
            continue
        name = (pers.text or "").strip()
        ref = pers.get("ref", "")
        email = ref.removeprefix("mailto:") if ref.startswith("mailto:") else None
        if not name:
            continue
        contributors.append({"name": name, "email": email, "xml_id": xml_id})

    contrib_ids = {c["xml_id"] for c in contributors}
    latest: str | None = None
    latest_any: str | None = None
    for el in root_element.iter():
        if _local(el) != "change":
            continue
        when = el.get("when")
        if not when:
            continue
        if latest_any is None or when > latest_any:
            latest_any = when
        who = (el.get("who") or "").lstrip("#")
        if who in contrib_ids and (latest is None or when > latest):
            latest = when
    return contributors, latest or latest_any


def build_index(output_dir: Path, version: str | None = None) -> str:
    """Scan ``output_dir/*.xml`` (excluding index.xml) and produce the index.

    ``version`` is the edition version; when given, the index opens with an
    ``appInfo/application`` naming it and pointing at its release tag.
    """
    root = etree.Element("index")
    if version:
        app_info = etree.SubElement(root, "appInfo")
        app = etree.SubElement(app_info, "application")
        app.set("ident", "leningrad-codex-tei")
        app.set("version", version)
        etree.SubElement(app, "label").text = "Leningrad Codex TEI"
        ptr = etree.SubElement(app, "ptr")
        ptr.set("type", "release")
        ptr.set("target", f"{REPO_URL}/releases/tag/v{version}")
    for path in sorted(output_dir.glob("*.xml")):
        if path.stem == "index":
            continue
        tree = etree.parse(str(path))
        root_element = tree.getroot()
        folio: str = path.stem
        pb = next((el for el in root_element.iter() if _local(el) == "pb"), None)
        if pb is not None:
            n = pb.get("n")
            if n:
                folio = n
        title = next(
            (
                el.text or ""
                for el in root_element.iter()
                if _local(el) == "title" and el.text
            ),
            "folio",
        )
        contributors, when = _contributors_and_date(root_element)
        entry = etree.SubElement(root, "entry")
        entry.set("folio", folio)
        entry.set("href", path.name)
        if when:
            entry.set("when", when)
        if contributors:
            entry.set("contributor", contributors[0]["name"])
        title_el = etree.SubElement(entry, "title")
        title_el.text = title
        for contrib in contributors:
            pers_el = etree.SubElement(entry, "persName")
            pers_el.text = contrib["name"]
            if contrib["email"]:
                pers_el.set("ref", f"mailto:{contrib['email']}")
        if when:
            date_el = etree.SubElement(entry, "date")
            date_el.set("when", when)
    return etree.tostring(root, pretty_print=True, encoding="unicode")
