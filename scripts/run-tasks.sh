#!/usr/bin/env bash
# Run PLAN.md tasks one per fresh Claude session (Opus), until done, blocked, or N rounds.
# Usage (Git Bash, repo root):  bash scripts/run-tasks.sh [rounds=2] [max_turns=80]
#   e.g. overnight: bash scripts/run-tasks.sh 30
set -uo pipefail
N=${1:-2}; TURNS=${2:-80}
MODEL=${SMARTCLASS_MODEL:-opus}
LIMIT_WAIT_MIN=${SMARTCLASS_LIMIT_WAIT_MIN:-30}   # on a Claude usage limit: wait this long, then retry the same round
LIMIT_MAX_WAITS=12     # ... at most this many times (6 hours)
root=$(cd "$(dirname "$0")/.." && pwd); cd "$root"

# claude -p has no auto-continue, so this script does the waiting. A limit is the
# last thing a stopped round prints, so only the last line counts: a round that
# merely discusses, say, a Gemini rate limit must not sleep for hours. "hit your
# ... limit" covers the wording changes so far (session, 5-hour) and later ones.
hit_usage_limit() {
  grep -v '^[[:space:]]*$' "$1" | tail -n 1 \
    | grep -qiE "hit your .*limit|usage limit|session limit|limit reached|rate limit|overloaded"
}

RESUME_NOTE="An earlier round of this task stopped at a Claude usage limit and left its unfinished work uncommitted in this working tree. Before step 2, read git status and git diff. Continue that task from that work instead of starting over, even if PLAN.md already ticks it. If it is finished, run the remaining steps and commit it."

# Only one loop at a time: two runs overwrite each other's files and test database.
lock=".claude/.loop.lock"
if [ -f "$lock" ] && kill -0 "$(cat "$lock")" 2>/dev/null; then
  echo "Another loop is already running (PID $(cat "$lock")). Not starting."; exit 1
fi
echo $$ > "$lock"; trap 'rm -f "$lock"' EXIT

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

# SMARTCLASS_BUILDER=opencode (hybrid): Opus plans (/plan-task, read-only), OpenCode builds
# (SMARTCLASS_OC_MODEL, --auto), the Claude Sonnet reviewer checks (at most 2 fix rounds),
# OpenCode ticks/logs/commits. [OPUS] tasks, a stuck builder or a failed review go to Opus /next-task.
# Approved by Yew Sing 2026-11-12 for this branch.
BUILDER=${SMARTCLASS_BUILDER:-claude}
OC_MODEL=${SMARTCLASS_OC_MODEL:-opencode-go/deepseek-v4.1-flash}
if [ "$BUILDER" = "opencode" ]; then
  command -v opencode > /dev/null || { echo "opencode not found on PATH."; exit 1; }
  install -m 755 scripts/opencode/pre-push .git/hooks/pre-push   # refuses pushes from the builder
  mkdir -p .claude/plans
  echo "Hybrid loop: plan Claude $MODEL, build OpenCode $OC_MODEL, review Claude Sonnet"
fi

oc() {  # one OpenCode turn; SMARTCLASS_NO_PUSH makes the pre-push hook refuse
  local out rc try
  for try in 1 2 3; do
    out=$(mktemp)
    SMARTCLASS_NO_PUSH=1 opencode run --standalone --auto -m "$OC_MODEL" "$@" > "$out" 2>&1; rc=$?
    cat "$out"
    # A provider/network drop ends the turn early; continue the same session instead of giving up.
    if grep -qiE "Error: *(Transport|.*timeout|.*ECONNRESET|.*overloaded|.*rate limit)" <(tail -n 5 "$out") && [ "$try" -lt 3 ]; then
      rm -f "$out"; echo "   (OpenCode connection error; retrying in 60 s)" >&2; sleep 60
      set -- -c "The connection dropped. Continue exactly where you stopped, with the same instructions."
      continue
    fi
    rm -f "$out"; return $rc
  done
}

# Tree hash of the code as it is on disk (tracked + untracked, minus PLAN.md, PROGRESS.md and
# .claude/), built in a throwaway index so the real one is untouched. Equal hashes = same code.
code_tree() {
  local idx; idx=$(mktemp)
  cp .git/index "$idx" 2>/dev/null || true
  GIT_INDEX_FILE="$idx" git add -A . > /dev/null 2>&1
  GIT_INDEX_FILE="$idx" git rm -r -q --cached --ignore-unmatch -- PLAN.md PROGRESS.md .claude > /dev/null 2>&1
  GIT_INDEX_FILE="$idx" git write-tree
  rm -f "$idx"
}

