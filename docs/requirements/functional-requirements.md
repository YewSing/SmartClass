# Functional Requirements

**Project:** Smart Classroom Management System (SmartClass) — UM FYP
**Source of scope:** `docs/private/PROJECT PROPOSAL PAPER.pdf` (local only, git-ignored) (revised scope, Nov 2026)
**Module ownership:** M1, M3, M4, M8 → Yong Yew Sing | M2, M5, M6, M7 → Chow Shino
**Last revised:** 2026-11-09

IDs are numbered per module: `FR-1xx` = Module 1, `FR-3xx` = Module 3, and so on.
Priorities use MoSCoW. **Deferred** = in scope of the proposal but blocked on another module; not built until that module exists.

---

## Context: SPeCTRUM (Moodle) integration

UM's LMS, SPeCTRUM, runs on Moodle. Real SPeCTRUM signs users in with Microsoft 365 SSO and gets enrolments from MAYA. SmartClass can't get web-service access to the real SPeCTRUM, so it uses a **local Moodle 4.5 instance that simulates SPeCTRUM** (`backend/moodle/`). Moodle is the source of truth for:

- user accounts (students and lecturers) and their credentials,
- courses, enrolments and lecturer assignments,
- course materials uploaded by lecturers,
- the official attendance record (Moodle Attendance plugin, `mod_attendance`).

Every SmartClass feature runs in SmartClass. Moodle is only the source of data and the place finalised attendance is copied to.

---

## Module 1 — User Management (Owner: Yew Sing)

### 1A. Authentication and accounts

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-101 | The system shall authenticate students and lecturers with their SPeCTRUM (Moodle) username and password through Moodle's token-based web-service login. SmartClass shall never store the Moodle password. | Must Have | Student, Lecturer |
| FR-102 | The system shall create a SmartClass account automatically on a user's first successful Moodle login. The role (student or lecturer) shall be derived from the user's Moodle course roles. | Must Have | System |
| FR-103 | The system shall authenticate administrators with a local email and password, independent of Moodle, in the web app only. The phone apps have no administrator sign-in. | Must Have | Admin |
| FR-104 | The system shall retrieve courses, student enrolments and lecturer assignments from Moodle on login and on a manual or scheduled sync, and shall reflect enrolments added or removed in Moodle. Class lists shall not be maintained separately in SmartClass. | Must Have | System |
| FR-105 | The system shall enforce role-based access control with three roles (Student, Lecturer, Administrator), so each user can only reach the functions and data their role permits. | Must Have | System |
| FR-106 | The system shall issue a short-lived access token and a refresh token after login, and shall support logout. | Must Have | System |
| FR-107 | The system shall let users view their profile: name, matric/staff number, email, faculty and enrolled or taught courses. Moodle-sourced fields are read-only. | Should Have | All |
| FR-108 | The system shall let administrators view all accounts, deactivate or reactivate an account, and create other administrator accounts. | Should Have | Admin |

### 1B. Face data registration (self-enrolment with student-card verification)

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-109 | The system shall require a student to accept a PDPA consent notice in the mobile app before any face data is captured, and shall record the consent version and timestamp. | Must Have | Student |
| FR-110 | The system shall let a student self-enrol their face in the mobile app by taking guided selfies (several angles) and a photo of their UM matric card. | Must Have | Student |
| FR-111 | The system shall automatically verify a submission by (a) comparing the face on the matric card with the selfies against a similarity threshold, and (b) reading the matric number (and name) from the card with OCR and checking it matches the logged-in student's account. | Must Have | System |
| FR-112 | The system shall approve the submission automatically when both checks in FR-111 pass, and shall then register the face embeddings for attendance recognition. | Must Have | System |
| FR-113 | When either check in FR-111 fails, the system shall place the submission in a verification queue for lecturers of the student's courses, showing the selfie and the card side by side with the OCR result and similarity score. The lecturer shall approve or reject it with a reason. | Must Have | Lecturer |
| FR-114 | The system shall notify the student of the verification result and let a rejected student submit again. | Should Have | Student |
| FR-115 | The system shall show the student their face enrolment status: not enrolled, pending review, active or rejected (with reason). | Should Have | Student |
| FR-116 | The system shall let a student withdraw consent, which deletes their face embeddings. | Must Have | Student |
| FR-117 | The system shall let administrators act as a fallback: perform the lecturer review in FR-113, and reset a student's face data. | Should Have | Admin |
| FR-118 | The system shall record an audit entry for every face verification decision, consent change, account deactivation and role change. | Should Have | System |
| FR-119 | The system shall let lecturers open any class they teach and view its details and full list of enrolled students, with each student's matric number and face registration status. | Should Have | Lecturer |

