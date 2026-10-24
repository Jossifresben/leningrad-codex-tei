---
name: commit-folios
description: Turn aligned folio sides into committed TEI documents on a working branch. Runs validate, generate-tei, and ruff format, then commits. Run it after align-folio and before folio-pr.
---

# Commit Folios

Take folio sides that are aligned and make a commit of their TEI documents in `edition/`.
Use the repo glossary in `AGENTS.md`: a **folio side** is `Fxxx{A|B}`, one TEI document per side.

The argument is one or more folio sides, for example `001B 002A 002B`. If none is given, ask the user. Do not guess.

## Rules

- Always pass `--folio` to `generate-tei`, one side at a time. Never run `generate-tei` without `--folio` or `--start-folio`. It rewrites a file from the alignment data and drops hand edits and `revisionDesc` entries.
- Never run `generate-tei` for a folio that already has a committed file in `edition/` on `main`. Those files are the source of truth. Tell the user and skip that folio.
- Do not push. `folio-pr` does that.
- Ask the user before you commit.

## Steps

0. **Check for changes on `main`.**
   Find the remote that points to `charlesLoder/leningrad-codex-tei` (`git remote -v`; usually `origin`, or `upstream` in a fork). Then run:
   ```sh
   git fetch <remote> main
   git log --oneline HEAD..<remote>/main
   ```
   - No output: continue to step 1.
   - Commits listed: show them and ask the user if they want to pull them in.
     - Yes, on `main`: `git pull --ff-only <remote> main`
     - Yes, on another branch: `git merge <remote>/main`. If a merge conflict occurs, stop and tell the user. Do not resolve it here.
     - No: continue to step 1.
   - If the commits change this skill, check with `git diff --name-only HEAD..<remote>/main -- .agents/skills/commit-folios`. If it lists a path, tell the user that they may need to restart their harness (agent session) to make the updated skill discoverable. The steps below may be out of date until they do. Ask if they want to stop here.
   Completion: the user chose to pull or not, and you told them about any skill change.

1. **Check the branch.**
   Run `git branch --show-current`.
   - On `main` (or detached): make a working branch. Name it `folios/<FIRST>-<LAST>` (for example `folios/001B-003A`) and ask the user to confirm the name. Run `git switch -c <name>`.
   - On another branch: continue on it.
   Completion: you are on a branch that is not `main`.

2. **Check the folios are aligned.**
   For each side, run `uv run leningrad validate --folio <FOLIO>`.
   - A side that does not pass: report it and remove it from the list. Do not fix the alignment here. Point the user to `align-folio` or to the "Handling errors with inference output" section of `CONTRIBUTING.MD`.
   - If the list is now empty, stop.
   Completion: every side left in the list passes `validate`.

3. **Check the git identity.**
   The TEI header takes the contributor from `git config user.name` and `git config user.email`. Show both values. If one is empty, stop and tell the user to set it (the `getting-started` skill has a step for this).
   Completion: both values are set.

4. **Generate the TEI documents.**
   For each side, one at a time:
   `uv run leningrad generate-tei --folio <FOLIO>`
   Completion: `edition/<FOLIO>.xml` exists for every side.

5. **Format.**
   Run `uv run ruff format`.
   Completion: the command ends without an error.

6. **Review the change.**
   Run `git status --short` and `git diff --stat`.
   Only the new `edition/<FOLIO>.xml` files may change. If any other path changed (for example an older folio file), stop and tell the user. Do not commit.
   Completion: the changes match the list of sides.

7. **Commit.**
   Show the list of sides and ask the user to confirm. Then stage only the paths from step 6 and commit. The message names the range, in the same style as the project history:
   - One side: `add folio 099A`
   - More than one: `add folios 092A to 098B`
   Completion: `git log -1 --stat` shows the new commit.

8. **Hand off.**
   Tell the user the folios are committed on branch `<name>`. Offer the `folio-pr` skill to open the pull request.
