#!/usr/bin/env bash
# Fast checks every task must pass. Run by the Stop hook during the task loop.
# Excludes live LLM, Moodle and E2E tests (slow / external) — the live LLM suite is
# triggered separately below, at most once per KB code state (see T82).
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
if [ -n "$(git status --porcelain -- ../mobile/lecturer/src ../mobile/lecturer/App.js)" ]; then
  echo "== lecturer web export (lecturer app sources changed)"
  out="$(mktemp -d)"
  (cd ../mobile/lecturer && CI=1 npx expo export --platform web --output-dir "$out" >/dev/null)
  rm -rf "$out"
fi

# ── live LLM suite (T82): run at most once per KB code state ──────────────────
# A round that changes app/services/kb/ (or a prompt) runs `pytest -m live` once; the
# hash of that directory is stored in .claude/.live-pass so the Stop hook and the loop
# script (which call check.sh several times) don't burn the daily quota. If the
# provider's daily quota is exhausted the live tests skip with LLM_QUOTA and we report
# "LIVE TESTS PENDING (quota)" instead of failing the round.
live_hash() {
  python -c "import hashlib, pathlib; h=hashlib.sha256(); \
    [h.update(p.read_bytes()) for p in sorted(pathlib.Path('app/services/kb').rglob('*.py'))]; \
    print(h.hexdigest())"
}
passfile="../.claude/.live-pass"
base="${SMARTCLASS_BASE:-HEAD}"
kb_changed="$(git diff --name-only "$base" -- app/services/kb | grep -c . || true)"
if [ "$kb_changed" -gt 0 ] && [ "$(live_hash)" != "$(cat "$passfile" 2>/dev/null || true)" ]; then
  echo "== live LLM tests (kb changed)"
  # -rs prints the skip reasons, so "LLM_QUOTA" shows up in the summary when quota is gone
  # "|| rc=$?" keeps set -e from exiting here before the output is printed
  rc=0; live_out="$(python -m pytest -m live -q -rs -p no:cacheprovider 2>&1)" || rc=$?
  echo "$live_out"
  if echo "$live_out" | grep -q "LLM_QUOTA"; then
    echo "LIVE TESTS PENDING (quota)"
  elif [ "$rc" -eq 0 ]; then
    mkdir -p ../.claude
    live_hash > "$passfile"
  else
    echo "live LLM tests failed" >&2
    exit 1
  fi
fi
