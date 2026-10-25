---
name: find-folios
description: Find open, unassigned folio issues and claim them for you.
---

# Find Folios

Find folio sides that still need to be aligned, and claim them for the user.
Use the repo glossary in `AGENTS.md`.

A comment of `/claim` on an open folio issue assigns the issue to the commenter.
The `claim-folio` workflow does this. It refuses an issue that has an assignee, and it refuses a user who already holds 50 open folio issues (per `.github/workflows/claim-folio.yml`).
A comment of `/unclaim` removes the commenter from the issue.

## Rules

- Do not comment on any issue until the user has seen the list and agreed.
- Do not change the script's repo or comment text without asking.

## Steps

1. **Check `gh`.**
   Run `gh --version` and `gh auth status`.
   - Not installed or not logged in: do not run the script. Give the user this URL and tell them to comment `/claim` on each issue they want:
     <https://github.com/charlesLoder/leningrad-codex-tei/issues?q=is%3Aissue+state%3Aopen+label%3Afolio+no%3Aassignee+sort%3Acreated-asc>
     Then stop.
   Completion: `gh` works, or the user has the URL.

2. **Ask how many folios.**
   Ask the user how many folios they want to align. Call the answer `<N>`.
   It must be a whole number. Generally, 10 is a good number in case model outputs need to be reviewed
   Tell them that a contiguous set is easiest.
   Completion: you have `<N>`.

3. **List the issues.**
   Run `.agents/skills/find-folios/scripts/claim_folios.sh <N>`.
   The script lists the `<N>` oldest open issues with the `folio` label and no assignee. It changes nothing.
   Show the list to the user. If fewer than `<N>` issues come back, say so.
   Completion: the user has seen the list.

4. **Ask to claim.**
   Ask the user if you may comment `/claim` on each listed issue.
   - Yes: run `.agents/skills/find-folios/scripts/claim_folios.sh <N> --claim`.
     The script comments, then waits up to 2 minutes for the workflow. It prints one line for each issue:
     - `ASSIGNED`: the issue is now the user's.
     - `TAKEN`: another user claimed it first.
     - `NO CHANGE`: the workflow did not assign it. The workflow replies on the issue with the cause (for example, the claim limit).
   - No: stop.
   Completion: the script has reported every listed issue, or the user declined.

5. **Report.**
   Tell the user which issues are assigned to them, and which are not.
   If an issue is `TAKEN`, offer to run the skill again for more issues.
   The user can start on assigned issues now. The `my-folios` skill shows them and offers to align them.
