# Use Cases: Modules 2, 5, 6, 7 — Dashboard and Notifications, Classroom Interaction, AI Quiz, Learning Analytics

**Modules:** 2 (Dashboard and Notifications), 5 (Classroom Interaction), 6 (AI-Powered Quiz and Assessment), 7 (Learning Analytics and Early Warning) | **Owner:** Shino
**Requirements:** FR-201–FR-218, FR-501–FR-520, FR-601–FR-621, FR-701–FR-716, NFR-04, NFR-06, NFR-10–NFR-13, NFR-20–NFR-23, NFR-28–NFR-32, NFR-38–NFR-42, NFR-46, NFR-47, NFR-51, NFR-52

Use case IDs follow the module: UC-2xx = Module 2, UC-5xx = Module 5, and so on.

---

# Module 2 — Dashboard and Notifications

## UC-201: View dashboard

- **Actor:** Student, Lecturer
- **Description:** The user opens the home screen and sees what matters now: today's classes, attendance, Moodle announcements and deadlines, and urgent items.
- **Preconditions:** The user is logged in; courses are synced (UC-103).
- **Postconditions:** None (read-only).

**Main Flow:**
1. User opens the app. System loads the role's dashboard (NFR-22).
2. *Student:* system shows today's classes with attendance status, attendance rate per course, upcoming deadlines and latest announcements from Moodle, and any live activity now (poll, live game, open quiz) (FR-201, FR-203).
3. *Lecturer:* system shows today's classes, attendance overview of the current or latest session, participation summary, running and recent quizzes, and at-risk alerts (FR-202).
4. Urgent and important notifications are pinned at the top until read (FR-208).
5. User taps an item to open the related screen.

**Alternative Flows:**
- *A live activity starts while the dashboard is open:* a card appears without refreshing (FR-213, NFR-20).

**Exception Flows:**
- *Moodle unreachable:* the dashboard still loads and shows the last synced announcements and deadlines with a "last updated" time (NFR-42).

---

## UC-202: Receive and read notifications

- **Actor:** System (primary), Student, Lecturer
- **Description:** A module raises an event (for example "attendance recorded" or "quiz published"). The system turns it into a prioritised notification and delivers it.
- **Preconditions:** The recipient has an account; for push, the app has registered a push token (FR-212).
- **Postconditions:** The notification is in the user's feed, and pushed or emailed according to its priority.

**Main Flow:**
1. A module calls the notification event interface with event type, recipients, priority, title, message and link (FR-205, FR-206).
2. System gives the notification a priority: urgent, important or general (FR-207). It skips the event if the same one was already sent to that user (FR-216).
3. System adds it to each recipient's in-app feed and shows it live if the app is open (FR-209, FR-213).
4. For urgent and important notifications, system sends an Android push through the Expo service and an email (FR-210, FR-211). Text contains no marks or performance details (NFR-12).
5. User opens the feed, taps a notification and it is marked read. "Mark all as read" is available (FR-209).

**Alternative Flows:**
- *iOS device:* no push is sent; the notification appears in the app and by email (FR-210).
- *Deadline or quiz closing soon:* the system raises a reminder 24 hours and 1 hour before (FR-215).
- *Old notifications:* deleted after the retention period (FR-218).

**Exception Flows:**
- *Push or email fails:* the action that raised the event is not affected, and failed emails are retried (NFR-38).

---

## UC-203: Manage notification settings

- **Actor:** Student, Lecturer
- **Description:** The user chooses whether general notifications are sent as push and email.
- **Preconditions:** The user is logged in.
- **Postconditions:** The setting is saved. Urgent and important notifications are always delivered.

**Main Flow:**
1. User opens Profile → Notifications.
2. User turns push and email for general notifications on or off (FR-214).
3. System saves the choice.

**Alternative Flows:**
- *Sign in on a new phone:* the app registers its push token; on logout the token is removed (FR-212).

---

## UC-204: Send a class announcement

- **Actor:** Lecturer
- **Description:** The lecturer sends a short announcement to the students of a class they teach, and can also post it to the course's Moodle announcement forum.
- **Preconditions:** Lecturer teaches the class.
- **Postconditions:** Students receive an important notification; the Moodle post exists if chosen.

**Main Flow:**
1. Lecturer opens the class and chooses New announcement.
2. Lecturer writes the message and chooses whether to also post it to Moodle (FR-217).
3. System sends an important notification to the enrolled students (UC-202).
4. If chosen, system posts it to the course announcement forum in Moodle and shows the post status.