# Opus COACH: reads the failure, the plan and the diff (read-only) and writes exact fix steps for
# OpenCode. Much cheaper than an Opus takeover. $1 log, $2 task, $3 plan, $4 what went wrong.
# Prints the hint; returns 1 when the coach gave none (usage limit, error).
coach() {
  local log=$1 task=$2 plan=$3 what=$4 out
  out=$(mktemp)
  claude -p "You are the COACH in the SmartClass hybrid task loop. A cheaper builder (DeepSeek through OpenCode) is carrying out the plan $plan for task $task and $what. Do NOT edit any file. Read the plan, run git status and git diff, read the code and tests the failure points at, and find the root cause.
Reply in at most 25 lines: ROOT CAUSE (1-3 lines), then FIX: numbered, exact steps (file, function, the change), then RUN: the commands to rerun. If the plan itself is wrong, say which step and what to do instead. Make your LAST line exactly COACH: $task

What the builder and the checks printed last:
$(tail -n 80 "$log" | cut -c1-300)
$( [ -f "$log.check" ] && { echo; echo "check.sh, last lines:"; tail -n 30 "$log.check"; } )
$( [ -n "${5:-}" ] && { echo; echo "Reviewer:"; echo "$5"; } )" \
    --model "$MODEL" --max-turns 30 \
    --allowedTools "Read" "Grep" "Glob" "Bash(git status*)" "Bash(git diff*)" "Bash(git log*)" > "$out" 2>&1
  cat "$out" >> "$log.coach"
  if grep -q "COACH: $task" <(tail -n 3 "$out"); then cat "$out"; rm -f "$out"; return 0; fi
  hit_usage_limit "$out" && tail -n 1 "$out" >> "$log"
  rm -f "$out"; return 1
}

opus_build() {  # $1 log, $2 optional extra instruction
  local extra=()
  [ -z "${2:-}" ] || extra=(--append-system-prompt "$2")
  claude -p "/next-task" --model "$MODEL" --permission-mode acceptEdits --max-turns "$TURNS" \
    --disallowedTools "Bash(git push*)" ${extra[@]+"${extra[@]}"} >> "$1" 2>&1
}

hybrid_round() {
  local log=$1 last task plan r check_rc=1 passed=0 review=""
  claude -p "/plan-task" --model "$MODEL" --max-turns 60 \
    --allowedTools "Read" "Grep" "Glob" "Edit(.claude/plans/**)" "Write(.claude/plans/**)" \
      "Bash(git status*)" "Bash(git diff*)" "Bash(git log*)" > "$log" 2>&1
  last=$(grep -v '^[[:space:]]*$' "$log" | tail -n 1)
  case "$last" in
    NONE:*)
      python - "${last#NONE: }" <<'PY'
import sys, datetime
p = "PROGRESS.md"; s = open(p, encoding="utf-8").read()
line = f"- No runnable task ({datetime.date.today()}): {sys.argv[1]}\n"
s = s.replace("\n## Log", "\n" + line + "\n## Log", 1) if "\n## Log" in s else s + line
open(p, "w", encoding="utf-8").write(s)
PY
      git add PROGRESS.md && git commit -q -m "Loop: no runnable task (${last#NONE: })" >> "$log" 2>&1
      return 0;;
    OPUS:*)
      echo "   [OPUS] task ${last#OPUS: }: Claude builds it" | tee -a "$log"
      opus_build "$log"; return 0;;
    PLAN:*) task=${last#PLAN: };;
    *) echo "   planner gave no PLAN/OPUS/NONE line" | tee -a "$log"; return 0;;
  esac
  plan=".claude/plans/$task.md"
  [ -f "$plan" ] || { echo "   planner wrote no $plan" | tee -a "$log"; return 0; }
  echo "   planned $task; OpenCode building" | tee -a "$log"
  oc --title "SmartClass $task" "$(sed "s|__PLAN__|$plan|" scripts/opencode/build.md)" >> "$log" 2>&1

  # Stuck or failing: OpenCode fixes once from the review alone; after that (or when it says
  # STUCK) an Opus coach diagnoses and OpenCode applies its steps, at most 2 coach rounds.
  # Only then does Opus take over (Yew Sing 2026-11-11: the loop must never stop on a stuck task).
  local fixed=0 coached=0 hint tree=""
  r=0
  while :; do
    if grep -q "TASK: STUCK" <(tail -n 5 "$log"); then
      [ "$coached" -lt 2 ] || break
      coached=$((coached + 1))
      echo "   OpenCode stuck: Opus coach $coached/2" | tee -a "$log"
      hint=$(coach "$log" "$task" "$plan" "stopped with TASK: STUCK") \
        || { echo "   coach gave no hint" | tee -a "$log"; break; }
      oc -c "$(cat scripts/opencode/coach-fix.md)
$hint" >> "$log" 2>&1
      continue
    fi
    r=$((r + 1))
    bash scripts/check.sh > "$log.check" 2>&1; check_rc=$?
    tree=$(code_tree)
    claude --agent reviewer -p "Task $task. Its plan: $plan (read it). Ticking the task in PLAN.md and writing its PROGRESS.md Log entry happen AFTER your review, so their absence is not a finding. PLAN.md entry:
$(grep -A1 -F "**$task " PLAN.md | head -n 2)

