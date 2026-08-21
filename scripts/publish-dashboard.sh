#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -d "$ROOT/.git" ]]; then
  echo "Nincs git repo — a dashboard helyben marad (docs/index.html)."
  exit 0
fi
git add docs
if git diff --cached --quiet; then
  echo "A dashboard nem változott, nincs mit feltölteni."
  exit 0
fi
git commit -m "Dashboard frissítés $(date '+%Y-%m-%d %H:%M')"
git push
