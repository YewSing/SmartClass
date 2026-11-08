---
description: Do exactly one PLAN.md task end-to-end (plan, build, test, review, commit, log), then stop.
---

You are running one round of the SmartClass task loop. Follow `CLAUDE.md` → "Task Loop Rules" strictly.

1. Read `CLAUDE.md`, `PLAN.md`, `PROGRESS.md` (Blocked + last 3 log entries).
2. Pick the task: the first `[ ]` task, top to bottom, whose `Depends on` are all `[x]`/`[~]`, and which is not `[HUMAN]` and not listed under Blocked. If none, write "No runnable task" under `## Next` in PROGRESS.md and stop.
3. Read the FRs/NFRs/UCs the task cites and the code it touches. Write a short plan (5–10 bullets) for this task only, in your reply.
4. Implement it. Write the tests named in its "Done when" (test first where practical).
5. Run `bash scripts/check.sh` and any task-specific test (`-m db`, `-m moodle`, `-m live`, E2E flow) named in "Done when". Fix until all pass. Never weaken a test to pass.
6. Use the `reviewer` subagent with the task ID and its "Done when" line. Fix every real problem it reports, then re-run step 5. At most 2 review rounds.
7. Tick the task in PLAN.md: `[x]`, or `[~]` if a manual check is still needed (say what in PROGRESS.md).
8. Add a ≤5-line entry to PROGRESS.md "Log" (Changed · Decisions · Interface/schema changes · Tests · Next).
9. `git add` the task's files (never `.env`, materials or images) and commit with message `Txx: <summary>` ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push (the loop script pushes).
10. Stop. Do not start another task.

If stuck after 3 genuine attempts on the same problem: revert your uncommitted changes for this task (`git stash push -u -m "Txx failed attempt"`), mark the task `[!]`, add a line under `## Blocked` (problem, what you tried, what is needed), commit PLAN.md + PROGRESS.md as `Txx: blocked`, and stop.
