---
description: Run the PLAN.md task loop in the background (default 30 rounds), then summarise what got done.
argument-hint: "[rounds, default 30]"
---

Start the SmartClass task loop and report back. Rounds: $ARGUMENTS (use 30 if empty).

1. Pre-flight, and fix only these if needed:
   - Must not be on `main`. If on main, stop and tell the user.
   - If there are uncommitted tracked changes, show them (`git status --short`, `git diff --stat`) and ask the user whether to commit them before starting. Don't start until the tree is clean.
2. Run `bash scripts/run-tasks.sh <rounds>` with the Bash tool using `run_in_background: true`. Don't poll; you'll be notified when it exits.
3. When it exits, read the script output, `PROGRESS.md` (Blocked, Next, and the new Log entries) and `git log --oneline` for the new commits.
4. Reply with a short report:
   - tasks finished (`[x]`), tasks needing a manual check (`[~]`, and exactly what to check), blocked tasks and why
   - any `TEST-CHANGE:` notes or interface/schema changes, which the user should look at
   - why the loop stopped (all rounds done, blocked, failing check, usage limit)
   - what's next in PLAN.md, especially `[HUMAN]` tasks now waiting for the user.
Do not do task work yourself in this session.
