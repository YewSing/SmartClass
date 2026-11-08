#!/usr/bin/env bash
# Fast checks every task must pass. Run by the Stop hook during the task loop.
# Excludes live LLM, Moodle and E2E tests (slow / external).
set -euo pipefail
cd "$(dirname "$0")/../backend"
echo "== ruff"
ruff check .
echo "== pytest (not live/moodle/e2e)"
python -m pytest -q -p no:cacheprovider -m "not live and not moodle and not e2e"
if [ -n "$(git status --porcelain -- ../frontend/admin/src)" ]; then
  echo "== admin build (admin sources changed)"
  (cd ../frontend/admin && npm run build --silent)
fi
