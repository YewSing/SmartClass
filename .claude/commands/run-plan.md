---
description: Run the PLAN.md task loop in the background (default 5 rounds), then summarise what got done.
argument-hint: "[rounds, default 5]"
---

Start the SmartClass task loop and report back. Rounds: $ARGUMENTS (use 5 if empty). Never use more than 5 unless Yew Sing typed a bigger number in this request.

1. Pre-flight, and fix only these if needed:
   - Must not be on `main`. If on main, stop and tell the user.
   - If there are uncommitted tracked changes, show them (`git status --short`, `git diff --stat`) and ask the user whether to commit them before starting. Don't start until the tree is clean.
2. Record the starting commit: `git rev-parse HEAD` (call it START).
   Run `bash scripts/run-tasks.sh <rounds>` with the Bash tool using `run_in_background: true`. Don't poll; you'll be notified when it exits.
3. When it exits, read the script output, `PROGRESS.md` (Blocked, Next, and the new Log entries) and `git log --oneline` for the new commits.
4. **Checkpoint review** (skip if no new commits). Each task already had a per-task review, so look for what those can't see — problems *across* tasks:
   - Use `git log --oneline START..HEAD` and `git diff --stat START..HEAD`, then read the diffs of the files that matter (models, migrations, routers, services, tests); skim the rest.
   - Check against `PLAN.md` "Done when" lines and the FRs/NFRs they cite: anything ticked `[x]` that isn't really done; drift from the spec; two tasks solving the same thing differently; duplicated code; API shapes or migrations that conflict; tests that only test mocks; security/privacy rules (NFR-01, NFR-04, NFR-06, NFR-09); anything touching Shino's modules.
   - Run `bash scripts/check.sh` once more, and `cd backend && python -m pytest -m "db" -q`.
   - Fix nothing yourself. Put real problems under `## Next` in PROGRESS.md as `REVIEW: <task> - <problem>` and commit `Checkpoint review START..HEAD`. If a problem means a finished task is wrong, change its box back to `[ ]` with a note, so the next loop redoes it.
   - If the loop stopped at the T04 checkpoint (or another `[HUMAN]` gate) and the review found no high-severity problem, say so clearly: the user only needs to reply "tick T04" for you to tick it, commit and push.
5. Reply with a short report:
   - what changed for someone using the app, in plain language, and exactly what to try (or "nothing visible yet")
   - tasks finished (`[x]`), tasks needing a manual check (`[~]`, and exactly what to check), blocked tasks and why
   - any `TEST-CHANGE:` notes or interface/schema changes, which the user should look at
   - why the loop stopped (all rounds done, blocked, failing check, usage limit)
   - checkpoint review verdict: OK / problems found (list the top ones, one line each)
   - what's next in PLAN.md, especially `[HUMAN]` tasks now waiting for the user
   - the backup taken at the start (path), in case the data needs restoring.
Do not do task work yourself in this session (ticking a `[HUMAN]` gate when the user asks is fine).
