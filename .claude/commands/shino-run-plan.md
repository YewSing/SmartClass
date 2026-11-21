---
description: Run Shino's plan-shino.md task loop (M2/M5/M6/M7) in the background (default 5 rounds), then summarise what got done.
argument-hint: "[rounds, default 5] [hybrid]"
---

Start Shino's SmartClass task loop and report back. Arguments: $ARGUMENTS. Rounds = the first number (use 5 if none). Never use more than 5 unless Shino typed a bigger number in this request. If the arguments contain `hybrid`, run with `SMARTCLASS_BUILDER=opencode` (Opus plans, OpenCode builds, Sonnet reviews).

1. Pre-flight, and fix only these if needed:
   - Must not be on `main`. If on main, stop and tell the user.
   - If there are uncommitted tracked changes, show them (`git status --short`, `git diff --stat`) and ask the user whether to commit them before starting. Don't start until the tree is clean.
   - If another loop is running (`.claude/.loop.lock` holds a live PID), say so and stop. Only one loop (Shino's or Yew Sing's) may run on a machine: they share the test database.
2. Record the starting commit: `git rev-parse HEAD` (call it START).
   Run `bash scripts/shino/run-tasks.sh <rounds>` (prefixed with `SMARTCLASS_BUILDER=opencode ` for hybrid) with the Bash tool using `run_in_background: true`. Don't poll; you'll be notified when it exits.
3. When it exits, read the script output, `progress-shino.md` (Blocked, Next, and the new Log entries) and `git log --oneline` for the new commits.
4. **Checkpoint review** (skip if no new commits). Each task already had a per-task review, so look for what those can't see — problems *across* tasks:
   - Use `git log --oneline START..HEAD` and `git diff --stat START..HEAD`, then read the diffs of the files that matter (models, migrations, routers, services, tests); skim the rest.
   - Check against `plan-shino.md` "Done when" lines and the FRs/NFRs they cite: anything ticked `[x]` that isn't really done; drift from the spec; two tasks solving the same thing differently; duplicated code; API shapes or migrations that conflict (one Alembic head); tests that only test mocks; security/privacy rules (NFR-04 role checks, NFR-06 audit, NFR-09 and FR-504/515/713 anonymity, graded results never ranked publicly); any edit to Yew Sing's modules (M1, M3, M4, M8) beyond an additive interface.
   - Run `bash scripts/check.sh` once more, and `cd backend && python -m pytest -m "db" -q`.
   - Fix nothing yourself. Put real problems under `## Next` in progress-shino.md as `REVIEW: <task> - <problem>` and commit `Checkpoint review START..HEAD`. If a problem means a finished task is wrong, change its box back to `[ ]` with a note, so the next loop redoes it.
   - If the loop stopped at a `[HUMAN] Checkpoint` and the review found no high-severity problem, say so clearly: Shino only needs to reply "tick Sxx" for you to tick it, commit and push.
5. Reply with a short report:
   - what changed for someone using the app, in plain language, and exactly what to try (or "nothing visible yet")
   - tasks finished (`[x]`), tasks needing a manual check (`[~]`, and exactly what to check), blocked tasks and why
   - any `TEST-CHANGE:` notes or interface/schema changes, which the user should look at
   - why the loop stopped (all rounds done, blocked, failing check, usage limit)
   - checkpoint review verdict: OK / problems found (list the top ones, one line each)
   - what's next in plan-shino.md, especially `[HUMAN]` tasks now waiting for Shino
   - the backup taken at the start (path), in case the data needs restoring.
Do not do task work yourself in this session (ticking a `[HUMAN]` gate when the user asks is fine).
