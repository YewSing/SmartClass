# Non-Functional Requirements

**Project:** Smart Classroom Management System (SmartClass) — UM FYP
**Companion document:** `functional-requirements.md`
**Last revised:** 2026-11-10

IDs run in one sequence, `NFR-01` to `NFR-24`, across all categories. They are grouped by quality attribute, not by module, and apply to the whole system. Priorities use MoSCoW (Must Have, Should Have, Could Have).
Targets are for the evaluation setting: one classroom of about 20 students on the simulated SPeCTRUM (Moodle 4.5) instance.

---

## 1. Security

| ID | Description | Priority | Linked FR |
|----|-------------|----------|-----------|
| NFR-01 | The system shall delete the selfies and matric card photo of a face enrolment once verification is complete. Only face embeddings shall be kept. | Must Have | FR-110 – FR-112 |
| NFR-02 | The system shall store face embeddings so that only the recognition service can read them. No API shall return them, and they shall be deleted when the student withdraws consent. | Must Have | FR-112, FR-116 |
| NFR-03 | The system shall encrypt all communication between the apps, Raspberry Pi devices and backend (HTTPS/TLS, WSS). | Must Have | FR-402 |
| NFR-04 | The system shall never store Moodle passwords, shall store administrator passwords only as salted hashes, and shall use short-lived access tokens. | Must Have | FR-101, FR-103, FR-106 |
| NFR-05 | The system shall check role and course-level access on the server for every request, and validate all input and uploaded files, so a user cannot reach data outside their role and courses. | Must Have | FR-105, FR-203, FR-706, FR-807 |
| NFR-06 | The system shall not reveal the identity of an anonymous question's author to lecturers or other students, and lecturers shall not be able to read individual students' assistant chats. | Must Have | FR-502, FR-509, FR-813 |
| NFR-07 | Each Raspberry Pi shall authenticate with its own revocable key. Secrets (database credentials, LLM API key, device keys) shall be kept in environment configuration, not in the source code. | Must Have | FR-402, FR-408 |

---

## 2. Usability

| ID | Description | Priority | Linked FR |
|----|-------------|----------|-----------|
| NFR-08 | The system shall guide a student through face enrolment step by step, so a first-time student can finish within 5 minutes. | Should Have | FR-109, FR-110, FR-115 |
| NFR-09 | The system shall let users reach frequent tasks (dashboard, submitting a question, voting, starting a quiz, asking the assistant) within three taps or clicks. The web and mobile apps shall use consistent layout and terminology. | Should Have | FR-201, FR-502, FR-505, FR-607, FR-805 |
| NFR-10 | A new user shall be able to complete the main tasks without training. Error messages shall be in plain language and tell the user what to do next. | Should Have | — |

---

## 3. Reliability

| ID | Description | Priority | Linked FR |
|----|-------------|----------|-----------|
| NFR-11 | The system shall save a confirmed attendance record before telling the user it was recorded, and shall not record a student twice for one session. | Must Have | FR-302, FR-405, FR-406 |
| NFR-12 | The system shall retry failed attendance syncs to Moodle automatically and shall not lose finalised attendance data while Moodle is unreachable. | Must Have | FR-311, FR-312 |
| NFR-13 | The system shall save quiz answers as the student answers, and the server shall enforce the time limit, so a lost connection does not lose answers or extend the time. | Must Have | FR-607 |
| NFR-14 | The system shall keep attendance and classroom interaction working when an external service (LLM provider, Moodle, push service) is unavailable, and shall show a clear message for the affected feature. | Must Have | FR-207, FR-602, FR-805 |

---

## 4. Performance

| ID | Description | Priority | Linked FR |
|----|-------------|----------|-----------|
| NFR-15 | In the evaluation, face recognition shall automatically identify at least 80% of enrolled students at the default threshold. Students who are not recognised shall be handled through lecturer review. | Must Have | FR-403 |
| NFR-16 | The system shall show a recognised student as present on the lecturer's live view within 10 seconds of the student appearing in front of the camera, and classroom interaction events (questions, votes, reactions, "I Don't Understand") within 3 seconds, with 20 students taking part. | Must Have | FR-306, FR-405, FR-503 – FR-508 |
| NFR-17 | The system shall respond to ordinary requests within 3 seconds, and dashboards and analytics pages shall load within 5 seconds, under normal load. | Must Have | FR-201, FR-202, FR-703 |
| NFR-18 | The system shall generate a draft of up to 10 quiz questions within 90 seconds, and the learning assistant shall give an answer within 15 seconds. | Should Have | FR-602, FR-805 |

---

## 5. Accessibility

| ID | Description | Priority | Linked FR |
|----|-------------|----------|-----------|
| NFR-19 | The web app shall follow WCAG 2.1 Level AA where practicable (text contrast, keyboard navigation, labelled fields and icons for screen readers). The mobile apps shall use touch targets of at least 48 dp and respect the device font size. | Should Have | — |
| NFR-20 | The system shall not use colour as the only way to show a status. Present or absent, notification priority and at-risk flags shall also use text or an icon. | Must Have | FR-205, FR-304, FR-710 |
| NFR-21 | A student who cannot use face recognition shall still be able to be marked present through lecturer review or manual override, and face enrolment shall have an administrator fallback. | Must Have | FR-113, FR-117, FR-305, FR-407 |

---

## 6. Scalability

| ID | Description | Priority | Linked FR |
|----|-------------|----------|-----------|
| NFR-22 | The system shall work with one classroom of about 20 students in the evaluation, and shall support up to 100 concurrent users on a single server without code changes. | Should Have | — |
| NFR-23 | The system shall run heavy work (face embedding, material indexing, LLM calls, Moodle sync) as background tasks, so it does not slow down ordinary requests. | Should Have | FR-403, FR-802, FR-311, FR-602 |
| NFR-24 | The system shall let new courses, users, rooms and cameras be added through Moodle sync or the administrator interface, and shall keep thresholds and retention periods as configuration values, without code changes. | Should Have | FR-104, FR-408, FR-707 |

---