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
2. Sees "attendance recorded" in the app.
3. Can check their attendance rate and history per course.

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
1. Opens a session for their class. The door camera only captures while a session is open.
2. Watches a live list of Present, Late and not yet recognised, without refreshing.
3. Unrecognised faces appear as photos. The lecturer assigns one to a student or dismisses it.
4. Can change any student's status at any time, and must give a reason. Every change is logged.
5. Ends the session. Everyone without a record becomes Absent.
6. Attendance is copied to Moodle automatically, with a synced, pending or failed label and a Retry button. If Moodle is down, nothing is lost.
7. Can export a CSV for a session or a date range.

**Other jobs**
- **Face verification queue:** sees the selfie and card side by side with the system's result, then approves or rejects with a reason. Lecturers of any of that student's courses can do this.
- **Course materials:** uploads files to SPeCTRUM as usual. SmartClass picks them up automatically, or through a Sync button. A status list shows which files the AI can read.
- **Question trends:** sees the most-asked topics and most-cited materials, only for topics at least 3 students asked about, with no names or question text.

**Phone or browser:** the same features and data. The browser has a side menu and a wider layout.

---

## Admin

A small role for jobs that don't suit a lecturer, in the browser only:
- View accounts, deactivate or reactivate them, and create other admins.
- Act as a fallback for the face verification queue, and reset a student's face data.
- View the audit log, and check or start the Moodle sync.
- Register door cameras, and issue or replace their keys.

The old `frontend/admin` site is deleted after these screens exist and Shino confirms she doesn't need it.

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

---

## Numbers chosen for you

All of these are settings that can change later.

| Setting | Value |
|---|---|
| Late | Recognised more than 15 min after the lecturer opens the session |
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

## Questions for you

These are the places where the plan may not match what you expect.

1. **Student "report an attendance problem":** the student app has a mock-up screen for this ("Face recognition did not detect me"), but no requirement or task covers it, so it would stay fake. Build it, or remove the screen? *Suggestion: build it. Missed detections will happen, and it makes a good demo.*
2. **Student not recognised at all:** today they become Absent unless the lecturer notices. Is the lecturer's override enough, or does this strengthen question 1?
3. **The Late clock starts when the lecturer opens the session,** not at the scheduled class time. If a lecturer opens it 20 minutes late, nobody is Late. *Suggestion: keep it. It's simple and fair to students.*
4. **Scanned PDFs:** the AI can't read them, and the lecturer only sees "no extractable text". Is that acceptable, or do you want OCR? *Suggestion: skip OCR unless time remains.*
5. **Telling lecturers what's missing:** we discussed showing topics students ask about that the materials don't cover. The plan only has most-asked topics and most-cited materials. Add it? *Suggestion: add it as a small task, since it's a clear benefit for lecturers.*
6. **Attendance edited directly in Moodle** isn't copied back. SmartClass is the master, and its next sync can overwrite that edit. Is that okay? *Suggestion: yes.*
7. **"Attendance recorded" only shows while the app is open** until Shino's notifications exist. Is that fine for your demo?
8. **Old student screens:** Participation is mock data, and likely belongs to Shino's M5. Should it stay visible until she builds it?