**Exception Flows:**
- *Moodle post fails:* the in-app notification is still sent; the post is retried and the lecturer sees its status (FR-217).

---

# Module 5 — Classroom Interaction

## UC-501: Open and close an interaction session

- **Actor:** Lecturer, System
- **Description:** The lecturer opens the live interaction tools for the class that is running. They close when the class ends.
- **Preconditions:** The lecturer teaches the course and the class session is running (UC-3xx start class).
- **Postconditions:** Enrolled students can join, or the session is closed and read-only.

**Main Flow:**
1. Lecturer opens the running class and taps Start interaction (NFR-47) (FR-501).
2. System opens the session and shows it as live on the dashboards of the course's students (FR-502).
3. Students join from the class screen.
4. Lecturer taps End interaction, or the system closes it when the class session ends (FR-501).
5. System saves the session summary (UC-507).

**Exception Flows:**
- *Student not enrolled in the course:* cannot join (FR-502, NFR-04).

---

## UC-502: Ask a live question

- **Actor:** Student
- **Description:** The student sends a question to the lecturer during class, optionally anonymously.
- **Preconditions:** An interaction session is open for the student's course.
- **Postconditions:** The question appears in the lecturer's list.

**Main Flow:**
1. Student opens the class screen and taps Ask a question.
2. Student types the question and chooses whether to send it anonymously (FR-503).
3. System adds the question to the list. The lecturer's screen updates at once (FR-516, NFR-20).
4. Other students can upvote it, once each (FR-505).

**Alternative Flows:**
- *Anonymous:* no one sees who asked; the author is stored only for class totals (FR-504, NFR-10).
- *After class:* the student can see their own past questions and whether the lecturer marked them answered (FR-520).

**Exception Flows:**
- *Session closed:* the app says questions are closed.

---

## UC-503: Manage live questions

- **Actor:** Lecturer
- **Description:** The lecturer reads incoming questions and marks them answered, pins them, or hides unsuitable ones.
- **Preconditions:** An interaction session is open.
- **Postconditions:** Question status is updated; hidden questions are audited.

**Main Flow:**
1. Lecturer opens the Questions list, ordered by votes and time (FR-505).
2. Lecturer reads a question and answers it in class.
3. Lecturer marks it as answered or pins it (FR-506).
4. System shows the new status to students.

**Alternative Flows:**
- *Unsuitable question:* the lecturer hides it; the system records an audit entry (FR-506).

---

## UC-504: Run a live poll

- **Actor:** Lecturer (primary), Student
- **Description:** The lecturer asks a poll question and sees answers as they come in.
- **Preconditions:** An interaction session is open.
- **Postconditions:** Poll result is saved with the session.

**Main Flow:**
1. Lecturer taps New poll, types the question and 2–6 options, and chooses single or multiple choice (FR-507).
2. Lecturer taps Start. Students get a `poll.started` notification and see the poll on screen (FR-206).
3. Each student votes once and can change the vote until the poll closes (FR-508, NFR-46).
4. Lecturer sees live results (FR-509, NFR-20).
5. Lecturer taps Close. The lecturer chooses whether students see the results (FR-509).

**Alternative Flows:**
- *Quick question:* the lecturer asks a short-text question instead and reads the answers as a list, anonymous to the class (FR-510).

---

## UC-505: Send a reaction or press "I Don't Understand"

- **Actor:** Student, System, Lecturer
- **Description:** The student signals that they are lost or reacts to the pace. The lecturer sees the class's overall level of confusion.
- **Preconditions:** An interaction session is open.
- **Postconditions:** The signal is recorded for the session and for Module 7.

**Main Flow:**
1. Student taps "I Don't Understand" and optionally picks a topic tag (FR-512, NFR-46).
2. System turns the student's signal on and records the press; a press within the cooldown (default 2 minutes) of the last one is not counted again (FR-512, FR-517).
3. Lecturer's screen shows how many are on right now and a timeline, with no student names (FR-515).
4. If enough students press within the time window, the system raises a `confusion.spike` notification to the lecturer (FR-514).
5. Lecturer slows down or explains again.
6. Student taps again to take the signal back, or the lecturer clears everyone's (FR-512).

