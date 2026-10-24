---
name: resolve-index-conflict
description: Fix the merge conflict in edition/index.xml on a folio pull request. Merges main into the PR branch, rebuilds the index in folio order with build-index, and pushes. Use when a folio PR shows a merge conflict.
---

# Resolve Index Conflict

Folio PRs nearly always conflict on `edition/index.xml`. Each PR adds entries at the same place in the file, so git cannot merge them.
`edition/index.xml` is a generated file. Do not merge it by hand. Rebuild it from the folio files with `build-index`. The entries then come out in folio order.

The argument is a PR number or URL, for example `611`. If none is given, ask the user. Do not guess.

`REPO` is `charlesLoder/leningrad-codex-tei`. Always pass `-R $REPO` to `gh` commands.

## Rules

- Only `edition/index.xml` may conflict. If any other file conflicts, stop and tell the user. Do not resolve it.
- Never edit the conflict markers by hand. Rebuild the file.
- Work in a separate `git worktree`. Do not touch the user's working tree.
- Ask the user before you push. A push is public.
- Do not use `--force`. Add a merge commit.

## Steps

1. **Read the PR.**
   `gh pr view <PR> -R $REPO --json title,headRefName,headRepositoryOwner,headRepository,isCrossRepository,maintainerCanModify,mergeable`
   - `mergeable` is not `CONFLICTING`: tell the user there is nothing to fix. Stop.
   - `isCrossRepository` is true and `maintainerCanModify` is false: stop and tell the user. They must ask the contributor to resolve it, or to allow edits.
   Completion: you know the head branch, the head repository, and that the PR conflicts.

2. **Make a worktree of the PR branch.**
   ```sh
   git fetch origin pull/<PR>/head:pr-<PR>
   git fetch origin main
   git worktree add <dir> pr-<PR>
   ```
   Use a directory outside the repo (for example a scratchpad or temp directory).
   Completion: `<dir>` holds the PR branch.

3. **Merge main.**
   In `<dir>`: `git merge origin/main --no-edit`
   Then run `git status --short | grep '^U\|^AA\|^DU\|^UD'`.
   - Only `edition/index.xml` is listed: continue.
   - Any other path is listed: stop (see Rules).
   Completion: `edition/index.xml` is the only unmerged path.

4. **Rebuild the index.**
   In `<dir>`:
   ```sh
   git checkout --theirs edition/index.xml
   uv run leningrad build-index
   ```
   The first command removes the conflict markers. `build-index` then writes the file again from all `edition/*.xml` files, sorted by folio.
   Completion: `build-index` prints `N entries -> edition/index.xml`.

5. **Check the result.**
   - No conflict markers: `grep -c '<<<<<<<\|>>>>>>>' edition/index.xml` prints `0`.
   - The entry count equals the number of folio files: `grep -c '<entry' edition/index.xml` equals `ls edition/*.xml | grep -vc index`.
   - The entries are in folio order: `grep -o 'entry folio="[0-9A-B]*"' edition/index.xml | sed 's/.*="//;s/"//' | awk 'NR>1&&$0<p{print "OUT OF ORDER " $0} {p=$0}'` prints nothing.
   - Only lines were added to main's index: `git diff origin/main --stat -- edition/index.xml` shows insertions only (5 lines for each folio side in the PR). Changed or removed lines mean an older entry changed. Stop and tell the user.
   - `uv run ruff format --check` passes.
   Completion: all five checks pass.

6. **Commit.**
   `git add edition/index.xml && git commit -m "merge main; rebuild index.xml in folio order"`
   Add the attribution line the session requires.
   Completion: `git status` shows a clean tree.

7. **Push.**
   Show the user the target and ask to confirm. Push to the head branch of the PR, with no force:
   - Same repository: `git push origin HEAD:<headRefName>`
   - Fork: `git push https://github.com/<headOwner>/<headRepo>.git HEAD:<headRefName>`
   Completion: the push ends without an error.

8. **Confirm.**
   Wait a few seconds, then run `gh pr view <PR> -R $REPO --json mergeable,mergeStateStatus`.
   - `mergeable` is `MERGEABLE`: done. `UNSTABLE` only means the checks are still running.
   - Still `CONFLICTING`: main moved while you worked. Go back to step 2.
   Completion: `mergeable` is `MERGEABLE`.

9. **Clean up.**
   `git worktree remove <dir>` and `git branch -D pr-<PR>` from the main clone.
   Tell the user the PR is mergeable.

## Notes

- Another PR that merges first makes this PR conflict again. Run this skill again.
- The cause was `commit-folios` building the index in each PR. It no longer does. A PR made with an older version of that skill can still carry an `index.xml` change.
