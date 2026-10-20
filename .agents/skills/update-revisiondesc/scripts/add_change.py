"""Add a new <change> to the top of the revisionDesc of edition TEI files.

The contributor comes from git config (user.name / user.email), the same
source the pipeline uses, unless --name / --email are given. The `who`
id uses the same rule as `contributor_xml_id` in stages/tei.py
(e.g. "Charles W. Loder" -> "#contrib-charles-w-loder").

When the file has no respStmt for that id, the script adds one after the
last respStmt in titleStmt, so the `who` pointer always resolves.

The script edits the text in place (no XML re-serialization), so the
rest of the file keeps its exact layout. It then parses the result to
check that it is well-formed before it writes.

Usage:
    python3 add_change.py --desc "Fix word split on line 3." 001B 002A
    python3 add_change.py --desc "..." edition/001B.xml --dry-run
    python3 add_change.py --desc "..." --name "Jane Doe" --email jane@x.org 001B
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

EDITION_DIR = Path("edition")
FOLIO_RE = re.compile(r"^\d{3}[AB]$")
REVISION_OPEN_RE = re.compile(r"^([ \t]*)<revisionDesc>[ \t]*\n", re.M)
FIRST_CHANGE_RE = re.compile(r"^([ \t]*)<change\b", re.M)
RESP_STMT_RE = re.compile(r"^([ \t]*)<respStmt\b.*?</respStmt>[ \t]*\n", re.M | re.S)


def git_config(key: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "config", key], capture_output=True, text=True, timeout=10
        )
    except Exception:
        return None
    value = proc.stdout.strip()
    return value if proc.returncode == 0 and value else None


def contributor_xml_id(name: str | None, email: str | None) -> str:
    """Same rule as stages/tei.py `contributor_xml_id`."""
    base = re.sub(r"[^a-z0-9]+", "-", (name or email or "contributor").lower()).strip(
        "-"
    )
    return f"contrib-{base}" if base else "contrib-unknown"


def resolve_path(arg: str) -> Path:
    if FOLIO_RE.match(arg):
        return EDITION_DIR / f"{arg}.xml"
    return Path(arg)


def add_resp_stmt(text: str, xml_id: str, name: str, email: str | None, resp: str) -> str:
    stmts = list(RESP_STMT_RE.finditer(text))
    if not stmts:
        raise ValueError("no respStmt found; cannot add contributor")
    last = stmts[-1]
    indent = last.group(1)
    ref = f" ref={quoteattr('mailto:' + email)}" if email else ""
    block = (
        f'{indent}<respStmt xml:id="{xml_id}">\n'
        f"{indent}  <resp>{escape(resp)}</resp>\n"
        f"{indent}  <persName{ref}>{escape(name)}</persName>\n"
        f"{indent}</respStmt>\n"
    )
    return text[: last.end()] + block + text[last.end() :]


def add_change(text: str, when: str, xml_id: str, desc: str) -> str:
    opener = REVISION_OPEN_RE.search(text)
    if opener is None:
        raise ValueError("no <revisionDesc> found")
    first = FIRST_CHANGE_RE.search(text, opener.end())
    indent = first.group(1) if first else opener.group(1) + "  "
    block = (
        f'{indent}<change when="{when}" who="#{xml_id}">\n'
        f"{indent}{escape(desc)}\n"
        f"{indent}</change>\n"
    )
    return text[: opener.end()] + block + text[opener.end() :]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", help="folio ids (001B) or TEI file paths")
    parser.add_argument("--desc", required=True, help="text of the new change")
    parser.add_argument("--when", help="date (default: today, YYYY-MM-DD)")
    parser.add_argument("--name", help="contributor name (default: git user.name)")
    parser.add_argument("--email", help="contributor email (default: git user.email)")
    parser.add_argument(
        "--resp",
        default="TEI revision",
        help="resp text when a new respStmt is added",
    )
    parser.add_argument("--dry-run", action="store_true", help="print, do not write")
    args = parser.parse_args()

    desc = " ".join(args.desc.split())
    if not desc:
        print("error: --desc is empty", file=sys.stderr)
        return 2

    when = args.when or dt.date.today().isoformat()
    try:
        dt.date.fromisoformat(when)
    except ValueError:
        print(f"error: --when must be YYYY-MM-DD, got {when!r}", file=sys.stderr)
        return 2

    name = args.name or git_config("user.name")
    email = args.email or git_config("user.email")
    if not name and not email:
        print(
            "error: no contributor; set git user.name or pass --name",
            file=sys.stderr,
        )
        return 2
    xml_id = contributor_xml_id(name, email)

    failed = 0
    for arg in args.files:
        path = resolve_path(arg)
        try:
            text = path.read_text(encoding="utf-8")
            if f'xml:id="{xml_id}"' not in text:
                text = add_resp_stmt(text, xml_id, name or email, email, args.resp)
                print(f"{path}: added respStmt {xml_id}")
            text = add_change(text, when, xml_id, desc)
            ET.fromstring(text.encode("utf-8"))
        except (OSError, ValueError, ET.ParseError) as exc:
            print(f"{path}: error: {exc}", file=sys.stderr)
            failed += 1
            continue
        if args.dry_run:
            start = text.index("<revisionDesc>")
            print(f"--- {path} (dry run)\n{text[start : start + 400]}")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"{path}: added change when={when} who=#{xml_id}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
