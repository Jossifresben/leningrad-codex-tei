"""download-uxlc stage: fetch the UXLC book archive, extract its XML, and clean up."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from lxml import etree

from leningrad_codex_tei.config import Config
from leningrad_codex_tei.schemas import UxlcEdition
from leningrad_codex_tei.stages.word_stream import edition_from_xml
from leningrad_codex_tei.util import net

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

# the stamp tei_header.xml.j2 writes, e.g. "(version UXLC 2.5, build 27.6, 1 Apr 2026)"
_STAMP = re.compile(r"\(version ([^,)]+)(?:, build ([^,)]+))?")


def edition_uxlc_stamps(output_dir: Path) -> set[tuple[str, str | None]]:
    """UXLC (version, build) pairs stamped in the folio headers under ``output_dir``."""
    stamps: set[tuple[str, str | None]] = set()
    for path in sorted(output_dir.glob("*.xml")):
        if path.name == "index.xml":
            continue
        root = etree.parse(str(path)).getroot()
        for resp in root.iter(f"{{{TEI_NS}}}respStmt"):
            if resp.get(XML_ID) != "source-uxlc":
                continue
            match = _STAMP.search("".join(resp.itertext()))
            if match:
                stamps.add((match.group(1).strip(), match.group(2)))
    return stamps


def _label(version: str | None, build: str | None) -> str:
    if version is None:
        return "an unknown version"
    return f"{version} (build {build})" if build else version


def check_uxlc_edition(edition: UxlcEdition | None, output_dir: Path) -> None:
    """Raise when ``edition`` is not the UXLC version the existing folios were made from.

    No folios in ``output_dir`` means there is nothing to match, so any version passes.
    """
    stamps = edition_uxlc_stamps(output_dir)
    if not stamps:
        return
    if len(stamps) > 1:
        found = ", ".join(_label(*s) for s in sorted(stamps, key=str))
        raise ValueError(f"the folios in {output_dir} mix UXLC versions: {found}")
    version, build = next(iter(stamps))
    got_version = edition.version if edition else None
    got_build = edition.build if edition else None
    if got_version != version or (build is not None and got_build != build):
        raise ValueError(
            f"UXLC is {_label(got_version, got_build)}, but the folios in "
            f"{output_dir} were made from {_label(version, build)}; "
            "check uxlc.download_url in the config, then run download-uxlc"
        )


def download_uxlc(config: Config, fetcher=None, out_dir: Path | None = None) -> dict:
    """Fetch the UXLC zip, extract its XML books into ``paths.uxlc``, then delete the zip.

    Nothing is extracted when the zip's UXLC version differs from the edition's.
    """
    url = config.uxlc.download_url
    dest_dir = (out_dir or config.paths.uxlc).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    data = (fetcher or net.fetch_url)(url)
    zip_name = Path(urlparse(url).path).name or "uxlc.zip"
    zip_path = dest_dir / zip_name
    zip_path.write_bytes(data)
    sha256 = hashlib.sha256(data).hexdigest()

    if not zipfile.is_zipfile(zip_path):
        zip_path.unlink(missing_ok=True)
        raise ValueError(f"downloaded UXLC payload at {url} is not a zip archive")

    with zipfile.ZipFile(zip_path) as archive:
        books = [
            m
            for m in archive.infolist()
            if not m.is_dir() and Path(m.filename).name.endswith(".xml")
        ]
        edition = next(
            (
                e
                for e in (edition_from_xml(archive.read(m)) for m in books)
                if e is not None
            ),
            None,
        )
        try:
            check_uxlc_edition(edition, config.paths.output)
        except ValueError:
            zip_path.unlink(missing_ok=True)
            raise
        for member in books:
            (dest_dir / Path(member.filename).name).write_bytes(archive.read(member))

    zip_path.unlink(missing_ok=True)

    return {
        "url": url,
        "path": str(dest_dir),
        "files": len(books),
        "zip_sha256": sha256,
        "zip_removed": True,
        "version": edition.version if edition else None,
        "build": edition.build if edition else None,
    }
