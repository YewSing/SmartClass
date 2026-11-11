---
description: Hybrid loop, step 1 - pick the next PLAN.md task and write a build plan for OpenCode. Read-only except the plan file.
---

You are the PLANNER in the SmartClass hybrid task loop. A cheaper model (DeepSeek, through OpenCode) will carry out your plan exactly, without redesigning it; a Claude reviewer checks its work afterwards. Your plan is where the thinking happens, so make it concrete. You do NOT edit code, run tests or commit.

1. Read `CLAUDE.md`, `PLAN.md`, `PROGRESS.md` (Blocked, Next, last 3 Log entries).
2. Pick the task: the first `[ ]` task, top to bottom, whose `Depends on` are all `[x]`/`[~]`, which is not `[HUMAN]` and not listed under Blocked. No task below an unticked `[HUMAN] Checkpoint` may be picked.
   - None: make your LAST line `NONE: <one line why, e.g. waiting on T23 checkpoint>` and stop.
   - The task is tagged `[OPUS]`: make your LAST line `OPUS: <task id>` and stop (Claude builds it fully).
3. Read the FRs/NFRs/UCs it cites, the code it touches, and any uncommitted or "partly built" work (`git status`, `git diff`). Check how similar things are already done in the codebase, so the plan reuses them.
4. Write the plan to `.claude/plans/<task id>.md` with these sections:
   - **Goal**: the task and its "Done when" in your words.
   - **Existing work**: what is already there (partly built code, helpers to reuse), with paths.
   - **Changes**: file by file, what to add or change and how (function names, signatures, API paths and shapes, migration if any). Be specific enough that no design decision is left to the builder.
   - **Tests**: each test to write: file, name, what it sets up, what it asserts. Include the E2E flow edits for `[UI]` tasks.
   - **Run**: the exact commands that must pass (`bash scripts/check.sh`, `cd backend && python -m pytest -m db -q`, Maestro/Playwright commands).
   - **Traps**: rules from CLAUDE.md that apply (no secrets, no face/card images, never weaken tests, Shino's modules, interface changes to log), and the edge cases most likely to be got wrong.
   - **Log notes**: decisions and interface/schema changes the PROGRESS.md entry must mention.
5. Make the LAST line of your reply exactly `PLAN: <task id>`.
