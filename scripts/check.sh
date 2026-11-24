#!/usr/bin/env bash
# Fast checks every task must pass. Run by the Stop hook during the task loop.
# Excludes live LLM, Moodle and E2E tests (slow / external) — the live LLM suite is
# triggered separately below, at most once per KB code state (see T82).
set -euo pipefail
cd "$(dirname "$0")/../backend"

# ── pass cache (task loop only) ────────────────────────────────────────────────
# In a loop round check.sh runs several times on the same code (the session, the Stop hook,
# the loop script after the commit). When it already passed on exactly this code and round
# base, say so and stop. Fingerprint = round base + tree of the code on disk (tracked and
# untracked, minus plan/progress files and .claude/), built in a throwaway index.
fingerprint() {
  local idx root; idx=$(mktemp); root=$(git rev-parse --show-toplevel)
  cp "$root/.git/index" "$idx" 2>/dev/null || true
  (
    cd "$root"
    export GIT_INDEX_FILE="$idx"
    git add -A . > /dev/null 2>&1
    git rm -r -q --cached --ignore-unmatch -- PLAN.md PROGRESS.md plan-shino.md progress-shino.md .claude > /dev/null 2>&1
    echo "${SMARTCLASS_BASE:-HEAD} $(git write-tree)"
  )
  rm -f "$idx"
}
pass_stamp="../.claude/.check-pass"
fp=""
if [ "${SMARTCLASS_LOOP:-}" = "1" ]; then
  fp="$(fingerprint || true)"
  if [ -n "$fp" ] && [ "$fp" = "$(cat "$pass_stamp" 2>/dev/null || true)" ]; then
    echo "== check.sh already passed on this exact code (cached; edit any code file to re-run)"
    exit 0
  fi
fi
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

# ── live LLM suite (T82): run at most once per AI code state ──────────────────
# A round that changes app/services/kb/ runs the whole live suite; a round that changes only
# app/services/quiz/ (M6 prompts) runs only the M6 live tests (S41), so a flaky M8 live test
# can't fail an M6 round. The hash of both directories is stored in .claude/.live-pass (whole
# suite passed) or .claude/.live-pass-quiz (M6 tests passed), so the Stop hook and the loop
# script (which call check.sh several times) don't burn the daily quota. New untracked files
# there count as a change too. If the provider's daily quota is exhausted the live tests skip
# with LLM_QUOTA and we report "LIVE TESTS PENDING (quota)" instead of failing the round.
live_hash() {
  python -c "import hashlib, pathlib; h=hashlib.sha256(); \
    [h.update(p.read_bytes()) for d in ('app/services/kb', 'app/services/quiz') \
     for p in sorted(pathlib.Path(d).rglob('*.py'))]; \
    print(h.hexdigest())"
}
base="${SMARTCLASS_BASE:-HEAD}"
changed_in() {
  { git diff --name-only "$base" -- "$1" 2>/dev/null || true; \
    git ls-files --others --exclude-standard -- "$1"; } | grep -c . || true
}
passed_in() { [ "$(live_hash)" = "$(cat "$1" 2>/dev/null || true)" ]; }
full_pass="../.claude/.live-pass"
quiz_pass="../.claude/.live-pass-quiz"
live_label=""; live_pass=""; live_paths=()
if [ "$(changed_in app/services/kb)" -gt 0 ]; then
  passed_in "$full_pass" || { live_label="whole suite"; live_pass="$full_pass"; }
elif [ "$(changed_in app/services/quiz)" -gt 0 ]; then
  if ! passed_in "$full_pass" && ! passed_in "$quiz_pass"; then
    live_label="M6 only"; live_pass="$quiz_pass"; live_paths=(tests/live/test_live_quiz*.py)
  fi
fi
if [ -n "$live_label" ]; then
  echo "== live LLM tests (kb/quiz changed): $live_label"
  # -rs prints the skip reasons, so "LLM_QUOTA" shows up in the summary when quota is gone
  # "|| rc=$?" keeps set -e from exiting here before the output is printed
  rc=0; live_out="$(python -m pytest -m live -q -rs -p no:cacheprovider \
    ${live_paths[@]+"${live_paths[@]}"} 2>&1)" || rc=$?
  echo "$live_out"
  if echo "$live_out" | grep -q "LLM_QUOTA"; then
    echo "LIVE TESTS PENDING (quota)"
  elif [ "$rc" -eq 0 ]; then
    mkdir -p ../.claude
    live_hash > "$live_pass"
  else
    echo "live LLM tests failed" >&2
    exit 1
  fi
fi

# Record the pass for the cache above (only reached when every check passed).
if [ -n "$fp" ]; then mkdir -p ../.claude && echo "$fp" > "$pass_stamp"; fi