---

## Module 2 — Dashboard and Notifications (Owner: Shino)

### 2A. Dashboards

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-201 | The system shall provide a student dashboard that displays the student's attendance status, upcoming deadlines, latest announcements, notifications and ongoing classroom activities. | Must Have | Student |
| FR-202 | The system shall provide a lecturer dashboard that displays an overview of class attendance, student participation, assessment activities and notifications. | Must Have | Lecturer |
| FR-203 | The system shall display on each dashboard only the data permitted for the user's role and enrolled or taught courses. | Must Have | System |
| FR-204 | The system shall display urgent and important notifications at the top of the dashboard, above general notifications. | Must Have | System |

### 2B. Notifications

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-205 | The system shall assign each notification one of three priority levels: urgent, important or general. | Must Have | System |
| FR-206 | The system shall list all notifications received by a user in an in-app notification feed, ordered by priority and then by time received. | Must Have | Student, Lecturer |
| FR-207 | The system shall send a push notification or email for each urgent and important notification within a configurable time (default 60 seconds) of the triggering event. General notifications shall appear in the notification feed only. | Must Have | System |
| FR-208 | The system shall deliver push notifications on Android devices. On iOS devices, the system shall deliver notifications in-app and by email. | Must Have | System |
| FR-209 | The system shall notify a student when their attendance has been recorded (event `attendance.recorded`, FR-406). | Must Have | System |
| FR-210 | The system shall notify a lecturer when a student is identified as at-risk by Module 7 (FR-709), and shall assign the notification important priority. | Must Have | System |
| FR-211 | The system shall assign important priority to, and notify students of, upcoming quiz deadlines and newly published quizzes. | Must Have | System |
| FR-212 | The system shall notify a student of the face enrolment result (event `face_enrolment.result`, FR-114), and shall notify lecturers of pending face enrolment reviews and unrecognised faces (events `face_enrolment.pending_review` and `face.unrecognised`, FR-113 and FR-407). | Should Have | System |


Interfaces Modules 1, 3, 4 and 8 expect from M2:
- `attendance.recorded` → student ("Attendance recorded for WIF3001") — FR-406
- `face_enrolment.result` → student (approved or rejected) — FR-114
- `face_enrolment.pending_review`, `attendance.flagged` → lecturer — FR-113, FR-318

Until M2 is built, these events appear as live updates inside the relevant app screens.

---

