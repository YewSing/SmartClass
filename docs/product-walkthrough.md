# What SmartClass Will Do

A plain-language picture of the finished plan for Yew Sing's modules (M1, M3, M4, M8). Most of it isn't built yet. The AI chat backend, Moodle and face recognition already exist in some form.

**How to use this page:** read it as if you were each person using the app. If something isn't what you pictured, tell Claude which line, and the plan gets changed before that part is built. Start with "Questions for you" at the end.

---

## The big picture

- **SPeCTRUM stays the source of truth.** We use a local Moodle that imitates it. Accounts, courses, class lists and lecturers' files all come from there, and nobody retypes them in SmartClass.
- **Every feature runs in SmartClass.** Moodle only supplies data and receives the final attendance.
- **Real SPeCTRUM is not connected.** It uses Microsoft login and needs UM IT's approval, so this is recorded as a limitation and future work.

| Who | Where they use it | How they sign in |
|---|---|---|
| Student | Phone app | SPeCTRUM username and password |
| Lecturer | Phone app and browser (same app) | SPeCTRUM username and password |
| Admin | Browser only | Separate email and password |

---

## Student

**First time**
1. Signs in with SPeCTRUM details. The account is created automatically, and their courses appear.
2. Opens Profile → Face enrolment and accepts the PDPA consent.
3. Takes 3–5 selfies, then a photo of their matric card.
4. A bad card photo gets a specific message, such as "Glare is covering your card details. Tilt the card away from the light and retake." After 2 blocked attempts they can choose "submit anyway".
5. The system compares the selfie with the card photo, and reads the matric number from the card.
   - Both pass: approved straight away.
   - Either fails: goes to a lecturer, and the student sees "pending review".
6. The photos are deleted after the decision. Only the face numbers (embeddings) are kept.
7. The student can withdraw consent at any time, which deletes their face data at once.

**Going to class**
1. Walks past the camera at the door while the session is open. They don't need to touch their phone.
2. Sees "attendance recorded" in the app, while the app is open. Push notifications come with Shino's M2.
3. If the camera missed them, taps "I'm here but wasn't recognised". The lecturer checks in the room and confirms.
4. Can check their attendance rate and history per course.

**Studying with the AI**
1. Opens the Assistant tab, picks an enrolled course, and starts or continues a chat. Other courses' materials can't be reached.
2. Asks a question. The answer cites the file and page or slide, and tapping a citation opens the source there.
3. If the materials don't cover it, the answer says so and is labelled as general knowledge.
4. Follow-up questions work, like "what about its disadvantages?".
5. Can rename and delete chats. No one else can read them, including lecturers.
6. Can generate a summary or study guide, flashcards, and non-graded practice questions.
7. Optional, if time allows: YouTube suggestions.

---

## Lecturer

**Attendance in class**
1. Sets each class's weekly day, time and room once. The session then opens by itself, 15 minutes before class.
2. Can start a class now (an extra or make-up class), extend it or end it early. Editing the weekly time applies from the next class. A class that didn't happen is confirmed as "Not held".
3. Watches a live list of Present, Late and not yet recognised, without refreshing.
4. Gets an in-app alert when a student flags "I'm here but wasn't recognised". The alert shows the student's name and matric number, plus the closest unmatched camera photo if there is one. The lecturer checks in the room, by asking for a raised hand or the matric card, then confirms or rejects. Lecturers are never asked to recognise a face from memory.
5. Can change any student's status at any time, and must give a reason. Every change is logged.
6. The session closes at the scheduled end, or when the lecturer ends it. Everyone without a record becomes Absent. If nothing was recorded and the lecturer did nothing, for example on a public holiday, nobody is marked Absent until the lecturer says whether the class was held.
7. Attendance is copied to Moodle automatically as soon as the class ends, and the label turns from pending to synced (or failed) by itself, with a Retry button. If Moodle is down, nothing is lost.
8. If someone changed a status directly in Moodle, it's never overwritten silently. The lecturer sees both values and chooses. Students can't mark themselves in Moodle for these sessions.
9. Can export a CSV for a session or a date range.

**Other jobs**
- **Face verification queue:** sees the selfie and card side by side with the system's result, then approves or rejects with a reason. Lecturers of any of that student's courses can do this.
- **Course materials:** uploads files to SPeCTRUM as usual. SmartClass picks them up automatically, or through a Sync button. A status list shows which files the AI can read.
- **Question trends:** sees three lists: most-asked topics, most-cited materials, and most-asked topics the materials don't cover. Topics appear only when at least 3 students asked, with no names or question text.
- **Before next class summary:** a short AI note on what to revisit and what the materials don't cover, built only from those anonymous lists.
- **Ask my materials:** chats with the same AI students use, with citations, to check what students are being told. These chats stay private and don't count in the trends.

**Phone or browser:** the same features and data. The browser has a side menu and a wider layout.

---

## Admin

A small role for jobs that don't suit a lecturer, in the browser only:
- View accounts, deactivate or reactivate them, and create other admins.
- Act as a fallback for the face verification queue, and reset a student's face data.
- View the audit log, and check or start the Moodle sync.
- Register door cameras, and issue or replace their keys.

The old `frontend/admin` site is deleted after these screens exist. Shino has confirmed she doesn't need it.

---

## The door camera

- A Raspberry Pi with a camera detects faces and sends only the cropped faces to the server. The server does the recognition.
- A student must be matched 3 frames in a row, and must be enrolled in that class's course. The laptop webcam works as a backup.
- There is no check against someone holding up a photo (no liveness detection). The lecturer's supervision is the safeguard, as the proposal states.

---

## Not coming from this plan

| What | Why |
|---|---|
| Push notifications, email, dashboards | Shino's M2. Until then, updates only show inside the app |
| Live polls, reactions, "I don't understand" | Shino's M5 |
| Graded quizzes and AI question drafting | Shino's M6. The quiz screens in the lecturer app stay a mock-up |
| Analytics and at-risk alerts | Shino's M7. It reads our attendance data |
| AI lock during a quiz, weak-topic recommendations, explaining wrong quiz answers | Mine, but they need M6 quiz results first |
| PDF attendance reports | A nice-to-have in the requirements, with no task in the plan |
| OCR for scanned PDFs | Skipped for now. Lecturers see "no extractable text" |
| The student Participation screen | Stays a mock-up until Shino's M5 |

---

## Numbers chosen for you

All of these are settings that can change later.

| Setting | Value |
|---|---|
| Session opens | 15 min before the scheduled start |
| Late | Recognised more than 15 min after the class's start, following any time change |
| Attendance rate | (Present + Late) ÷ (closed sessions − Excused) |
| Excused | Only a lecturer can set it |
| Frames needed to confirm a face | 3 in a row |
| Selfie and card photos deleted | Within 24 hours of the decision |
| Unrecognised face photos deleted | When resolved, or after 7 days |
| Automatic material sync | Every 5 minutes |
| Minimum students before a topic appears in trends | 3 |
| Assistant answer time target | Within 15 s |
| Assistant language | English |

---
