#!/usr/bin/env bash
# Fails if a commit would add private research to this PUBLIC repo.
# Used by the local pre-commit hook (.githooks/pre-commit) and by CI
# (.github/workflows/private-content-guard.yml).
#
# Private research lives OUTSIDE this repo, in the sibling folder
# ../audhd-research-private. See docs/content-model.md.
#
# Usage: check-private-content.sh [--staged]   (default: all tracked files)
set -euo pipefail

if [[ "${1:-}" == "--staged" ]]; then
  files=$(git diff --cached --name-only --diff-filter=ACMR)
else
  files=$(git ls-files)
fi

# Folder names used by the private research tree, as top-level paths.
blocked_dirs='^(series|canon|private|unsorted|standalone|audhd-research-private|audhd-research-publication)/'
# File names and types that only the private tree should hold.
blocked_names='(case-file|consent-agreement|intake-questionnaire|dedupe-removed|manifest-plan|manifest-copy-log)'
blocked_types='\.(docx|doc|pptx|pptd|zip|bundle|7z|rar)$'
max_kb=5120   # anything larger than 5 MB is almost certainly not platform code

status=0
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  if [[ "$f" =~ $blocked_dirs ]]; then
    echo "BLOCKED (private folder): $f"; status=1
  elif [[ "$f" =~ $blocked_names ]]; then
    echo "BLOCKED (private file name): $f"; status=1
  elif [[ "$f" =~ $blocked_types ]]; then
    echo "BLOCKED (file type kept private): $f"; status=1
  elif [[ -f "$f" ]] && (( $(du -k "$f" | cut -f1) > max_kb )); then
    echo "BLOCKED (larger than 5 MB): $f"; status=1
  fi
done <<< "$files"

if (( status )); then
  echo
  echo "This repo is public. Move these files to ../audhd-research-private and unstage them:"
  echo "  git restore --staged <file>"
fi
exit $status