## Module 3 — Attendance Management (Owner: Yew Sing)

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-301 | The system shall open each class's attendance session automatically at its scheduled time, starting a configurable time before the class (default 15 minutes), and close it at the scheduled end. | Must Have | System |
| FR-302 | The system shall record a student as **Present**, with a timestamp, when Module 4 submits a verified recognition for that student during an open session. If that recognition comes more than a configurable time (default 15 minutes) after the class's effective start time, the status is **Late** instead. Only the first recognition counts. | Must Have | System |
| FR-303 | The system shall mark every enrolled student without a Present or Late record as **Absent** when the session closes. | Must Have | System |
| FR-304 | The system shall use four attendance statuses: Present, Late, Excused and Absent. Excused is set only by a lecturer's override (for example, for a medical certificate). | Must Have | System |
| FR-305 | The system shall let the lecturer manually override a student's status for a session, with an optional reason. Each override shall be logged with actor, old status, new status, reason (if given) and timestamp. | Must Have | Lecturer |
| FR-306 | The system shall show the lecturer a live view of an open session: who is present or late, who is not yet recognised, and the counts. It shall update without a manual refresh. | Must Have | Lecturer |
| FR-307 | The system shall keep the attendance history of every student for every session of each course. | Must Have | System |
| FR-308 | The system shall calculate each student's attendance rate per course ((Present + Late sessions) ÷ (closed sessions − Excused sessions)), so Late counts as attended and Excused doesn't count against the student. | Must Have | System |
| FR-309 | The system shall let a student view their own attendance history and attendance rate per course. | Must Have | Student |
| FR-310 | The system shall let a lecturer generate attendance reports for a session, or for a course over a date range, and export them as CSV. | Should Have | Lecturer |
| FR-311 | The system shall copy the finalised attendance of a closed session to the matching session of the course's Moodle Attendance activity (`mod_attendance`). Failed syncs shall be retried automatically. | Must Have | System |
| FR-312 | The system shall re-sync a session to Moodle when its attendance is overridden after the first sync, and shall show the lecturer each session's sync status (pending, synced, failed). A closed or overridden session is sent at once and its new status appears on the lecturer's screen without a refresh; the queue and retries remain for when Moodle is down. | Should Have | Lecturer |
| FR-313 | The system shall expose attendance records and rates through an internal read interface for Module 7 (Learning Analytics). | Must Have | System |
| FR-314 | The system shall export attendance reports as PDF. | Could Have | Lecturer |
| FR-315 | The system shall let a lecturer set the weekly schedule (day, time, room) of the classes they teach. Moodle doesn't supply a timetable, so the schedule is kept in SmartClass. | Must Have | Lecturer |
| FR-316 | The system shall let the lecturer start a class now, extend it, or end it early. These actions are audited and don't alter the weekly schedule. A change to the weekly schedule applies from the next class (at most one scheduled session per class per day); Start now covers an extra class. A class that didn't happen is confirmed "Not held" (FR-317). (Changing or cancelling one class was removed by Yew Sing on 2026-11-12.) | Must Have | Lecturer |
| FR-317 | When a session reaches its end with no recognitions and no lecturer action, the system shall not mark anyone Absent or sync to Moodle until the lecturer confirms whether the class was held. | Must Have | System, Lecturer |
| FR-318 | The system shall let an enrolled student with no attendance record flag in the app, during an open session, that they are in class but weren't recognised, and shall alert the lecturer in the app. | Must Have | Student |
| FR-319 | The system shall let the lecturer confirm a flag, recording Present or Late from the flag time, or reject it with a reason. The decision is audited and shown to the student. An unresolved flag leaves the student Absent and stays in the lecturer's list. | Must Have | Lecturer |
| FR-320 | The system shall compare synced sessions with Moodle and never silently overwrite a status changed there. It shall show the lecturer both values and let them choose. Student self-marking in Moodle stays off for these sessions. | Should Have | Lecturer |

---

## Module 4 — Facial Recognition Attendance Verification (Owner: Yew Sing)

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-401 | The system shall use a Raspberry Pi with a camera module at the classroom entrance, which captures frames only while an attendance session is open for its room. | Must Have | System |
| FR-402 | The Raspberry Pi shall detect faces locally and send only the cropped face images to the backend over an authenticated connection (per-device key). | Must Have | System |
| FR-403 | The backend shall extract a face embedding from each crop and match it against the registered embeddings of students enrolled in the session's course, accepting a match only at or above a configurable similarity threshold. | Must Have | System |
| FR-404 | The system shall confirm a student only after they are matched consistently across a configurable number of consecutive frames (default 3). | Must Have | System |
| FR-405 | The system shall submit each confirmed recognition, with timestamp and device ID, to Module 3 to record attendance. | Must Have | System |
| FR-406 | The system shall give feedback on recognition: the student is told on their phone that attendance was recorded, and the lecturer's live session view shows them as present or late. | Must Have | Student, Lecturer |
| FR-407 | The system shall keep faces that are detected but not matched as supporting evidence, not as a task for the lecturer. When a student flags (FR-318), the lecturer sees the closest unmatched face with its similarity. Lecturers are never asked to identify a face from memory. | Must Have | Lecturer |
| FR-408 | The system shall let administrators register camera devices, assign each to a room, and regenerate a device's key. Each device's online or offline status (heartbeat) shall be shown. | Should Have | Admin |
| FR-409 | The system shall support a USB webcam (Logitech) on a laptop as a backup capture device, using the same pipeline. | Should Have | System |
| FR-410 | The system shall delete unrecognised-face crops once they are resolved, or after a retention period. | Should Have | System |
| FR-411 | The Raspberry Pi shall buffer crops while the backend is unreachable and send them, with original timestamps, when the connection returns. | Could Have | System |

