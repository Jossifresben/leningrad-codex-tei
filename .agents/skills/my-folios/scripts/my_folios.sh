#!/usr/bin/env bash
# List open `folio` issues assigned to the current gh user (oldest first).
# Marks each folio by where its TEI file is: merged to origin/main, committed
# on the current branch, or only in the working tree. Changes nothing.
#
# Usage: my_folios.sh
# Set REPO=owner/name to use a different repo (default below).
set -euo pipefail

REPO="${REPO:-charlesLoder/leningrad-codex-tei}"

command -v gh >/dev/null || { echo "gh is not installed" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh is not logged in; run 'gh auth login'" >&2; exit 1; }

root=$(git rev-parse --show-toplevel)

issues=$(gh issue list -R "$REPO" --label folio --state open \
  --assignee @me --search "sort:created-asc" --limit 200 \
  --json number,title --jq '.[] | "\(.number)\t\(.title)"')

if [[ -z "$issues" ]]; then
  echo "No open folio issues are assigned to you."
  exit 0
fi

echo "$issues" | while IFS=$'\t' read -r number title; do
  folio=$(grep -oE '[0-9]{3}[AB]' <<<"$title" | head -n1 || true)
  status=""
  if [[ -n "$folio" ]]; then
    if git -C "$root" cat-file -e "origin/main:edition/$folio.xml" 2>/dev/null; then
      status="  [on main]"
    elif git -C "$root" cat-file -e "HEAD:edition/$folio.xml" 2>/dev/null; then
      status="  [committed on branch]"
    elif [[ -f "$root/edition/$folio.xml" ]]; then
      status="  [generated, not committed]"
    fi
  fi
  echo "#$number  $title$status"
done
