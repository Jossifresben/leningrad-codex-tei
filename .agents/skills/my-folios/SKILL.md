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
   Run `git fetch origin main`, then `.agents/skills/my-folios/scripts/my_folios.sh`.
   The script lists open issues with the `folio` label that are assigned to the current `gh` user, oldest first.
   A line can end with a status:
   - `[on main]`: the TEI file is already merged. The issue is probably stale.
   - `[committed on branch]`: committed, but not yet in a pull request that is merged.
   - `[generated, not committed]`: the file is in `edition/` but not in a commit.
   - No status: the folio is not aligned yet.
   Completion: you have the list.

3. **Report.**
   Show the list to the user. Then offer the next step for the first group that applies, in this order:
   - Empty list: say that no folios are assigned. Offer the `find-folios` skill to claim some.
   - `[on main]`: tell the user the issue is open but the file is merged. Ask them to check the issue. Do not do more for these folios.
   - `[committed on branch]`: offer the `folio-pr` skill to open the pull request. The issue closes when the pull request merges.
   - `[generated, not committed]`: offer the `commit-folios` skill.
   - No status (not aligned): these are the work left. Offer to align them, and ask which method the user wants:
     - **Harness (recommended if the user chose it in `getting-started`):** use the `align-folio` skill with one subagent for each folio side. The `align-folio` skill says to do one folio side per session, because context from one folio can change the work on the next. A fresh subagent for each folio keeps the context apart. Before you start the subagents, make sure that each folio side has a task packet in `{alignments}/tasks/{folio}/`. If a packet is missing, run `uv run leningrad prepare-folio --folio <FOLIO> --limit <LIMIT>` first. Without a packet, the `align-folio` skill stops at step 1. Give each subagent only its folio side (for example `001B`) and tell it to use the `align-folio` skill. Tell each subagent to end with its notes from "Reporting model output" in the `align-folio` skill, so you can collect them. Tell each subagent to put its helper scripts and temporary files only in its own folder, `{alignments}/tasks/{folio}/work/`, and not in a shared scratchpad. Subagents that run in parallel share one scratchpad, so a file with the same name (for example `build.py`) can be written over by a different subagent. Ask the user if the subagents may run in parallel or one at a time. When all subagents finish, report the `validate` result of each folio. Then summarize the notes from all subagents in two groups: items that need human review, and review notes. Ask the user if they want to review any of them before you continue (for example, to look at the folio image for a column with an unexpected line count or update the raw output). Help with the review if they say yes. Then offer the `commit-folios` skill with the folios that passed. Keep the notes, because the `folio-pr` skill puts them in the pull request body.
     - **Gemini:** `uv run --env-file .env leningrad align-folio --folio <FOLIO> --limit <LIMIT>`. After `parse-raw` and `validate` pass, offer the `commit-folios` skill.
