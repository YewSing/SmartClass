#!/usr/bin/env bash
# Fast checks every task must pass. Run by the Stop hook during the task loop.
# Excludes live LLM, Moodle and E2E tests (slow / external).
set -euo pipefail
cd "$(dirname "$0")/../backend"
echo "== test guard"
python ../scripts/test_guard.py
echo "== ruff"
ruff check .
echo "== pytest (not live/moodle/e2e)"
python -m pytest -q -p no:cacheprovider -m "not live and not moodle and not e2e"
echo "== student app unit tests"
(cd ../mobile/student && npm test --silent >/dev/null)
echo "== lecturer app unit tests"
(cd ../mobile/lecturer && npm test --silent >/dev/null)
if [ -n "$(git status --porcelain -- ../frontend/admin/src)" ]; then
  echo "== admin build (admin sources changed)"
  (cd ../frontend/admin && npm run build --silent)
fi
if [ -n "$(git status --porcelain -- ../mobile/lecturer/src ../mobile/lecturer/App.js)" ]; then
  echo "== lecturer web export (lecturer app sources changed)"
  out="$(mktemp -d)"
  (cd ../mobile/lecturer && CI=1 npx expo export --platform web --output-dir "$out" >/dev/null)
  rm -rf "$out"
fi
