# PROGRESS-SHINO

Short log for Shino's modules (M2, M5, M6, M7). Newest entry at the bottom of "Log". Each entry is at most 5 lines:
`### Sxx — <title> — <date>` then: Changed · Decisions · Interface/schema changes · Tests · Next.

Counterpart of `PROGRESS.md` (Yew Sing's M1/M3/M4/M8 log). Same conventions: test removals/skips need a `TEST-CHANGE:` line here (checked by Shino's own `scripts/shino/test_guard.py` copy, not Yew Sing's); shared interface or schema changes are noted in the entry; every schema change ships an Alembic migration chained after the single current head. Yew Sing's loop scripts (`scripts/run-tasks.sh`, `scripts/test_guard.py`, `PLAN.md`, `PROGRESS.md`) are never modified from this plan.

## Blocked
<!-- Format: - Sxx: <problem>, what was tried, what is needed. Remove the line when it's resolved. -->

## Next
<!-- Follow-up ideas found during tasks that are out of the current task's scope. -->
- Reply to R1 and R2 in `docs/requests-for-shino.md` (S10 and S40 cover both, but a reply before Yew Sing builds T44 decides the `emit` shape early — he asked for it in R1).
- `GET /lecturer/analytics` ownership hole (any lecturer reads any class's analytics, NFR-04) and the "counts only `present`" drift are written up under Module 7 in `docs/requirements/functional-requirements.md`; fix lands in S40, after S02 pins the current behaviour.
- The two student endpoints in `routers/analytics.py` (`/student/me/attendance`, `/student/me/attendance/summary`) are dead code since T39 (the app uses T32's `/student/me/attendance/courses`); S40 removes them.
- Depends on Yew Sing's side: T44 (`notify.emit`, currently `[ ]` in PLAN.md) before S10; T43 (attendance flags) before the `attendance.flagged` call site in S12; T82's live-suite conventions for any S30/S33 LLM work.
- Migration heads: before the first migration, run `alembic heads` and chain after the single current head (Yew Sing's last note: `d1e2f3a4b5c6` after the fyp2-m8 → fyp2-loop merge).
- Dashboards (FR-201/FR-202) are scheduled last (section 5) so they aggregate real data from M5/M6/M7 instead of stubs; the source of "latest announcements" is an open decision to make with Yew Sing in S60.

## Log

### S00 — Plan generated — 2026-11-13
- Changed: `PLAN-SHINO.md` (35 tasks, S01–S71) and this file created for Shino's modules, mirroring `PLAN.md`'s format and the CLAUDE.md task-loop rules.
- Decisions: build order is notifications (M2 backbone) → interaction (M5) → quiz (M6) → analytics (M7) → dashboards (M2 rest) so each section builds on real data and no dashboard ships with stubs; S02 characterises the old `analytics.py` before anything rebuilds it (same pattern as Yew Sing's T02); S01 gives Shino her own loop under `scripts/shino/` (or manual one-task-per-session) and never touches Yew Sing's `scripts/run-tasks.sh` / `scripts/test_guard.py` / `PLAN.md` / `PROGRESS.md`.
- Interface/schema: none yet (setup).
- Tests: none yet. Starting state on this date: check.sh ~555 passing on Yew Sing's tree; `routers/analytics.py` is the only Shino-owned backend code; M5/M6 have no backend, only mock screens (student Participation/PartSessionPerf, lecturer QuizList/CreateQuiz/LiveResults/ResultsClosed/Breakdown).
- Next: S01.
