#!/usr/bin/env bash
# Stop hook: during the task loop (SMARTCLASS_LOOP=1) refuse to stop while scripts/check.sh fails.
# Interactive sessions are unaffected. Gives up after 5 blocks so a session can't spin forever.
[ "${SMARTCLASS_LOOP:-}" = "1" ] || exit 0
cat > /dev/null   # hook input (unused)
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
counter="$root/.claude/.stop-blocks"
if out=$(bash "$root/scripts/check.sh" 2>&1); then rm -f "$counter"; exit 0; fi
n=$(( $(cat "$counter" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$counter"
if [ "$n" -gt 5 ]; then
  echo "scripts/check.sh still failing after 5 attempts; allowing stop. Follow the Blocked procedure." >&2
  exit 0
fi
{ echo "scripts/check.sh is failing, so the task is not done. Fix the cause (never weaken or skip tests),"
  echo "or if truly stuck follow the Blocked procedure in /next-task. Last output:"
  echo "$out" | tail -40; } >&2
exit 2
