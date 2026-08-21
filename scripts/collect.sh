#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi
"$PYTHON" -m farewatch collect "$@"
COLLECT_EXIT=$?
"$PYTHON" -m farewatch dashboard
if [[ -d "$ROOT/.git" ]]; then
  bash "$ROOT/scripts/publish-dashboard.sh" || true
fi
exit "$COLLECT_EXIT"
