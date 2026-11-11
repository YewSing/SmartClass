# Requests for Shino (Modules 2, 5, 6, 7)

Things Yew Sing's modules (1, 3, 4, 8) need from Shino's modules. Each request says what is
needed, what Yew Sing's side already provides, and its status. Shino (or her Claude session):
please read this when you pull `main`, and reply by editing the **Status / reply** line of the
request, or by message to Yew Sing.

---

## R1 — Notifications for face enrolment (M2) — opened 2026-11-10

**Why:** a student self-enrols their face (FR-110). If the automatic checks fail, the submission
waits for a lecturer's review (FR-113). FR-114 says the student is told the result.
Notifications are Module 2.

**Needed from M2:** deliver two events (push, in-app or email, whichever M2 supports):

| Event | To | When | Payload |
|---|---|---|---|
| `face_enrolment.pending_review` | lecturers of the student's courses | a submission needs review | `{enrolment_id, student_name, matric_no, courses}` |
| `face_enrolment.result` | the student | a lecturer/admin decided | `{enrolment_id, status: "active" \| "rejected", reason}` |

**What Yew Sing's side provides:** `app/services/notify.py` with
`emit(event: str, user_ids: list[int], payload: dict)` (PLAN.md T44). Until M2 hooks in, it only
logs and the apps refresh their own screens. M2 replaces or wraps `emit` to deliver. The same
hook will carry `attendance.recorded` (student) and `attendance.flagged` (lecturer), listed in
`docs/requirements/functional-requirements.md` under Module 2.

**Question for Shino:** is `emit(event, user_ids, payload)` a shape that works for M2? If you
prefer a different one (e.g. with a priority level: urgent / important / general), say so here
before T44 is built.

**Status / reply:** open

---

## Open issue already raised

- `GET /lecturer/analytics` (M7) lets any lecturer read any class's analytics (NFR-04). Details
  and the suggested fix are under Module 7 in `docs/requirements/functional-requirements.md`.
