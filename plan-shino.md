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

Global UI Design Guidelines — Application-Wide Design System

Use the attached screenshot as the primary visual reference for the overall design language of the entire application.

This design guideline applies to ALL pages, modules, dashboards, forms, tables, dialogs, navigation elements, and interactive components across the application.

The screenshot should be treated as a reference for visual styling, typography, spacing, colors, and component appearance — NOT as a reference for page content or information architecture.

The goal is to establish a consistent, modern, clean, and professional visual identity throughout the entire application.

1. Overall Design Philosophy

Adopt a modern, minimalist educational SaaS dashboard aesthetic.

The overall interface should feel:

Clean and professional.
Modern and lightweight.
Friendly and approachable.
Well-structured and easy to navigate.
Consistent across all pages and modules.
Visually balanced without unnecessary decoration.

Prioritise usability, readability, consistency, and clear visual hierarchy.

Avoid overly complicated layouts, excessive decorative elements, heavy shadows, unnecessary gradients, and visually overwhelming components.

2. Color System

Maintain a consistent application-wide color palette based on the reference screenshot.

Primary colors:

Primary blue for important actions, navigation highlights, links, and interactive elements.
White for the main page background.
Very light grey or cool grey for secondary backgrounds and subtle visual separation.
Dark navy or near-black for primary text.
Muted grey for secondary text, descriptions, and timestamps.

Semantic colors:

Green for success, active, online, and live states.
Red for errors, destructive actions, and important warnings.
Amber or yellow for pending states and attention indicators.
Blue for informational states.

Use soft tinted backgrounds for status indicators and highlighted components.

Keep the color palette consistent across all pages. Do not introduce unrelated colors without a functional reason.

3. Typography System

Typography must be consistent throughout the entire application.

Use a clean, modern sans-serif font that matches the reference screenshot and the existing application.

Establish a clear typography hierarchy:

Page titles: Medium to semibold, clearly distinguishable without being excessively large.
Section headings: Semibold with moderate font sizes.
Subheadings: Medium weight.
Body text: Regular weight for comfortable reading.
Supporting descriptions: Smaller font sizes with muted colours.
Labels and metadata: Compact and readable.
Buttons: Medium font weight.

Important typography rules:

Do NOT make every text element bold.
Avoid excessively heavy font weights.
Use regular and medium weights for most content.
Reserve semibold or bold for important headings and key information.
Use font size, weight, colour, and spacing to create hierarchy instead of relying on bold typography alone.
Maintain consistent line heights and text spacing.

The interface should look refined and readable rather than thick, heavy, or visually crowded.

4. Spacing & Layout System

Use a consistent spacing system across all pages.

Maintain consistent horizontal page margins.
Use balanced vertical spacing between sections.
Keep related elements visually grouped.
Align headings, content, and actions consistently.
Avoid unnecessary empty space.
Avoid overcrowding content.
Use whitespace to establish hierarchy and improve readability.
Maintain consistent internal padding across similar components.

Layouts should be responsive and adapt naturally to different screen sizes.

Do not force every page into the same layout. Each page may have its own information architecture, but the spacing, alignment principles, and visual language should remain consistent.

5. Cards & Containers

Follow the lightweight container style shown in the reference screenshot.

Preferred styling:

White backgrounds.
Subtle light-grey borders.
Moderate corner radius.
Minimal or no shadows.
Consistent border thickness.
Soft tinted backgrounds for highlighted content.
Consistent padding and spacing.

Avoid:

Heavy shadows.
Thick borders.
Excessively rounded containers.
Too many nested cards.
Putting every individual element inside a separate card.

Use cards when they help group related information, not simply to decorate the page.

6. Buttons & Interactive Components

All buttons and interactive elements should follow a consistent design language.

Primary buttons:

Primary blue background.
White text.
Clear visual emphasis.
Consistent height and padding.

Secondary buttons:

White or light background.
Subtle border.
Dark text.

