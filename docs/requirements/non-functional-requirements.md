# Non-Functional Requirements

**Project:** Smart Classroom Management System (SmartClass) — UM FYP
**Last revised:** 2026-11-21. NFR-01–NFR-30 cover Modules 1, 3, 4 and 8 plus system-wide qualities (owner: Yew Sing). NFR-40–NFR-61 cover Modules 2, 5, 6 and 7 (owner: Shino) and sit at the end of each category table.

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
| NFR-40 | Anonymity | No API shall return the identity behind an anonymous question to a lecturer or another student, and anonymous questions shall be left out of any individual-level figure shown to a lecturer. | Must Have | FR-504, FR-515, FR-713 |
| NFR-41 | Quiz integrity | The server shall not send a question's correct answer or explanation to a student's device before the question has closed (live game) or before the lecturer releases results (graded quiz). Unreleased marks and answers shall be hidden by the server, not just in the app. | Must Have | FR-611, FR-618 |
| NFR-42 | Notification content | Push and email text shall not contain marks, attendance rates or other performance details about a student. Such details are shown only after the user opens the app and signs in. | Should Have | FR-205, FR-210, FR-211, FR-711 |
| NFR-43 | Leaderboard privacy | The server shall honour each student's nickname or opt-out choice: no API shall return the real name of a student who chose a nickname or opted out to other students. | Must Have | FR-613 |

## Performance

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-10 | Recognition latency | From the backend receiving a face crop to the attendance record being written: ≤ 2 s (95th percentile). | Must Have | FR-403–FR-405 |
| NFR-11 | Device frame rate | Face detection on the Raspberry Pi shall process at least 5 frames per second. | Should Have | FR-401, FR-402 |
| NFR-12 | Feedback latency | The student's phone shall show "attendance recorded" within 5 s of the confirmed recognition. | Should Have | FR-406 |
| NFR-13 | API latency | Non-AI API requests shall respond within 500 ms (95th percentile) with 20 students and 1 lecturer active at once. | Must Have | All |
| NFR-14 | Assistant latency | The assistant shall return a complete answer within 15 s (95th percentile) under normal LLM provider conditions. | Should Have | FR-805, FR-806 |
| NFR-15 | Ingestion time | Syncing and indexing a new 50-page PDF shall complete within 2 minutes. | Should Have | FR-801, FR-802 |
| NFR-44 | Real-time updates | Live interaction events (poll votes, questions, live quiz questions and answer counts, in-app notifications) shall appear on the other users' screens within 2 s (95th percentile) with 20 students and 1 lecturer active. | Should Have | FR-213, FR-516, FR-610 |
| NFR-45 | AI quiz time | Drafting a 10-question quiz shall complete within 60 s, and automatic grading of a student's short answers within 60 s of submission (95th percentile), under normal LLM provider conditions. | Should Have | FR-601, FR-602, FR-616 |
| NFR-46 | Dashboard load | The student and lecturer dashboards shall load within 3 s (95th percentile), using Moodle data cached from the last sync. | Should Have | FR-201, FR-202, FR-203 |
| NFR-47 | Timer accuracy | The server shall lock a quiz answer or submit an attempt within 2 s of its timer ending. | Should Have | FR-608 |

## Accuracy (evaluated in functional testing)

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-16 | Face recognition | On a test with the enrolled class, at least 95% of entries by enrolled students shall be recognised, with a false-match rate of at most 1%. | Must Have | FR-403, FR-404 |
| NFR-17 | Card verification | On a test set of genuine and mismatched (selfie, card) pairs, no mismatched pair shall be auto-approved, and at least 80% of genuine pairs with a clear card photo shall be auto-approved. | Must Have | FR-111, FR-112 |
| NFR-18 | Assistant grounding | On the Q&A evaluation set, at least 80% of answers to in-syllabus questions shall be judged correct, and at least 90% of them shall carry at least one citation that supports the answer. | Must Have | FR-805 |
| NFR-19 | Off-syllabus labelling | 100% of answers to out-of-syllabus questions in the evaluation set shall be labelled as general knowledge. | Must Have | FR-806 |
| NFR-48 | Question quality | On a test of AI-drafted questions from sample course materials, at least 80% shall be judged acceptable by a lecturer without editing (clear, one correct answer, answerable). Questions labelled "from material" shall name a source page or slide. | Should Have | FR-602, FR-603 |
| NFR-49 | AI short-answer grading | On a test set of short answers marked by a lecturer, the AI's correct or incorrect decision shall match the lecturer's in at least 80% of cases. | Should Have | FR-616 |
| NFR-50 | MCQ and points | On test data, multiple-choice grading shall match the answer key, and game points and ranks shall match hand-calculated values, in 100% of cases. | Must Have | FR-612, FR-613, FR-616 |
| NFR-51 | Indicators | On test data, the attendance rate, participation counts and topic mastery calculated by Module 7 shall match hand-calculated values in 100% of cases. | Must Have | FR-702 |
| NFR-52 | At-risk rules | On a prepared test data set, each early-warning rule shall flag exactly the students it should flag, and the same rule shall not alert the same student twice. | Must Have | FR-708, FR-711 |

