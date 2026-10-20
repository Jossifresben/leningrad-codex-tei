---
name: update-revisiondesc
description: Add a new change entry to the top of the revisionDesc of existing TEI folio documents in edition/.
---

# Update revisionDesc

Record a hand edit to one or more existing folio documents in
`edition/`. The script adds one new `<change>` as the first child of
`<revisionDesc>` (most recent first) and keeps the rest of the file
unchanged.

Use the repo glossary in `AGENTS.md`: a **folio side** is `Fxxx{A|B}`,
one TEI document per side under `edition/`.

Do not run `generate-tei` to do this. It drops hand edits.

## Steps

1. **Get the folio sides.**
   Use the folio sides the user named. When the user did not name them,
   use the changed files in `git status --short -- edition/`
   (skip `edition/index.xml`). When the list is still empty, ask the user.
   Completion: a list of `edition/NNN{A|B}.xml` files that exist.

2. **Get the change text.**
   Use the text the user gave. Else write one or two short sentences
   from the diff (`git diff -- edition/<folio>.xml`) and show it to the user.
   Completion: one short description of the edit.

3. **Find the contributor.**
   Run `git config user.name` and `git config user.email`.
   When both are empty, ask the user for a name (and optional email),
   then pass `--name` / `--email` in step 4.
   Completion: a contributor name is known.

4. **Do a dry run.**
   ```bash
   python3 .agents/skills/update-revisionDesc/scripts/add_change.py \
     --desc "<text>" --dry-run 001B 002A
   ```
   The date is today in `YYYY-MM-DD`. The `who` is
   `#contrib-<slug of name>` (same rule as the pipeline, e.g.
   `#contrib-charles-w-loder`). When the file has no `respStmt` with
   that id, the script adds one, and prints `added respStmt`.
   Tell the user when this occurs.
   Completion: the output shows the new `<change>` at the top and no errors.

5. **Write the change.**
   Run the same command without `--dry-run`.
   Then check with `git diff -- edition/<folio>.xml`.
   Completion: each diff adds only the new `<change>` (and a new
   `respStmt` when step 4 said so). The script exits 0.

## Notes

- Options: `--when YYYY-MM-DD` (other date), `--name`, `--email`,
  `--resp` (text for a new `respStmt`, default `TEI revision`).
- The script parses the result before it writes. A file that is not
  well-formed is not written, and the script exits 1.
- The script uses only the standard library. No new packages.
- Do not commit unless the user asks.
