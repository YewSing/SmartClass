# PROGRESS

Short log, newest entry at the bottom of "Log". Each entry is at most 5 lines:
`### Txx — <title> — <date>` then: Changed · Decisions · Interface/schema changes · Tests · Next.

## Blocked
<!-- Format: - Txx: <problem>, what was tried, what is needed. Remove the line when it's resolved. -->

## Next
<!-- Follow-up ideas found during tasks that are out of the current task's scope. -->

## Log

### T00 — Setup — 2026-11-08
- Changed: FR/NFR/UC docs rewritten for M1/M3/M4/M8 (commit 646f1c0); CLAUDE.md loop rules; PLAN.md; hooks, reviewer agent, /next-task, scripts/run-tasks.sh.
- Decisions: Moodle login + auto-create accounts, local admin; face self-enrolment verified against the matric card (local OCR); Present/Absent only; mod_attendance sync; Pi does detection, server does recognition; M8 quiz-based features deferred.
- Tests: 12 KB unit tests passing at start.
- Next: T01.

### T00b — Web and admin decision — 2026-11-09
- Decisions: lecturer app also runs in a browser (Expo web); small admin role with web-only screens inside it; `frontend/admin` retired after T22, T46, T96, once Shino confirms (T95).
- Changed: PLAN.md adds T05, T22, T93, T95, T96 and edits T03, T46, T89; CLAUDE.md gets the web direction and "Merging to main"; new `/prepare-merge` command.
- Next: T01.

### T00c — Week 7 priority — 2026-11-09
- Decisions: the student AI chat screen must be ready for the Week 7 demo, so T80, T93, T84, T89 now run right after the T04 checkpoint (PLAN.md section 0b). Dependencies are unchanged.
- Next: T01.