---

## Module 5 — Classroom Interaction (Owner: Shino)

All interactions in this module are non-graded. Graded assessments are handled by Module 6.

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-501 | The system shall allow a lecturer to open and close an interaction session for a scheduled class of a course they teach. Students enrolled in the course shall be able to participate only while the session is open. | Must Have | Lecturer |
| FR-502 | The system shall allow a student to submit a question during an open interaction session, with an option to submit it anonymously. The system shall not display the identity of an anonymous student to the lecturer or other students. | Must Have | Student |
| FR-503 | The system shall display submitted questions to the lecturer in real time and shall allow the lecturer to mark each question as answered. | Must Have | Lecturer |
| FR-504 | The system shall allow a lecturer to create a live poll with a question and two or more answer options, and to open and close voting. | Must Have | Lecturer |
| FR-505 | The system shall allow each enrolled student to vote once per poll while it is open, and shall display the poll results to the lecturer in real time. | Must Have | Student |
| FR-506 | The system shall allow a lecturer to post a live question to the class and shall display students' responses to the lecturer in real time. | Should Have | Lecturer |
| FR-507 | The system shall allow a student to send a reaction (from a predefined set) during an open session, and shall display the reaction counts to the lecturer in real time. | Should Have | Student |
| FR-508 | The system shall provide an "I Don't Understand" button that a student can select during an open session, and shall display the number of students who selected it to the lecturer in real time. | Must Have | Student |
| FR-509 | The system shall record every question, poll vote, response, reaction and "I Don't Understand" signal with the session, student and timestamp, for use by Module 7. The system shall retain the student's identity for anonymous questions for counting purposes only. | Must Have | System |

---

## Module 6 — AI-Powered Quiz and Assessment (Owner: Shino)

Interface used from M8: retrieval over the course knowledge base (FR-814), so Module 6 does not parse materials itself.
Interfaces M8 needs from M6 (deferred FR-820 to FR-824): quiz results per student per question, tagged with topic or source material, and whether the student has an active graded attempt.

### 6A. Question generation and publishing

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-601 | The system shall allow a lecturer to select one or more materials of a course they teach and specify the question type (multiple-choice or short-answer), level and the number of questions to generate. | Must Have | Lecturer |
| FR-602 | The system shall generate draft questions from the selected materials using an LLM. Each multiple-choice question shall include answer options and the correct answer, and each short-answer question shall include a suggested answer. | Must Have | System |
| FR-603 | The system shall tag each generated question with its source material and topic. | Must Have | System |
| FR-604 | The system shall allow a lecturer to review, edit, approve or delete each generated question. The system shall allow only approved questions to be published. | Must Have | Lecturer |
| FR-605 | The system shall allow a lecturer to publish a quiz from approved questions with a time limit and an open and close date and time. | Must Have | Lecturer |

### 6B. Taking quizzes and grading

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-606 | The system shall allow a student to view the published quizzes of courses they are enrolled in, on mobile devices and computers. | Must Have | Student |
| FR-607 | The system shall allow a student to make one attempt per quiz within the time limit, and shall automatically submit the attempt when the time limit expires. | Must Have | Student |
| FR-608 | The system shall automatically grade multiple-choice questions upon submission. | Must Have | System |
| FR-609 | The system shall allow a lecturer to review and score short-answer responses. | Must Have | Lecturer |
| FR-610 | The system shall provide an AI-suggested score for each short-answer response, which the lecturer can accept or change. | Could Have | System |
| FR-611 | The system shall allow a student to view their quiz score and per-question results after grading is complete. | Must Have | Student |

