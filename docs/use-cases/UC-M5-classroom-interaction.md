# Use Cases: Module 5 — Classroom Interaction

**Module:** 5 (Classroom Interaction) | **Owner:** Shino
**Requirements:** FR-501–FR-509, NFR-05, NFR-06, NFR-09, NFR-10, NFR-16, NFR-20

All interactions in this module are non-graded. Graded assessments are handled by Module 6.

---

## UC-501: Open and close an interaction session

- **Actor:** Lecturer
- **Description:** The lecturer opens an interaction session for a scheduled class so that students can take part, and closes it when the activity is finished.
- **Preconditions:** The lecturer is logged in and teaches the course; a class is scheduled.
- **Postconditions:** The session is open (or closed). Students can participate only while it is open.

**Main Flow:**
1. Lecturer taps the scheduled class on the dashboard, then "Start interaction" (within 3 taps, NFR-09).
2. System checks that the lecturer teaches the course (NFR-05) and opens the session (FR-501).
3. The enrolled students' dashboards show the session under ongoing activities (FR-201).
4. System shows the lecturer's live view: incoming questions, polls, live questions, reaction counts and the "I Don't Understand" count (UC-503 to UC-508).
5. When the class activity ends, the lecturer taps "End interaction".
6. System closes the session. Any poll still open is closed, and no new input is accepted.

**Alternative Flows:**
- *Session already open for this class:* the system shows the existing live view.

**Exception Flows:**
- *Lecturer does not teach the course:* the request is refused.

---

## UC-502: Submit a question

- **Actor:** Student
- **Description:** The student sends a question to the lecturer during class, with the option to stay anonymous.
- **Preconditions:** The student is enrolled in the course and an interaction session is open.
- **Postconditions:** The question is saved and shown to the lecturer.

**Main Flow:**
1. Student opens the open session from the dashboard and taps "Ask a question".
2. Student types the question and chooses whether to send it anonymously.
3. Student taps Send. System checks the student is enrolled (NFR-05) and that the session is still open.
4. System saves the question with the session, student and time (FR-509).
5. The question appears on the lecturer's screen within 3 seconds (NFR-16). An anonymous question shows "Anonymous" and no name (FR-502, NFR-06).

**Exception Flows:**
- *Session closed before sending:* the system refuses it and shows "This session has ended".
- *Empty question:* the system asks the student to type something.
- *Connection lost:* the app shows an error and keeps the typed text so the student can send again (NFR-10).

---

## UC-503: View and answer questions in real time

- **Actor:** Lecturer
- **Preconditions:** An interaction session is open.
- **Postconditions:** Answered questions are marked.

**Main Flow:**
1. Lecturer opens the question list in the live view.
2. System shows the submitted questions as they arrive, without refreshing (FR-503, NFR-16). Anonymous questions show no identity (NFR-06).
3. Lecturer answers a question in class and marks it as answered.
4. System moves the question to the answered list.

---

## UC-504: Create and run a live poll

- **Actor:** Lecturer
- **Preconditions:** An interaction session is open.
- **Postconditions:** The poll is closed and its results are saved.

**Main Flow:**
1. Lecturer taps "New poll" and enters a question and two or more answer options (FR-504).
2. Lecturer taps "Open voting". Students see the poll.
3. System shows the lecturer the votes as they arrive, as counts per option (FR-505, NFR-16).
4. Lecturer taps "Close voting". Students can no longer vote.

**Exception Flows:**
- *Fewer than two options:* the system does not let the lecturer open the poll.

---

## UC-505: Vote in a poll

- **Actor:** Student
- **Preconditions:** The student is enrolled in the course and a poll is open.
- **Postconditions:** One vote is recorded for the student.

**Main Flow:**
1. Student sees the open poll on the interaction screen.
2. Student selects an option and taps Vote.
3. System checks the student has not voted in this poll, records the vote (FR-505, FR-509) and confirms to the student.
4. The lecturer's poll results update (UC-504).

**Exception Flows:**
- *Student has already voted:* the system refuses a second vote.
- *Voting closed before the student votes:* the system refuses it and shows "Voting has closed".

---

## UC-506: Post a live question and collect responses

- **Actor:** Lecturer (posts), Student (responds)
- **Preconditions:** An interaction session is open.
- **Postconditions:** The responses are saved.

**Main Flow:**
1. Lecturer taps "Ask the class" and types a live question (FR-506).
2. Students see the question and type a response.
3. System saves each response (FR-509) and shows it to the lecturer as it arrives (NFR-16).
4. Lecturer closes the live question.

**Exception Flows:**
- *Live question closed before the student sends:* the system refuses the response.

---

## UC-507: Send a reaction

- **Actor:** Student
- **Preconditions:** The student is enrolled in the course and an interaction session is open.
- **Postconditions:** The reaction is recorded.

**Main Flow:**
1. Student taps one reaction from the predefined set (FR-507). Each reaction has a text label as well as an icon (NFR-20).
2. System records the reaction (FR-509).
3. The lecturer's reaction counts update within 3 seconds (NFR-16).

---

## UC-508: Signal "I Don't Understand"

- **Actor:** Student
- **Preconditions:** The student is enrolled in the course and an interaction session is open.
- **Postconditions:** The signal is recorded and counted.

**Main Flow:**
1. Student taps the "I Don't Understand" button (reachable within 3 taps, NFR-09) (FR-508).
2. System records the signal with the session, student and time (FR-509).
3. The lecturer sees the number of students who selected it, updated within 3 seconds (NFR-16).

**Alternative Flows:**
- *Same student taps again in the same session:* the student is counted once in the lecturer's number.

---

## UC-509: Record interaction data

- **Actor:** System
- **Description:** Every interaction is saved so that Module 7 can use it for engagement indicators.
- **Preconditions:** A student interaction happens in an open session (UC-502 to UC-508).
- **Postconditions:** The data is stored and available to Module 7.

**Main Flow:**
1. System saves each question, poll vote, response, reaction and "I Don't Understand" signal with the session, student and time (FR-509).
2. For an anonymous question, the system keeps the student's identity for counting only. It is never shown to the lecturer or other students (NFR-06).
3. Module 7 reads the data after the session closes (UC-701).
