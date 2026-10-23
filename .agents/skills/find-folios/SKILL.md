---
name: find-folios
description: Find open, unassigned folio issues and ask the repo owner to assign them to you.
---

# Find Folios

Find folio sides that still need to be aligned, and ask the repo owner to assign them to the user.
Use the repo glossary in `AGENTS.md`.

## Rules

- Do not comment on any issue until the user has seen the list and agreed.
- Do not change the script's repo or comment text without asking.

## Steps

1. **Check `gh`.**
   Run `gh --version` and `gh auth status`.
   - Not installed or not logged in: do not run the script. Give the user this URL and tell them to tag @charlesLoder in a comment on each issue they want:
     <https://github.com/charlesLoder/leningrad-codex-tei/issues?q=is%3Aissue+state%3Aopen+label%3Afolio+sort%3Acreated-asc>
     Then stop.
   Completion: `gh` works, or the user has the URL.

2. **Ask how many folios.**
   Ask the user how many folios they want to align. Call the answer `<N>`. It must be a whole number of 1 or more.
   Tell them that a contiguous set is easiest.
   Completion: you have `<N>`.

3. **List the issues.**
   Run `.agents/skills/find-folios/scripts/claim_folios.sh <N>`.
   The script lists the `<N>` oldest open issues with the `folio` label and no assignee. It changes nothing.
   Show the list to the user. If fewer than `<N>` issues come back, say so.
   Completion: the user has seen the list.

4. **Ask to comment.**
   Ask the user if you may comment on each listed issue. The comment tags the repo owner and says the user would like the issue assigned to them.
   - Yes: run `.agents/skills/find-folios/scripts/claim_folios.sh <N> --comment`.
   - No: stop.
   Completion: every listed issue has a comment, or the user declined.

5. **Report.**
   Tell the user which issues got a comment. Say that the owner must assign the issues, and that they should wait for the assignment before they start.
   When the issues are assigned, the `my-folios` skill shows them and offers to align them.