### 6C. Results and integration

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-612 | The system shall allow a lecturer to view quiz results, including each student's score and the class average. | Must Have | Lecturer |
| FR-613 | The system shall identify and display to the lecturer the questions answered incorrectly by more than a configurable percentage of students (default 50%). | Should Have | System |
| FR-614 | The system shall share quiz results per student per question, with the question's topic and source material, with Module 7 and Module 8. | Must Have | System |

---

## Module 7 — Learning Analytics and Early Warning (Owner: Shino)

### 7A. Engagement indicators and dashboards

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-701 | The system shall collect attendance data from Module 3 (FR-313), participation data from Module 5 (FR-509) and quiz results from Module 6 (FR-614). | Must Have | System |
| FR-702 | The system shall calculate the following indicators for each student per course: attendance rate, absence frequency, classroom participation frequency, number of questions submitted, number of "I Don't Understand" signals, and quiz scores with their trend across quizzes. | Must Have | System |
| FR-703 | The system shall display to the lecturer the indicators of each individual student in the lecturer's courses. | Must Have | Lecturer |
| FR-704 | The system shall display to the lecturer the class-level engagement trend across sessions. | Must Have | Lecturer |
| FR-705 | The system shall display to the lecturer the class assessment performance by topic and by session. | Should Have | Lecturer |
| FR-706 | The system shall display to a student their own attendance status, engagement summary and academic performance indicators. A student shall not be able to view other students' indicators. | Must Have | Student |

### 7B. Early warning

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-707 | The system shall flag a student as at-risk when any of the following conditions is met: (a) the attendance rate falls below a configurable minimum percentage; (b) the student is absent for a configurable number of consecutive sessions; (c) quiz scores decline across a configurable number of consecutive quizzes; (d) classroom participation decreases by more than a configurable percentage compared with the previous period. | Must Have | System |
| FR-708 | The system shall evaluate the early warning conditions in FR-707 after each attendance session closes and after each quiz is graded. | Must Have | System |
| FR-709 | When a student is flagged, the system shall generate an alert stating the student, the course and the condition met, and shall send it to the lecturer through Module 2 (FR-210). | Must Have | System |
| FR-710 | The system shall display to the lecturer a list of at-risk students in their courses, with the condition that triggered each flag. | Should Have | Lecturer |

> **Open issue for Shino (found 2026-11-09, not fixed because M7 is your module):** `GET /lecturer/analytics` in `backend/app/routers/analytics.py` checks that the caller is a lecturer or admin, but not that a lecturer teaches the class in `occurrence_id`. Any lecturer can read any class's analytics, including the names, matric numbers and attendance rates of its at-risk students. NFR-04 says lecturers may only reach the courses they teach.
>
> **Fix:** when the caller is a lecturer, call `await ensure_teaches_occurrence(db, actor, occurrence_id)` (from `app.core.deps`) after the "Occurrence not found" check. It returns 403 if they aren't assigned to the class. `backend/tests/test_lecturer_access.py` shows how to test it. Delete this note once it's fixed.

---

## Module 8 — Personalized Learning: AI Learning Assistant (Owner: Yew Sing)

Module 8 turns each course's lecturer materials into a course knowledge base. Students learn from it through a cited AI assistant (similar to NotebookLM). Recommendations based on quiz results depend on Module 6 and are **deferred** (FR-820–FR-824).

### 8A. Course knowledge base

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-801 | The system shall read course materials directly from the course's Moodle page (no re-upload to SmartClass), and shall detect new, changed and removed files on each sync. | Must Have | System |
| FR-802 | The system shall extract text from supported materials (PDF, PowerPoint, Word, plain text), split it into passages, create embeddings and store them in a per-course knowledge base. Each passage keeps its source file and page or slide number. | Must Have | System |
| FR-803 | The system shall let a lecturer trigger a sync of their course's materials, and shall sync automatically on a schedule. | Must Have | Lecturer |
| FR-804 | The system shall show the lecturer each material's processing status: indexed, no extractable text (e.g. scanned), unsupported or error. | Should Have | Lecturer |

