#!/usr/bin/env bash
# Run PLAN.md tasks one per fresh Claude session (Opus), until done, blocked, or N rounds.
# Usage (Git Bash, repo root):  bash scripts/run-tasks.sh [rounds=2] [max_turns=80]
#   e.g. overnight: bash scripts/run-tasks.sh 30
set -uo pipefail
N=${1:-2}; TURNS=${2:-80}
MODEL=${SMARTCLASS_MODEL:-opus}
LIMIT_WAIT_MIN=30      # on a Claude usage limit: wait this long, then retry the same round
LIMIT_MAX_WAITS=12     # ... at most this many times (6 hours)
root=$(cd "$(dirname "$0")/.." && pwd); cd "$root"

branch=$(git branch --show-current)
[ "$branch" != "main" ] || { echo "Refusing to run on main. Switch to a feature branch."; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "Uncommitted changes. Commit or stash first."; exit 1; }

echo "Backing up app DB + Moodle data (undo with: bash scripts/restore-data.sh)..."
bash scripts/backup-data.sh || { echo "Backup failed - not starting the loop."; exit 1; }
echo "Starting postgres..."
(cd backend && docker compose up -d) > /dev/null 2>&1
(cd backend/moodle && docker compose up -d) > /dev/null 2>&1   # simulated SPeCTRUM for moodle tests
for _ in $(seq 1 30); do
  docker inspect -f '{{.State.Health.Status}}' backend-db-1 2>/dev/null | grep -q healthy && break; sleep 2
done

mkdir -p .claude/logs
export SMARTCLASS_LOOP=1
done_rounds=0; waits=0
while [ "$done_rounds" -lt "$N" ]; do
  before=$(git rev-parse HEAD)
  export SMARTCLASS_BASE="$before"     # test guard compares against the round's starting commit
  rm -f .claude/.stop-blocks
  log=".claude/logs/round-$(date +%Y%m%d-%H%M%S).log"
  echo "== Round $((done_rounds + 1))/$N  $(date +%H:%M)  (log: $log)"
  claude -p "/next-task" --model "$MODEL" --permission-mode acceptEdits --max-turns "$TURNS" \
    --disallowedTools "Bash(git push*)" > "$log" 2>&1

  if [ "$before" = "$(git rev-parse HEAD)" ]; then
    if grep -qiE "usage limit|limit reached|rate limit|overloaded" "$log" && [ "$waits" -lt "$LIMIT_MAX_WAITS" ]; then
      waits=$((waits + 1))
      [ -z "$(git status --porcelain --untracked-files=no)" ] || git stash push -u -q -m "loop: partial work before usage limit"
      echo "   Claude usage limit - waiting ${LIMIT_WAIT_MIN} min (wait $waits/$LIMIT_MAX_WAITS), then retrying this round"
      sleep $((LIMIT_WAIT_MIN * 60)); continue
    fi
    echo "   no commit this round - stopping. Read $log"; break
  fi
  waits=0; done_rounds=$((done_rounds + 1))
  subject=$(git log -1 --format=%s); echo "   committed: $subject"
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "   uncommitted changes left behind - stopping"; break
  fi
  if ! bash scripts/check.sh > /dev/null 2>&1; then
    echo "   check.sh fails after the round - stopping"; break
  fi
  git push -q origin "$branch" 2>/dev/null || echo "   (push failed; continuing)"
  case "$subject" in *": blocked"*) echo "   task blocked - stopping. See PROGRESS.md"; break;; esac
done
echo "Finished $done_rounds round(s). Summary: PROGRESS.md · git log --oneline -$done_rounds"
