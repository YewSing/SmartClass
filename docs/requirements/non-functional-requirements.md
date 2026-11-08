# Non-Functional Requirements

**Project:** Smart Classroom Management System (SmartClass) — UM FYP
**Last revised:** 2026-11-08. NFR-01–NFR-30 cover Modules 1, 3, 4 and 8 plus system-wide qualities (owner: Yew Sing). NFRs specific to Modules 2, 5, 6 and 7 are to be added by their owner (Shino) from NFR-40.

The evaluation context is **one classroom of about 20 students**, one entrance camera and one lecturer (proposal §4.9). Every figure below is measured in that context, with the backend on a laptop (development) or a VPS (UAT).

---

## Security and privacy

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-01 | Face data | The system shall keep face data only as embedding vectors. Self-enrolment selfies and matric-card photos shall be deleted within 24 hours of the verification decision. | Must Have | FR-110–FR-113 |
| NFR-02 | Face data | Unrecognised-face crops shall be deleted once resolved, or after at most 7 days. | Must Have | FR-407, FR-410 |
| NFR-03 | PDPA consent | No face data shall be captured without a recorded consent (version + timestamp). Withdrawing consent shall delete the student's embeddings at once. | Must Have | FR-109, FR-116 |
| NFR-04 | Access control | Every API endpoint shall enforce role checks on the server. Students shall only reach their own records and the courses they are enrolled in; lecturers only the courses they teach. | Must Have | FR-105, FR-807 |
| NFR-05 | Credentials | Moodle passwords shall never be stored or logged by SmartClass. Local admin passwords shall be stored as salted bcrypt hashes. | Must Have | FR-101, FR-103 |
| NFR-06 | Audit trail | Attendance overrides, face verification decisions, consent changes and role changes shall be written to an append-only audit log that no role can edit or delete. | Must Have | FR-118, FR-305 |
| NFR-07 | Transport | In the UAT deployment, all traffic between apps, the Raspberry Pi and the backend shall use HTTPS (TLS 1.2+). Each camera device shall authenticate with its own key. | Must Have | FR-402, FR-408 |
| NFR-08 | Secrets | API keys (LLM, YouTube) and the Moodle service token shall live only in server environment configuration, never in the repository or the mobile/web apps. | Must Have | FR-801, FR-805 |
| NFR-09 | Chat privacy | No API shall return a student's individual assistant chats to anyone but that student. Aggregates for lecturers shall include only topics asked by at least 3 distinct students. | Must Have | FR-808, FR-813 |

## Performance

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-10 | Recognition latency | From the backend receiving a face crop to the attendance record being written: ≤ 2 s (95th percentile). | Must Have | FR-403–FR-405 |
| NFR-11 | Device frame rate | Face detection on the Raspberry Pi shall process at least 5 frames per second. | Should Have | FR-401, FR-402 |
| NFR-12 | Feedback latency | The student's phone shall show "attendance recorded" within 5 s of the confirmed recognition. | Should Have | FR-406 |
| NFR-13 | API latency | Non-AI API requests shall respond within 500 ms (95th percentile) with 20 students and 1 lecturer active at once. | Must Have | All |
| NFR-14 | Assistant latency | The assistant shall return a complete answer within 15 s (95th percentile) under normal LLM provider conditions. | Should Have | FR-805, FR-806 |
| NFR-15 | Ingestion time | Syncing and indexing a new 50-page PDF shall complete within 2 minutes. | Should Have | FR-801, FR-802 |

## Accuracy (evaluated in functional testing)

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-16 | Face recognition | On a test with the enrolled class, at least 95% of entries by enrolled students shall be recognised, with a false-match rate of at most 1%. | Must Have | FR-403, FR-404 |
| NFR-17 | Card verification | On a test set of genuine and mismatched (selfie, card) pairs, no mismatched pair shall be auto-approved, and at least 80% of genuine pairs with a clear card photo shall be auto-approved. | Must Have | FR-111, FR-112 |
| NFR-18 | Assistant grounding | On the Q&A evaluation set, at least 80% of answers to in-syllabus questions shall be judged correct, and at least 90% of them shall carry at least one citation that supports the answer. | Must Have | FR-805 |
| NFR-19 | Off-syllabus labelling | 100% of answers to out-of-syllabus questions in the evaluation set shall be labelled as general knowledge. | Must Have | FR-806 |

## Reliability

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-20 | Moodle outage | If Moodle is unreachable, attendance shall still be recorded in SmartClass, and the Moodle sync shall retry with backoff until it succeeds, without losing data. Users already logged in shall keep working. | Must Have | FR-311, FR-312 |
| NFR-21 | LLM outage | If the LLM provider fails or times out, the assistant shall return a clear error within its timeout, and no other module shall be affected. | Must Have | FR-805 |
| NFR-22 | Idempotency | Repeated recognition events or sync calls for the same student and session shall never create duplicate attendance records. | Must Have | FR-302, FR-311 |
| NFR-23 | Device loss | If the camera device goes offline during a session, the lecturer shall see this within 60 s and can fall back to manual overrides or the backup webcam. | Should Have | FR-408, FR-409 |
| NFR-24 | Failure isolation | A failure of the face pipeline, Moodle or the LLM shall not make login, attendance viewing or the other modules unavailable. | Must Have | All |

## Usability and accessibility

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-25 | Lecturer workflow | A lecturer shall be able to open or close an attendance session within 3 taps from the dashboard. | Must Have | FR-301 |
| NFR-26 | Self-enrolment | A student shall be able to finish face self-enrolment (consent, selfies, card) within 3 minutes, guided step by step on screen. | Should Have | FR-109, FR-110 |
| NFR-27 | Touch and contrast | Interactive elements in the mobile apps shall have touch targets of at least 48×48 dp and meet WCAG 2.1 AA contrast. | Should Have | All UI |

## Maintainability, portability and testability

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-28 | LLM portability | All LLM calls shall go through one adapter configured by environment variables, so the provider (e.g. Gemini, DeepSeek, OpenAI) can be changed without code changes. | Must Have | FR-805–FR-811 |
| NFR-29 | Automated tests | Backend features of Modules 1, 3, 4 and 8 shall have automated tests that run without the camera hardware, and without Moodle or the LLM unless the test is explicitly marked as a live test. | Must Have | All |
| NFR-30 | Platform | The mobile apps shall run on Android 10+ and iOS through Expo. Push notifications are Android only; on iOS, notifications are shown in the app and by email (proposal §4.9). | Must Have | FR-406, FR-114 |

---

## Module 2, 5, 6, 7 NFRs (Owner: Shino) — *placeholder*

To be written by the module owner, starting at NFR-40.
