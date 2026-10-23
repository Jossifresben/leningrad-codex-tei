---
name: folio-pr
description: Ship committed folio TEI documents as a PR that closes each folio issue. Works from a fork or from a clone with write access.
---

# Folio PR

Ship a branch of committed folio sides as one pull request that closes each folio's issue.
Run `commit-folios` first. This skill needs the folio sides to be committed already.

Use the repo glossary in `AGENTS.md`: a **folio side** is `Fxxx{A|B}`, one TEI document per side under `edition/`.

`REPO` is `charlesLoder/leningrad-codex-tei`. Always pass `-R $REPO` to `gh` commands that read or write issues and pull requests, so a fork does not change the target.

## Rules

- Ask the user before you push and before you create the pull request. Both are public.
- Do not push to `main`.

## Steps

1. **Check the branch and the working tree.**
   Run `git branch --show-current` and `git status --short`.
   - On `main`: stop. Tell the user to run `commit-folios`, which makes a working branch.
   - Uncommitted changes in `edition/`: stop. Tell the user to run `commit-folios`.
   Completion: you are on a branch that is not `main`, and `edition/` is clean.

2. **Collect the committed folio sides.**
   Run `git fetch origin main`. Then:
   `git diff --name-only origin/main...HEAD -- edition/ | grep -oE '[0-9]{3}[AB]' | sort -u`
   Completion: every `edition/XXXX.xml` side on the branch is listed, sorted, with no extras. `index.xml` is not a side. If the list is empty, stop.

3. **Resolve each side to its issue number.**
   For each side `$FOLIO` (e.g. `001B`), run:
   `gh issue list -R $REPO --state open --search "$FOLIO in:title" --json number,title,assignees --limit 5`
   Keep only hits whose title starts with `Folio $FOLIO` (e.g. `Folio 001B: create TEI document`).
   Discard any other title that merely mentions the side (e.g. `Damaged line in 072A`).
   Expect exactly one kept hit of the form `Folio XXXX: create TEI document`.
   Check the assignee against `gh api user --jq .login`. If the issue is assigned to someone else, or to no one, warn the user and ask whether to continue with that side.
   Completion: every side has exactly one `#N` with a `Folio XXX[A|B]`-prefixed title; any `NOT FOUND`, duplicate or assignee warning is reported before continuing.

4. **Choose where to push.**
   Run `gh repo view $REPO --json viewerPermission --jq .viewerPermission`.
   - `WRITE`, `MAINTAIN` or `ADMIN`: the user can push to `origin`. Set `PUSH_REMOTE=origin` and `HEAD_REF=<branch>`.
   - Anything else (`READ`, `TRIAGE`): the user needs a fork. Tell the user. If the fork does not exist, ask to create it with `gh repo fork $REPO --clone=false --remote --remote-name fork`. Set `PUSH_REMOTE=fork` and `HEAD_REF=<login>:<branch>`, where `<login>` is from `gh api user --jq .login`.
   Completion: you know `PUSH_REMOTE` and `HEAD_REF`.

5. **Push the branch.**
   Show the user the branch, the remote and the list of sides. Ask to confirm. Then run:
   `git push -u $PUSH_REMOTE <branch>`
   Completion: the branch tracks `$PUSH_REMOTE/<branch>`.

6. **Build the PR body.**
   First line names the range, then one `Closes #N` line per issue in folio order, e.g.:
   `Adds TEI documents for folios 001B through 038A.`
   Completion: the body holds one `Closes` line per side, in the same order as step 2.

7. **Create the PR and verify.**
   Show the title and body to the user and ask to confirm. Then run:
   `gh pr create -R $REPO --base main --head $HEAD_REF --title "Add folios <FIRST> to <LAST>" --body-file <file>`
   Then `gh pr view <number> -R $REPO --json number,title,url,baseRefName,headRefName,body` to confirm base `main`, head, title, and body.
   Completion: the PR URL is returned and its body carries every `Closes #N`.