bash scripts/check.sh exited $check_rc. Its last lines:
$(tail -n 25 "$log.check")" --model sonnet --max-turns 40 > "$log.review$r" 2>&1
    review=$(cat "$log.review$r")
    echo "   review $r: $(grep -m1 -oE 'VERDICT: [A-Z ]+' "$log.review$r" || echo 'no verdict'), check.sh exit $check_rc" | tee -a "$log"
    if [ "$check_rc" -eq 0 ] && grep -q "VERDICT: PASS" "$log.review$r"; then passed=1; break; fi
    if [ "$fixed" -eq 0 ]; then
      fixed=1
      oc -c "$(cat scripts/opencode/fix.md)
$review

check.sh (exit $check_rc), last lines:
$(tail -n 25 "$log.check")" >> "$log" 2>&1
    elif [ "$coached" -lt 2 ]; then
      coached=$((coached + 1))
      echo "   still failing: Opus coach $coached/2" | tee -a "$log"
      hint=$(coach "$log" "$task" "$plan" "still fails the checks or the review after a fix" "$review") \
        || { echo "   coach gave no hint" | tee -a "$log"; break; }
      oc -c "$(cat scripts/opencode/coach-fix.md)
$hint" >> "$log" 2>&1
    else
      break
    fi
  done

  if [ "$passed" -eq 1 ]; then
    checked_tree=$tree   # lets the main loop skip a second check.sh when the commit adds no code
    oc -c "$(sed "s|__MODEL__|$OC_MODEL|" scripts/opencode/finish.md)
$review" >> "$log" 2>&1
  else
    echo "   OpenCode could not finish $task after $coached coach round(s): Opus takes over" | tee -a "$log"
    opus_build "$log" "Task $task was planned in $plan and partly built by another model; its uncommitted work is in this tree. Last reviewer output (if any): $log.review$r; check output: $log.check; coach notes: $log.coach. Pick $task, read the plan, git status and git diff, continue from that work (fix, do not start over), then run steps 5-9. Add 'built by OpenCode, finished by Opus' to the Log entry."
  fi
}

mkdir -p .claude/logs
export SMARTCLASS_LOOP=1
done_rounds=0; waits=0; resume_args=()
while [ "$done_rounds" -lt "$N" ]; do
  before=$(git rev-parse HEAD)
  export SMARTCLASS_BASE="$before"     # test guard compares against the round's starting commit
  rm -f .claude/.stop-blocks
  checked_tree=""                      # set by hybrid_round when its check.sh passed
  log=".claude/logs/round-$(date +%Y%m%d-%H%M%S).log"
  echo "== Round $((done_rounds + 1))/$N  $(date +%H:%M)  (log: $log)"
  if [ "$BUILDER" = "opencode" ]; then
    hybrid_round "$log"
  else
    claude -p "/next-task" --model "$MODEL" --permission-mode acceptEdits --max-turns "$TURNS" \
      --disallowedTools "Bash(git push*)" ${resume_args[@]+"${resume_args[@]}"} > "$log" 2>&1
  fi

  if [ "$before" = "$(git rev-parse HEAD)" ]; then
    if hit_usage_limit "$log" && [ "$waits" -lt "$LIMIT_MAX_WAITS" ]; then
      waits=$((waits + 1))
      # Partial work stays in the tree for the retry; a stash would hide it from the next round.
      if [ -n "$(git status --porcelain -- . ':(exclude)*.pdf')" ] || [ "${#resume_args[@]}" -gt 0 ]; then
        resume_args=(--append-system-prompt "$RESUME_NOTE")
      fi
      echo "   Claude usage limit - waiting ${LIMIT_WAIT_MIN} min (wait $waits/$LIMIT_MAX_WAITS), then retrying this round"
      sleep $((LIMIT_WAIT_MIN * 60)); continue
    fi
    echo "   no commit this round - stopping. Read $log"; break
  fi
  waits=0; resume_args=(); done_rounds=$((done_rounds + 1))
  subject=$(git log -1 --format=%s); echo "   committed: $subject"
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "   uncommitted changes left behind - stopping"; break
  fi
  # The pre-review check.sh already passed on this exact code when only PLAN/PROGRESS changed since.
  if [ -n "$checked_tree" ] && [ "$(code_tree)" = "$checked_tree" ]; then
    echo "   (code unchanged since its passing check.sh; post-commit run skipped)"
  elif ! bash scripts/check.sh > /dev/null 2>&1; then
    echo "   check.sh fails after the round - stopping"; break
  fi
  git push -q origin "$branch" 2>/dev/null || echo "   (push failed; continuing)"
  case "$subject" in
    *": blocked"*) echo "   task blocked - stopping. See PROGRESS.md"; break;;
    *"no runnable task"*) echo "   waiting on a checkpoint - stopping"; break;;
  esac
done
echo "Finished $done_rounds round(s). Summary: PROGRESS.md · git log --oneline -$done_rounds"