### 8B. Student learning assistant

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-805 | The system shall let a student ask questions about a course they are enrolled in, and shall answer from that course's materials with citations (file and page or slide) for each claim. | Must Have | Student |
| FR-806 | When the materials do not cover a question, the system shall answer from general knowledge and clearly label the answer as not from the course materials. | Must Have | Student |
| FR-807 | The system shall restrict each student to the knowledge bases of the courses they are enrolled in. | Must Have | System |
| FR-808 | The system shall save chat sessions per student, let the student list, rename and delete them, and use the conversation history for follow-up questions. | Must Have | Student |
| FR-809 | The system shall let a student open a cited source straight from the citation: a cited PDF opens in the app at the cited page; other cited files (PowerPoint, Word) open in another app, with the citation showing the slide or section number. (Changed 2026-11-13: no passage screen in between.) | Should Have | Student |
| FR-810 | The system shall generate a summary or study guide for a selected material or topic, with citations. (The student app offers the summary only; study guide left its menu on 2026-11-14 because it read like a normal answer. The API still accepts it.) | Should Have | Student |
| FR-811 | The system shall generate non-graded flashcards and practice questions, with answers and citations, from a selected material or topic. | Should Have | Student |
| FR-812 | The system shall suggest external learning resources (YouTube videos and search keywords) for a topic the student is studying. | Could Have | Student |

### 8C. Lecturer view and integration

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-813 | The system shall show lecturers anonymised aggregates of what students ask the assistant (most-asked topics, the materials cited most often, and most-asked topics the materials don't cover). A topic is shown only when at least 3 distinct students asked about it. Lecturers shall never be able to read individual students' chats. | Should Have | Lecturer |
| FR-814 | The system shall provide an internal retrieval interface over a course's knowledge base for Module 6 (quiz generation). | Should Have | System |
| FR-815 | The system shall let a lecturer ask questions over the materials of a course they teach, through the same assistant students use and with citations, so they can check what students are told. These chats are private to the lecturer and are not counted in question trends. | Should Have | Lecturer |
| FR-816 | The system shall generate a short "before next class" summary for the lecturer from the question trends (FR-813): what to revisit, with material sections, and what the materials don't cover. It shall use only the aggregates (topics asked by at least 3 students), never individual chats. | Should Have | Lecturer |

### 8D. Deferred — depends on Module 6 quiz results

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-820 | The system shall refuse course-content help in the assistant while the student has an active graded quiz attempt in that course. | Deferred (Must) | System |
| FR-821 | The system shall analyse a student's incorrect quiz answers to identify weak topics or concepts. | Deferred (Must) | System |
| FR-822 | The system shall recommend the relevant sections of the lecturer's materials (and external resources, FR-812) for each weak topic, personalised per student. | Deferred (Must) | Student |
| FR-823 | The system shall explain why a student's quiz answer was wrong, citing the materials. | Deferred (Should) | Student |
| FR-824 | The system shall summarise, for lecturers, the topics and questions the class most often answers incorrectly, with the related material sections to revisit. | Deferred (Should) | Lecturer |

---

## Notes and assumptions

- **Moodle simulation:** FR-101 uses the simulated SPeCTRUM's username and password. Real SPeCTRUM uses Microsoft 365 SSO, so signing in against the live system would need Microsoft OAuth and approval from UM IT. This is recorded as a scope limitation and future work.
- **Face privacy:** selfies and card photos are used only for verification and are then deleted. Only embeddings are kept (NFR-01, NFR-02). Lecturers never approve a face from memory: FR-113 always shows the card next to the selfie, and attendance flags (FR-319) are checked in the room.
- **Attendance statuses:** Present, Late, Excused and Absent (FR-304), which map one-to-one to Moodle's Attendance plugin.
- **No liveness detection** (proposal §4.9). The camera is at the entrance under the lecturer's supervision.
- **Assistant language:** English only. An LLM API is required (provider set in configuration). Answers prefer course materials (FR-805) over general knowledge (FR-806).
- **Thresholds** (face similarity, consecutive frames, card-match similarity, aggregate minimum group size, retention periods) are configuration values, not hard-coded.