**Alternative Flows:**
- *Reaction:* the student turns a quick reaction on (for example "too fast"); tapping it again takes it back, tapping another switches. The lecturer sees how many of each are on now and can clear them (FR-511).

**Exception Flows:**
- *Interaction paused or class ended:* the buttons are off; every signal goes down when the class ends.

---

## UC-506: Review the interaction summary

- **Actor:** Lecturer
- **Description:** After class the lecturer reviews what happened during the interaction session.
- **Preconditions:** The interaction session is closed.
- **Postconditions:** None (read-only, or CSV downloaded).

**Main Flow:**
1. Lecturer opens the class and chooses Interaction summary.
2. System shows questions asked and answered, poll results, reactions and the confusion timeline (FR-518).
3. Lecturer optionally exports the summary as CSV; anonymous questions are exported without identity (FR-519).

---

# Module 6 — AI-Powered Quiz and Assessment

## UC-601: Draft a quiz from a prompt

- **Actor:** Lecturer (primary), System
- **Description:** The lecturer describes the quiz in plain language. The AI drafts questions from the course materials and fills in the quiz settings it finds in the prompt.
- **Preconditions:** The lecturer teaches the course; its materials are indexed (FR-804).
- **Postconditions:** A saved draft quiz with draft questions exists.

**Main Flow:**
1. Lecturer taps New quiz and types a prompt, for example "game quiz, 10 MCQ and 2 short-answer on week 5 slides, 20 seconds per question". The lecturer may select materials (FR-601).
2. System reads the quiz details from the prompt and fills the settings (FR-601).
3. System drafts the questions from the materials through Module 8's retrieval (FR-602, FR-814). It may add extended questions, unless the lecturer said to use only the material.
4. System labels each question "from material" or "extended", tags it with topic and source page or slide, and writes an explanation of the correct answer (FR-602, FR-603).
5. System shows the draft for review (UC-602) (NFR-21).

**Alternative Flows:**
- *Prompt has no quiz details:* settings are left at defaults for the lecturer to fill in.
- *Further prompt:* the lecturer refines the draft, for example "make question 3 harder" (FR-604).

**Exception Flows:**
- *LLM fails or times out:* a clear error is shown and the lecturer can add questions manually (NFR-40).
- *Materials have no extractable text:* the system says so and asks the lecturer to choose other materials.

---

## UC-602: Review and publish a quiz

- **Actor:** Lecturer
- **Description:** The lecturer checks and edits the draft, confirms the settings, and publishes the quiz to the class.
- **Preconditions:** A draft quiz exists (UC-601).
- **Postconditions:** The quiz is published to the enrolled students, who are notified.

**Main Flow:**
1. Lecturer opens the draft. Each question shows its source, label, answer and explanation (FR-603).
2. Lecturer edits, deletes, reorders, regenerates or adds questions (FR-604).
3. Lecturer approves the questions. Only approved questions can be published (FR-604).
4. Lecturer reviews the settings: title, type (game or graded), timer mode (per question or whole quiz), open and close time, shuffle, and when results are released (FR-605, FR-606).
5. Lecturer taps Publish. System sends a `quiz.published` notification to the enrolled students (FR-606).

**Alternative Flows:**
- *Leave and continue later:* the draft stays saved (FR-604).
- *Unpublish or close:* the lecturer can do this; questions can no longer be edited once there are attempts (FR-606).

**Exception Flows:**
- *A live game is chosen with a whole-quiz timer:* the system uses per-question timers (FR-606).

---

## UC-603: Run a live game quiz

- **Actor:** Lecturer (primary), Student
- **Description:** The lecturer plays a game quiz live in class. Students answer on their phones against a countdown and compete on a leaderboard.
- **Preconditions:** A game quiz is published; the lecturer and students are in the app.
- **Postconditions:** Points and answers are saved; leaderboard shown; the quiz does not count toward marks.

**Main Flow:**
1. Lecturer starts the game from the quiz card (NFR-47). Students tap Join on their quiz card (FR-607, FR-610).
2. Lecturer releases question 1. Students see it with a countdown (FR-610, FR-608).
3. Students answer. The lecturer sees live answer counts (FR-610, NFR-20).
4. When the timer ends (or the lecturer ends it early), answers lock (NFR-23).
5. System reveals the correct answer, how the class answered and the explanation (FR-611). The server only sends the answer at this point (NFR-11).
6. System awards points: base points plus a speed bonus (FR-612, NFR-30).
7. System shows the leaderboard: top five and the student's own rank (FR-613).
8. Steps 2–7 repeat for each question. At the end the app shows a podium and a celebration (FR-615).

