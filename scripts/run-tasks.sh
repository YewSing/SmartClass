#!/usr/bin/env bash
# Run PLAN.md tasks one per fresh Claude session.
# Usage (Git Bash, repo root):  bash scripts/run-tasks.sh [rounds=2] [max_turns=80]
set -uo pipefail
N=${1:-2}; TURNS=${2:-80}
root=$(cd "$(dirname "$0")/.." && pwd); cd "$root"

branch=$(git branch --show-current)
[ "$branch" != "main" ] || { echo "Refusing to run on main. Switch to a feature branch."; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "Uncommitted changes. Commit or stash first."; exit 1; }

echo "Starting postgres..."
(cd backend && docker compose up -d) > /dev/null 2>&1
for _ in $(seq 1 30); do
  docker inspect -f '{{.State.Health.Status}}' backend-db-1 2>/dev/null | grep -q healthy && break; sleep 2
done

mkdir -p .claude/logs
export SMARTCLASS_LOOP=1
for i in $(seq 1 "$N"); do
  before=$(git rev-parse HEAD)
  rm -f .claude/.stop-blocks
  log=".claude/logs/round-$(date +%Y%m%d-%H%M%S).log"
  echo "== Round $i/$N  (log: $log)"
  claude -p "/next-task" --permission-mode acceptEdits --max-turns "$TURNS" > "$log" 2>&1

  if [ "$before" = "$(git rev-parse HEAD)" ]; then
    echo "   no commit this round - stopping. Read $log"; break
  fi
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
echo "Done. Read PROGRESS.md, then: git log --oneline -$N"