Tertiary buttons:

Minimal styling.
Text buttons or simple icon buttons where appropriate.

Interactive states:

Default.
Hover.
Active.
Selected.
Disabled.
Loading.
Success.

Use subtle transitions and clear feedback.

Ensure buttons have consistent corner radii, typography, padding, and alignment throughout the application.

Not every button should be visually prominent. Establish a clear distinction between primary, secondary, and tertiary actions.

7. Icons & Visual Elements

Use a consistent icon style throughout the application.

Prefer clean, minimal outline icons.
Use consistent icon sizes and stroke weights.
Align icons properly with their labels.
Use icons to improve clarity, not merely for decoration.
Use small status indicators where appropriate.
Avoid mixing unrelated icon styles.

Icons should feel like part of one unified design system.

8. Badges, Status Indicators & Labels

Use compact and subtle badges for statuses and categories.

Examples include:

Active
Completed
Pending
Live
Available
Unavailable

Use soft background colors with appropriately contrasting text.

Avoid oversized or overly saturated badges.

Maintain consistent badge heights, padding, typography, and corner radii across all modules.

9. Forms, Inputs & Tables

Apply the same visual language to all forms, input fields, dropdowns, checkboxes, radio buttons, and tables.

Forms:

Clean input fields with subtle borders.
Consistent heights and padding.
Clear labels and helper text.
Consistent spacing between fields.
Clearly distinguishable focus and error states.

Tables:

Clean and readable layouts.
Subtle dividers.
Clear column headings.
Appropriate row spacing.
Avoid excessive borders and unnecessary decoration.

All components should feel visually consistent regardless of which module they belong to.

10. Responsive Design

The application must maintain a consistent design language across desktop, tablet, and mobile.

Use responsive layouts appropriate to the content.
Maintain readable typography at different screen sizes.
Ensure consistent spacing and alignment.
Adapt multi-column layouts naturally on smaller screens.
Prevent horizontal overflow.
Ensure interactive elements have comfortable touch targets.
Keep navigation and important actions accessible.

Do not simply shrink desktop layouts to fit mobile. Adapt the layout while preserving the same visual identity.

11. Consistency Across the Entire Application

This is one of the most important requirements.

Every page should look like it belongs to the same application.

Maintain consistency in:

Typography and font weights.
Primary and secondary colors.
Page backgrounds.
Spacing and alignment.
Border radius.
Card and container styling.
Button appearance.
Icon style.
Input field styling.
Badges and status indicators.
Hover, focus, and active states.
Modal and popup appearance.

Individual pages may have different layouts depending on their functionality, but they must share the same underlying visual design language.

Avoid introducing a completely different visual style when developing new pages or modules.

12. Implementation Guidelines

Before making UI changes:

Inspect the existing application and identify its current design patterns.
Use the attached screenshot as the primary visual styling reference.
Identify reusable components and existing styles.
Reuse existing components wherever possible.
Consolidate inconsistent styling where necessary.
Apply the design guidelines consistently across the requested pages.
Avoid unnecessarily changing existing functionality or application logic.

Where appropriate, establish reusable design tokens or shared components for colors, typography, spacing, buttons, cards, inputs, and badges.

Do not duplicate different styling rules for components that should look the same.

Final requirement: Treat this as the application's global visual design standard, not a page-specific redesign. Every existing and newly developed page should follow this design language while retaining its own appropriate content structure and functionality.

## Work sequence