**Alternative Flows:**
- *Student joins late:* enters at the current question (FR-610).
- *Lecturer pauses, skips or ends the game:* the system applies it to all screens (FR-610).
- *Student chose a nickname or opted out:* shown as the nickname or not at all on the leaderboard (FR-613, NFR-13).

**Exception Flows:**
- *A student loses connection:* they rejoin at the current question within 5 seconds of reconnecting (NFR-41).

---

## UC-604: Attempt a graded quiz

- **Actor:** Student
- **Description:** The student takes a graded quiz in the app within its time limit.
- **Preconditions:** The quiz is published and open; the student is enrolled.
- **Postconditions:** Answers are submitted and graded; the student has used their one attempt.

**Main Flow:**
1. Student opens the quiz card and taps Start (FR-607, NFR-46). System marks the student as having an active graded attempt for Module 8 (FR-609).
2. System shows the questions with the timer (whole quiz or per question) (FR-608).
3. Student selects or types answers. Each answer is saved within 5 seconds (NFR-39).
4. Student submits, or the timer ends and the system submits automatically (FR-608, NFR-23).
5. System grades multiple-choice answers and short answers (UC-605) (FR-616).
6. The student sees "Submitted". Results are shown after the lecturer releases them (UC-606).

**Alternative Flows:**
- *Connection lost or app closed:* the student reopens the quiz and continues; saved answers are kept and the time is not extended (NFR-39).

**Exception Flows:**
- *Student already attempted:* the app shows that the quiz is done (FR-607).
- *Quiz closed or not yet open:* the card shows its open time.

---

## UC-605: Grade short answers automatically

- **Actor:** System (primary), Lecturer
- **Description:** The AI grades each short answer by comparing it with the suggested answer. The lecturer can look at doubtful scores and change them.
- **Preconditions:** A student has submitted an attempt with short-answer questions.
- **Postconditions:** Every short answer has a final score and a short reason.

**Main Flow:**
1. System sends each short answer to the AI with the suggested answer (FR-616, NFR-21).
2. AI returns a score and a short reason. The score is final without lecturer approval (FR-616).
3. System flags answers the AI is not confident about (FR-617).
4. Lecturer opens the Flagged list, reads the answer and score, and optionally changes the score and adds feedback (FR-617).
5. System logs the change with actor, old score, new score and time (FR-617).

**Exception Flows:**
- *LLM fails:* the short answers stay "pending" and are graded when the provider recovers. Multiple-choice grading is not affected (NFR-40).

---

## UC-606: View results and review answers (student)

- **Actor:** Student
- **Description:** The student sees their marks and reviews each question once the lecturer releases results.
- **Preconditions:** The student submitted a quiz; the lecturer released results.
- **Postconditions:** None (read-only).

**Main Flow:**
1. Student receives a `quiz.graded` notification and opens the quiz card (FR-206).
2. System shows the marks. For each question it shows the student's answer, the correct answer and the explanation, as far as the lecturer released them (FR-618).
3. Student can open the topic's cited source page or slide.

**Alternative Flows:**
- *Lecturer has not released marks or answers:* the unreleased parts stay hidden. The server does not send them to the app (FR-618, NFR-11).

---

## UC-607: View quiz results and release them (lecturer)

- **Actor:** Lecturer
- **Description:** The lecturer reviews how the class did and decides when students can see the results.
- **Preconditions:** A quiz has attempts.
- **Postconditions:** Results are released to students as chosen.

**Main Flow:**
1. Lecturer opens the quiz results (FR-619).
2. System shows submissions, score distribution, average and the correct rate of each question, including the most-missed questions.
3. Lecturer chooses to release marks, answers, both or neither (FR-618).
4. System makes the chosen parts visible to students and sends `quiz.graded` (FR-206).

---

## UC-608: View leaderboards

- **Actor:** Student, Lecturer
- **Description:** Shows how students rank in game quizzes, per quiz and across the course.
- **Preconditions:** At least one game quiz has been played.
- **Postconditions:** None (read-only).

**Main Flow:**
1. User opens the course's Leaderboard.
2. System shows the course leaderboard, which adds up each student's points across the game quizzes (FR-614).
3. User opens one game quiz to see its leaderboard (FR-613).

