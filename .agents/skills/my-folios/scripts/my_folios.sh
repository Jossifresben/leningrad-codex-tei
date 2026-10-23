#!/usr/bin/env bash
# List open `folio` issues assigned to the current gh user (oldest first).
# Marks folios whose TEI file already exists in edition/. Changes nothing.
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
  if [[ -n "$folio" && -f "$root/edition/$folio.xml" ]]; then
    status="  [TEI exists in edition/]"
  fi
  echo "#$number  $title$status"
done
