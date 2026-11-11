A senior Claude engineer (the coach) read your work, the plan and the failures, and found the root cause. Its diagnosis and exact fix steps are below.

Follow its FIX steps exactly and in order, even where they differ from what you tried before. If a step clearly cannot work, say why in one line and do the closest thing that does. The hard rules from the start of this session still apply: never weaken or skip a test, never read `backend/.env` or face/card images, no git commit/push/stash/reset/checkout, and do not run `bash scripts/check.sh` (the loop runs it).

Then run the commands under RUN (or the plan's **Run** commands) until they pass. Do not tick the task, write PROGRESS.md or commit. Make the LAST line of your reply `TASK: <task id>` (or `TASK: STUCK <task id>` with a short reason if you still cannot fix it).

---