**Alternative Flows:**
- *Student chose a nickname or opted out:* other students see the nickname or no entry. Lecturers always see real names (FR-613, NFR-13).
- *Graded quiz:* no leaderboard is shown (FR-613).

---

# Module 7 — Learning Analytics and Early Warning

## UC-701: View class analytics

- **Actor:** Lecturer
- **Description:** The lecturer sees how a course is doing: attendance, participation and quiz performance over time.
- **Preconditions:** The lecturer teaches the course.
- **Postconditions:** None (read-only).

**Main Flow:**
1. Lecturer opens the course and chooses Analytics.
2. System checks that the lecturer teaches the course (FR-714, NFR-04).
3. System shows attendance trend by session, participation trend, quiz performance by quiz and by topic, and the number of at-risk students (FR-703).
4. System also shows the most-missed quiz topics and the lowest-engagement sessions (FR-716).
5. Lecturer optionally exports the report as CSV (FR-707).

**Alternative Flows:**
- *Administrator:* can open the analytics of any class (FR-714).

**Exception Flows:**
- *Lecturer does not teach the class:* the request is rejected (FR-714, NFR-04).
- *Too few sessions or quizzes:* the indicator shows "not enough data" and no alert is raised from it (FR-706).

---

## UC-702: View a student's analytics

- **Actor:** Lecturer
- **Description:** The lecturer opens one student's indicators and trends.
- **Preconditions:** The lecturer teaches the course; the student is enrolled in it.
- **Postconditions:** None (read-only).

**Main Flow:**
1. Lecturer opens a student from the class list or the at-risk list.
2. System shows the student's attendance rate, absences, consecutive absences, participation, questions submitted, confusion signals, graded-quiz scores and trend, and topic mastery (FR-702, FR-704).
3. Anonymous questions are not included in the student's figures (FR-713, NFR-10).

---

## UC-703: View my own progress

- **Actor:** Student
- **Description:** The student sees their own attendance, engagement and quiz performance.
- **Preconditions:** The student is logged in.
- **Postconditions:** None (read-only).

**Main Flow:**
1. Student opens Progress.
2. System shows the student's attendance status, engagement summary, quiz performance and topic mastery for each course (FR-705, FR-702).
3. Topic mastery from graded and game quizzes is shown separately (FR-702).

**Alternative Flows:**
- *Too few sessions or quizzes:* the indicator shows "not enough data" (FR-706).

**Exception Flows:**
- *A student asks for another student's data:* rejected; students only reach their own records (FR-705, NFR-04).

---

## UC-704: Receive an at-risk alert and follow up

- **Actor:** System (primary), Lecturer
- **Description:** The system flags a student who meets a warning rule and tells the lecturer. The lecturer records what they did.
- **Preconditions:** Early-warning rules are on (defaults or the lecturer's settings).
- **Postconditions:** The alert has a status and is audited.

**Main Flow:**
1. System evaluates the rules after each attendance session is finalised, after each graded quiz is graded, and once a day (FR-710).
2. A student meets a rule: attendance rate below the minimum, absent several sessions in a row, graded-quiz scores declining, or participation dropping a lot (FR-708, NFR-32).
3. System raises an `at_risk.alert` through Module 2 to the lecturer, showing which rule fired and the numbers behind it (FR-711). Push and email text has no student details (NFR-12).
4. Lecturer opens the At-risk list for the course (FR-712).
5. Lecturer contacts the student, then marks the alert Acknowledged, Followed up or Dismissed, with an optional note (FR-712).
6. System writes an audit entry (FR-715, NFR-06).

**Alternative Flows:**
- *Same rule fires again for the same student:* no second alert until the rule clears and recurs (FR-711).

**Exception Flows:**
- *Student has too little data:* no alert is raised (FR-706).

---

## UC-705: Configure early-warning rules

- **Actor:** Lecturer
- **Description:** The lecturer changes the warning thresholds for a course they teach or turns individual rules off.
- **Preconditions:** The lecturer teaches the course.
- **Postconditions:** New thresholds apply from the next evaluation; the change is audited.

**Main Flow:**
1. Lecturer opens the course's Analytics → Alert rules.
2. System shows each rule with its threshold (default attendance minimum 80%, 3 consecutive absences, 3 declining quizzes, 50% participation drop) (FR-708).
3. Lecturer changes a value or turns a rule on or off (FR-709, NFR-52).
4. System saves it and writes an audit entry (FR-715).
