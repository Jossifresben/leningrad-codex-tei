#!/usr/bin/env bash
# List open, unassigned `folio` issues (oldest first) and optionally comment
# on each to ask the repo owner for assignment.
#
# Usage:
#   claim_folios.sh <N>             # list only; changes nothing
#   claim_folios.sh <N> --comment   # list, then comment on each issue
#
# Set REPO=owner/name to use a different repo (default below).
set -euo pipefail

REPO="${REPO:-charlesLoder/leningrad-codex-tei}"
OWNER="${REPO%%/*}"

usage() {
  echo "Usage: $0 <N> [--comment]" >&2
  exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage
N="$1"
[[ "$N" =~ ^[1-9][0-9]*$ ]] || usage
COMMENT=false
if [[ $# -eq 2 ]]; then
  [[ "$2" == "--comment" ]] || usage
  COMMENT=true
fi

command -v gh >/dev/null || { echo "gh is not installed" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "gh is not logged in; run 'gh auth login'" >&2; exit 1; }

# Tab-separated: number, title. Sorted oldest first, like the issues URL in CONTRIBUTING.MD.
issues=$(gh issue list -R "$REPO" --label folio --state open \
  --search "no:assignee sort:created-asc" --limit "$N" \
  --json number,title --jq '.[] | "\(.number)\t\(.title)"')

if [[ -z "$issues" ]]; then
  echo "No open, unassigned folio issues found."
  exit 0
fi

echo "$issues" | while IFS=$'\t' read -r number title; do
  echo "#$number  $title"
done

$COMMENT || exit 0

echo
echo "$issues" | while IFS=$'\t' read -r number title; do
  gh issue comment "$number" -R "$REPO" \
    --body "@$OWNER I would like to be assigned this issue. Thank you!" >/dev/null
  echo "Commented on #$number"
done