- [~] **S01 [UI] Shared class-session command card.** Depends on: existing M3 T38b.
  Done when: `mobile/lecturer` Dashboard top card handles Start now, +15 minutes, and End class (with the existing finalisation warning/confirmation); it states that attendance and interaction share this session; `AttendanceDetail` has no lifecycle controls; use existing LecturerContext session actions and preserve all attendance/sync behaviour. Add/adjust unit + Playwright/Maestro coverage for dashboard start/extend/end and absence of controls in attendance detail.
  Status: `[~]` done but optional manual phone/Maestro confirmation still pending (progress-shino.md, 2026-11-20); lecturer unit tests, Expo web export, and Playwright browser E2E (`mobile/lecturer/e2e-web/live-session.spec.js`, `desktop.spec.js`) pass.
  Test map: lecturer web E2E `mobile/lecturer/e2e-web/`; backend tests for S02/S04 in `backend/tests/test_notifications.py`, `test_dashboard_moodle.py`, `test_interaction.py`; student Maestro flow `mobile/student/e2e/interaction.yaml` (+ `interaction_fixture.py`, `interaction.setup.sh`) — emulator run waived for S05 (Maestro driver install timed out); completed via Playwright + unit suites + responsive review.

- [x] **S02 [API] M2 notification foundation and dashboard reads.** Depends on: S01.
  Done when: additive notification model, event adapter around `notify.emit`, priority mapping, deduplication, read state, authenticated feed endpoints, and dashboard aggregates exist; M3 events from R1 work without edits to M3. Moodle announcements/deadlines are read-only sync data. Tests cover recipient isolation, priorities, read operations, and duplicate suppression.
  Refresh decision: Moodle announcements/deadlines refresh only on successful Moodle login (FR-203). The snapshot includes its refresh time; Moodle tokens are never persisted. Manual/scheduled snapshot refresh is out of scope.
  Verified: `scripts/check.sh` passed (709 backend tests plus both mobile unit suites); live Moodle login/snapshot test passed; follow-up reviewer PASS. Runtime migrations and Moodle allowlist applied.

- [x] **S03 [UI] M2 role dashboards and notification centre.** Depends on: S02.
  Done when: student and lecturer dashboards satisfy FR-201/202/203/208/209 with real API state, the lecturer dashboard retains S01 as its top card, and a notification feed as bell icon supports mark-one/all-read plus deep links. Old dashboard placeholders and mock data are removed only after replacement flows pass mobile and lecturer-web E2E.
  Lecturer scope clarification: Dashboard keeps the top shared-session command card and live attendance state; it intentionally does not add a Today list or a closed-session attendance summary. Closed records remain in Attendance.
  Verified: student 65/65 and lecturer 55/55 unit tests, both Expo web exports, focused lecturer Playwright dashboard/notification/live-session flows, full `scripts/check.sh` (709 backend tests plus both mobile suites), and independent design evaluation PASS after refinement.

- [x] **S04 [API] M5 interaction session and real-time events.** Depends on: S01, S02.
  Done when: Shino-owned models/services/routes implement M5 keyed to `attendance_session_id`, access checks, anonymous-question privacy, questions/upvotes/moderation, polls, quick answers, reactions, confusion cooldown/spike, and websocket updates. Interaction is unavailable whenever the linked attendance session is not open and all live interaction closes when it closes. Tests cover lifecycle coupling, privacy, enrolment, cooldowns, live events, and audit events.
  Verified: 15 focused interaction tests, 81 interaction/session/access regressions, final reviewer PASS, and full `scripts/check.sh` exit 0 (724 backend tests plus both mobile suites). Development migration `f5a6b7c8d9e0` applied; legacy tables preserved.

- [x] **S05 [UI] M5 lecturer moderation and student live participation.** Depends on: S04.
  Done when: the shared live-session view exposes interaction controls/status from Dashboard, lecturers can moderate and read aggregates, students can ask/vote/react/respond/report confusion, and each state updates in real time. Post-session summary is read-only. Add lecturer web and both mobile E2E coverage.
  Verification clarification: Shino waived emulator testing for this task. Use the seeded lecturer Playwright flow, both app unit suites and web exports, responsive visual review, and the repository check.
  Verified: seeded lecturer Playwright passed, student 70/70 and lecturer 55/55 unit tests passed, both web exports passed, independent responsive review passed, and full `scripts/check.sh` exited 0 with 724 backend tests.

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
