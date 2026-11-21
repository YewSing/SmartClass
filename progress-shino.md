# PROGRESS — Shino's modules (M2, M5, M6, M7)

Short log for [plan-shino.md](plan-shino.md), newest entry at the bottom of "Log". Each entry is at most 5 lines:
`### Sxx — <title> — <date>` then: Changed · Decisions · Interface/schema changes · Tests · Next.
Yew Sing's log is [PROGRESS.md](PROGRESS.md); never edit it. Test removals need a line `TEST-CHANGE: <test> - <why>` here.

## Blocked
<!-- Format: - Sxx: <problem>, what was tried, what is needed. Remove the line when it's resolved. -->

## Next
<!-- Follow-up ideas found during tasks that are out of the current task's scope. -->

### Requests for Yew Sing
<!-- Interface gaps in M1/M3/M4/M8 that a task needed. Copy each to docs/requests-for-shino.md style when sending. -->

## Log

### S01 — Shino task loop — 2026-11-21
- Changed: added `scripts/shino/run-tasks.sh` (same engine as `scripts/run-tasks.sh`, pointed at plan-shino.md / progress-shino.md), `/shino-run-plan`, `/shino-next-task`, `/shino-plan-task`, the `shino-reviewer` agent and `scripts/shino/opencode/` prompts.
- Decisions: fresh start; earlier M2/M5/M6/M7 code is removed in S02, not reused. Both loops share `.claude/.loop.lock`, so only one runs at a time (they share the test DB).
- Interface changes: `scripts/test_guard.py` also accepts `TEST-CHANGE:` in progress-shino.md (additive).
- Tests: `backend/tests/test_shino_loop_script.py`.
