---
description: Shino's loop - do exactly one plan-shino.md task (M2/M5/M6/M7) end-to-end (plan, build, test, review, commit, log), then stop.
---

You are running one round of Shino's SmartClass task loop (Modules 2, 5, 6, 7). Follow `CLAUDE.md` → "Task Loop Rules" strictly, reading `PLAN.md` as `plan-shino.md` and `PROGRESS.md` as `progress-shino.md`. Never edit Yew Sing's `PLAN.md` or `PROGRESS.md`.

1. Read `CLAUDE.md`, `plan-shino.md` (Guardrails + the task list), `progress-shino.md` (Blocked, Next, last 3 Log entries).
2. Pick the task: the first `[ ]` task, top to bottom, whose `Depends on` are all `[x]`/`[~]`, and which is not `[HUMAN]` and not listed under Blocked. No task below an unticked `[HUMAN] Checkpoint` may be picked. If none, write "No runnable task (<date>): <why>" under `## Next` in progress-shino.md, commit it as `Loop: no runnable task`, and stop.
3. Read the FRs/NFRs/UCs the task cites (`docs/requirements/`), the interfaces it consumes (`docs/interfaces.md`), and the code it touches. Check how similar things are already done (M5 `interaction_service.py`/`routers/interaction.py` is the reference for Shino-owned code: access checks, after-commit websocket events, audit, migrations). Write a short plan (5–10 bullets) for this task only, in your reply.
4. Implement it. Write the tests named in its "Done when" (test first where practical). Tests never call Moodle, the LLM, Expo Push or SMTP: mock them (respx / fakes) or replay recorded fixtures. New AI prompts get `@pytest.mark.live` cases in `backend/tests/live/` on the synthetic test course and recorded fixtures in `backend/tests/fixtures/llm/`.
5. Run `bash scripts/check.sh` and any task-specific test (`-m db`, `-m moodle`, `-m live`, E2E flow) named in "Done when". Fix until all pass. Never weaken a test to pass.
   - `[UI]` lecturer web: `cd mobile/lecturer && npm run e2e:web` (or the task's spec). `[UI]` mobile: `bash scripts/e2e-mobile.sh <student|lecturer> <flow>`. If the E2E setup itself is broken, mark the task `[~]` and say exactly what is unverified.
6. Use the `shino-reviewer` subagent with the task ID and its "Done when" line. Fix every real problem it reports, then re-run step 5. At most 2 review rounds.
7. Tick the task in `plan-shino.md`: `[x]`, or `[~]` if a manual check is still needed (say exactly what in progress-shino.md).
8. Add a ≤5-line entry at the bottom of progress-shino.md "Log": `### Sxx — <title> — <date>` then Changed · Decisions · Interface/schema changes (also add new contracts to `docs/interfaces.md`) · Tests · Next.
9. `git add` the task's files (never `.env`, materials or images) and commit with message `Sxx: <summary>` ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push (the loop script pushes).
10. Stop. Do not start another task.

If stuck after 3 genuine attempts on the same problem: revert your uncommitted changes for this task (`git stash push -u -m "Sxx failed attempt"`), mark the task `[!]`, add a line under `## Blocked` in progress-shino.md (problem, what you tried, what is needed), commit plan-shino.md + progress-shino.md as `Sxx: blocked`, and stop.

Ownership: if the task seems to need a change inside Yew Sing's modules (M1, M3, M4, M8), do not make it. Use the documented interface; if the interface is missing something, write the request in `docs/requests-for-shino.md` style under a new "Requests for Yew Sing" heading in progress-shino.md `## Next`, and build only a stub on your side.