## Reliability

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-20 | Moodle outage | If Moodle is unreachable, attendance shall still be recorded in SmartClass, and the Moodle sync shall retry with backoff until it succeeds, without losing data. Users already logged in shall keep working. | Must Have | FR-311, FR-312 |
| NFR-21 | LLM outage | If the LLM provider fails or times out, the assistant shall return a clear error within its timeout, and no other module shall be affected. | Must Have | FR-805 |
| NFR-22 | Idempotency | Repeated recognition events or sync calls for the same student and session shall never create duplicate attendance records. | Must Have | FR-302, FR-311 |
| NFR-23 | Device loss | If the camera device goes offline during a session, the lecturer shall see this within 60 s and can fall back to manual overrides or the backup webcam. | Should Have | FR-408, FR-409 |
| NFR-24 | Failure isolation | A failure of the face pipeline, Moodle or the LLM shall not make login, attendance viewing or the other modules unavailable. | Must Have | All |
| NFR-53 | Notification failure | A failure of push or email delivery shall not block or undo the action that triggered the notification. Failed email sends shall be retried. | Must Have | FR-205, FR-210, FR-211 |
| NFR-54 | Quiz answers | A student's selected answer shall be saved within 5 s, so a lost connection or app restart does not lose it. Resubmitting the same answer shall never score a question twice. | Must Have | FR-607, FR-612 |
| NFR-55 | LLM outage (quiz) | If the LLM provider fails, quiz drafting shall show a clear error and let the lecturer add questions manually, and short answers that could not be graded shall stay "pending" and be graded when the provider recovers. Other modules shall not be affected. | Must Have | FR-601, FR-604, FR-616 |
| NFR-56 | Live game rejoin | A student who loses connection during a live game shall rejoin at the current question within 5 s of reconnecting. | Should Have | FR-610 |
| NFR-57 | Dashboard without Moodle | If Moodle is unreachable, the dashboard shall still load, showing the last synced announcements and deadlines with a "last updated" time. | Should Have | FR-203 |

## Usability and accessibility

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-25 | Lecturer workflow | A lecturer shall be able to open or close an attendance session within 3 taps from the dashboard. | Must Have | FR-301 |
| NFR-26 | Self-enrolment | A student shall be able to finish face self-enrolment (consent, selfies, card) within 3 minutes, guided step by step on screen. | Should Have | FR-109, FR-110 |
| NFR-27 | Touch and contrast | Interactive elements in the mobile apps shall have touch targets of at least 48×48 dp and meet WCAG 2.1 AA contrast. | Should Have | All UI |
| NFR-58 | In-class actions | A student shall be able to answer a live quiz question, vote in a poll or press "I Don't Understand" within 2 taps from the class screen. | Should Have | FR-512, FR-508, FR-610 |
| NFR-59 | Lecturer live tools | A lecturer shall be able to start a live poll or a live game quiz within 3 taps from the class screen. | Should Have | FR-507, FR-610 |

## Maintainability, portability and testability

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-28 | LLM portability | All LLM calls shall go through one adapter configured by environment variables, so the provider (e.g. Gemini, DeepSeek, OpenAI) can be changed without code changes. | Must Have | FR-805–FR-811 |
| NFR-29 | Automated tests | Backend features of Modules 1, 3, 4 and 8 shall have automated tests that run without the camera hardware, and without Moodle or the LLM unless the test is explicitly marked as a live test. | Must Have | All |
| NFR-30 | Platform | The mobile apps shall run on Android 10+ and iOS through Expo. Push notifications are Android only; on iOS, notifications are shown in the app and by email (proposal §4.9). | Must Have | FR-406, FR-114 |
| NFR-60 | Automated tests (M2, 5, 6, 7) | Backend features of Modules 2, 5, 6 and 7 shall have automated tests that run without the LLM, push or email services unless the test is explicitly marked as a live test. | Must Have | All |
| NFR-61 | Configuration (M2, 5, 6, 7) | Thresholds, cooldowns, scoring values, reminder times and retention periods used by Modules 2, 5, 6 and 7 shall be configuration values, not hard-coded. | Should Have | FR-215, FR-512, FR-612, FR-709 |
