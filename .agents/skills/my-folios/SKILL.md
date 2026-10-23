---
name: my-folios
description: List the open folio issues that are assigned to you.
---

# My Folios

Show the folio sides that are assigned to the user and not yet closed.
Use the repo glossary in `AGENTS.md`.
This skill only reads. It does not change any issue.

## Steps

1. **Check `gh`.**
   Run `gh --version` and `gh auth status`.
   - Not installed or not logged in: do not run the script. Give the user this URL and tell them to open it while logged in to GitHub:
     <https://github.com/charlesLoder/leningrad-codex-tei/issues?q=is%3Aissue+state%3Aopen+label%3Afolio+assignee%3A%40me+sort%3Acreated-asc>
     Then stop.
   Completion: `gh` works, or the user has the URL.

2. **List the issues.**
   Run `.agents/skills/my-folios/scripts/my_folios.sh`.
   The script lists open issues with the `folio` label that are assigned to the current `gh` user, oldest first.
   A line ends with `[TEI exists in edition/]` when the folio file is already in `edition/`.
   Completion: you have the list.

3. **Report.**
   Show the list to the user.
   - Empty list: say that no folios are assigned. Offer `/find-folios` to ask for some.
   - Folios with a TEI file but an open issue: tell the user that the issue closes when the pull request merges. Offer `/folio-pr`.
   - Folios without a TEI file: these are the work left. Offer to align them, and ask which method the user wants:
     - **Harness (recommended if the user chose it in `/getting-started`):** use the `align-folio` skill with one subagent for each folio side. The `align-folio` skill says to do one folio side per session, because context from one folio can change the work on the next. A fresh subagent for each folio keeps the context apart. Give each subagent only its folio side (for example `001B`) and tell it to use the `align-folio` skill. Ask the user if the subagents may run in parallel or one at a time. When all subagents finish, report the `validate` result of each folio.
     - **Gemini:** `uv run --env-file .env leningrad align-folio --folio <FOLIO> --limit <LIMIT>`.
