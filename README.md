# UXLC 2.5 mirror

This branch holds a copy of the Unicode/XML Leningrad Codex (UXLC), version 2.5, build 27.6 (1 Apr 2026).
It is not part of the edition. It is the base text that the [Leningrad Codex TEI](https://github.com/charlesLoder/leningrad-codex-tei) edition was made from.

## Why this branch exists

[tanach.us](https://www.tanach.us) serves only the current UXLC release at one URL (`Books/Tanach.xml.zip`).
On 18 Oct 2026, that URL changed to UXLC 2.6.
The edition uses UXLC 2.5, so the pipeline cannot get its base text from tanach.us anymore.

The pipeline's `download-uxlc` step gets `Tanach-2.5.xml.zip` from this branch.
The URL in the pipeline's `config.yaml` names a commit of this branch, so the file it gets does not change.

## Contents

`Tanach-2.5.xml.zip` holds 44 files in `Books/`:

- the 39 book XMLs (e.g. `Books/Genesis.xml`)
- the 5 Documentary Hypothesis variants (e.g. `Books/Genesis.DH.xml`)

Each XML file is the file as the pipeline's `download-uxlc` step extracted it from the tanach.us `Tanach.xml.zip` of UXLC 2.5 (build 27.6), with no changes.
Each file's `teiHeader/fileDesc/editionStmt/edition` says `UXLC 2.5`, build `27.6`.

The zip itself is not the tanach.us zip.
The original zip was deleted after extraction, so this zip was made again from the extracted files.
It does not include these files from the original zip, because the pipeline does not use them and the license does not cover them:

- `Books/TanachHeader.xml` and `Books/TanachIndex.xml`
- `License.html`, `Pages/`, and `Images/`

sha256 of the zip:

```
25b22c0484b14eab04868494efa774ea568f778c3fcd4254f6b68ec9065c2fca  Tanach-2.5.xml.zip
```

## License and citation

The tanach.us [license](https://www.tanach.us/License.html) says:

> All biblical Hebrew text, in any format, may be viewed or copied without restriction.

The tanach.us site asks for this citation:

> Unicode/XML Leningrad Codex: UXLC 2.5 (27.6), Tanach.us Inc., West Redding, CT, USA, Apr 2026.

The UXLC is not the Westminster Leningrad Codex (WLC). Do not represent it as such.

## Do not change this branch

Do not change `Tanach-2.5.xml.zip`.
For a new UXLC version, add a new file (e.g. `Tanach-2.6.xml.zip`) and update this README.
