# PLAN — Shino's modules (M2, M5, M6, M7)

Scope: Dashboard & Notifications, Classroom Interaction, AI Quiz & Assessment, and Learning Analytics. This is deliberately separate from [PLAN.md](PLAN.md), which remains Yew Sing's plan for M1/M3/M4/M8. Follow the same task-loop, test, E2E, interface, and progress rules in `CLAUDE.md`.

## Guardrails and integration contract

- Do not rewrite or take ownership of M1/M3/M4/M8. Consume their documented interfaces only: notification hook (`docs/requests-for-shino.md`), attendance read interface and KB retrieval (`docs/interfaces.md`).
- `AttendanceSession` is the single class-session source of truth. M5 data is keyed to `attendance_session_id`; it never starts, extends, or ends an independent class session.
- Lecturer class lifecycle controls belong in the **top session card on Dashboard**. It opens, extends, and ends the shared class session. Attendance detail remains focused on live roster, overrides, history, and SPeCTRUM sync.
- Opening a class makes attendance and interaction available; extending changes the common session end time; ending closes attendance and interaction work together. M5 must derive availability from the attendance session's `open` status and react to its public close event/state, without altering M3's close semantics.
- Preserve all existing M3 APIs, websocket events, tests, and E2E flows. Any additive cross-module contract is documented in `docs/interfaces.md` and `progress-shino.md`.

## Product and UI direction

The old isolated mock screens become a coherent “live teaching command centre”: a calm, information-dense desktop lecturer workspace that also collapses cleanly to phone cards. The dashboard session card is the operational anchor; beneath it, attendance, interaction, live quiz, at-risk signals, and notifications show only actionable state. Student screens use the same current-class context, prioritising one clear action over decorative cards. Use the existing React Native/Expo design system and navigation patterns; do not introduce a second visual system or duplicate route state.

## Work sequence

- [x] **S01 [UI] Shared class-session command card.** Depends on: existing M3 T38b.
  Done when: `mobile/lecturer` Dashboard top card handles Start now, +15 minutes, and End class (with the existing finalisation warning/confirmation); it states that attendance and interaction share this session; `AttendanceDetail` has no lifecycle controls; use existing LecturerContext session actions and preserve all attendance/sync behaviour. Add/adjust unit + Playwright/Maestro coverage for dashboard start/extend/end and absence of controls in attendance detail.
  Status: complete — lecturer unit tests, Expo web export, and Playwright browser E2E pass.

- [x] **S02 [API] M2 notification foundation and dashboard reads.** Depends on: S01.
  Done when: additive notification model, event adapter around `notify.emit`, priority mapping, deduplication, read state, authenticated feed endpoints, and dashboard aggregates exist; M3 events from R1 work without edits to M3. Moodle announcements/deadlines are read-only sync data. Tests cover recipient isolation, priorities, read operations, and duplicate suppression.
  Refresh decision: Moodle announcements/deadlines refresh only on successful Moodle login (FR-203). The snapshot includes its refresh time; Moodle tokens are never persisted. Manual/scheduled snapshot refresh is out of scope.
  Verified: `scripts/check.sh` passed (709 backend tests plus both mobile unit suites); live Moodle login/snapshot test passed; follow-up reviewer PASS. Runtime migrations and Moodle allowlist applied.

- [x] **S03 [UI] M2 role dashboards and notification centre.** Depends on: S02.
  Done when: student and lecturer dashboards satisfy FR-201/202/203/208/209 with real API state, the lecturer dashboard retains S01 as its top card, and a notification feed as bell icon(student/lecturer mobile) or in side bar (lecturer web) supports mark-one/all-read plus deep links. Old dashboard placeholders and mock data are removed only after replacement flows pass mobile and lecturer-web E2E.
  Lecturer scope clarification: Dashboard keeps the top shared-session command card and live attendance state; it intentionally does not add a Today list or a closed-session attendance summary. Closed records remain in Attendance.
  Verified: student 65/65 and lecturer 55/55 unit tests, both Expo web exports, focused lecturer Playwright dashboard/notification/live-session flows, full `scripts/check.sh` (709 backend tests plus both mobile suites), and independent design evaluation PASS after refinement.

- [ ] **S04 [API] M5 interaction session and real-time events.** Depends on: S01, S02.
  Done when: Shino-owned models/services/routes implement M5 keyed to `attendance_session_id`, access checks, anonymous-question privacy, questions/upvotes/moderation, polls, quick answers, reactions, confusion cooldown/spike, and websocket updates. Interaction is unavailable whenever the linked attendance session is not open and all live interaction closes when it closes. Tests cover lifecycle coupling, privacy, enrolment, cooldowns, live events, and audit events.

- [ ] **S05 [UI] M5 lecturer moderation and student live participation.** Depends on: S04.
  Done when: the shared live-session view exposes interaction controls/status from Dashboard, lecturers can moderate and read aggregates, students can ask/vote/react/respond/report confusion, and each state updates in real time. Post-session summary is read-only. Add lecturer web and both mobile E2E coverage.

- [ ] **S06 [API] M6 quiz authoring, delivery, and result interfaces.** Depends on: S02, M8 retrieval interface.
  Done when: quiz persistence, AI draft/review/publish workflow, game and graded attempts/timers, autosave, grading/result release, leaderboards, and M7/M8 read interfaces meet FR-601–621. Generation calls only `app.services.kb.retrieval_api.search`; quiz attempts and server timers are authoritative. Tests include permissions, timer expiry, one graded attempt, anonymous/public-result boundaries, and interfaces.

- [ ] **S07 [UI] M6 replacement lecturer and student quiz journeys.** Depends on: S06.
  Done when: legacy mock `Quiz*`, `LiveResults`, `ResultsClosed`, and student quiz placeholders are replaced with real authoring/review, live-game, graded attempt, result, and leaderboard flows. The UI distinguishes game from graded quizzes and never exposes a graded ranking. Test the happy paths in lecturer web and student mobile.

- [ ] **S08 [API] M7 indicators, access control, and early warning.** Depends on: S04, S06.
  Done when: M7 reads attendance only through `attendance_read.py`, interaction through M5's read interface, and quiz outcomes through M6's read interface. It fixes current `GET /lecturer/analytics` ownership enforcement with `ensure_teaches_occurrence`, handles Late/Excused correctly, prevents anonymous-question identity leakage, evaluates configurable rules, emits `at_risk.alert`, and audits updates. Tests cover all FR-701–715 rules and cross-lecturer denial.

- [ ] **S09 [UI] M7 lecturer analytics and student learning insights.** Depends on: S08.
  Done when: real course/student analytics replace hard-coded charts; lecturer screens show trends, evidence, at-risk actions and threshold controls; students see only their own attendance, engagement, performance, and topic mastery with “not enough data” states. Add mobile/web E2E and export coverage where implemented.

- [ ] **S10 [CHECK] Integration, visual QA, and handover.** Depends on: S03, S05, S07, S09.
  Done when: all stated checks pass, the lecturer desktop/mobile and student live-class flows are visually reviewed, no M1/M3/M4/M8 files were changed except approved additive integration wiring, and `progress-shino.md` has final interfaces, tests, and known limitations.

## Required first replies

Before S02, update only the Status / reply fields in `docs/requests-for-shino.md`:

- R1: confirm M2 will adapt the existing `notify.emit(event, user_ids, payload)` hook, with M2 resolving priority/title/message/link.
- R2: confirm M7 will use `attendance_read.py` and will fix the existing access/control calculation defects as S08.
