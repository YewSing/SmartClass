# Use Cases: Module 6 — AI-Powered Quiz and Assessment

**Module:** 6 (AI-Powered Quiz and Assessment) | **Owner:** Shino
**Requirements:** FR-601–FR-614, FR-211, FR-814, NFR-05, NFR-09, NFR-13, NFR-14, NFR-17, NFR-18, NFR-23, NFR-24

Module 6 does not read course materials itself. It gets passages from the course knowledge base through Module 8's retrieval interface (FR-814).
Module 8 will need two things from this module: quiz results per student per question, tagged with topic and source material (UC-609), and whether a student has an active graded attempt (UC-604). Module 8's use of them (FR-820 to FR-824) is deferred.

---

## UC-601: Generate draft questions from materials

- **Actor:** Lecturer (primary), System
- **Description:** The lecturer picks course materials, a question type and a number, and the system uses an LLM to draft questions.
- **Preconditions:** The lecturer teaches the course, and at least one material of the course is indexed in the knowledge base (Module 8).
- **Postconditions:** A set of draft questions exists, each tagged with its source material and topic. Nothing is visible to students.

**Main Flow:**
1. Lecturer opens Quizzes, chooses the course and taps "New quiz".
2. Lecturer selects one or more materials, the question type (multiple-choice or short-answer) and the number of questions (FR-601).
3. System retrieves the relevant passages of the selected materials through Module 8 (FR-814).
4. System asks the LLM to draft the questions. Generation runs in the background and the app shows its progress (NFR-23).
5. Each multiple-choice question has answer options and the correct answer. Each short-answer question has a suggested answer (FR-602).
6. System tags each question with its source material and topic (FR-603).
7. The drafts are shown for review (UC-602), within 90 seconds for up to 10 questions (NFR-18).

**Alternative Flows:**
- *Lecturer wants more questions:* the lecturer runs the generation again. New drafts are added to the existing ones.

**Exception Flows:**
- *Selected material has no extractable text or is not indexed:* the system does not allow it to be selected and shows its status.
- *LLM error or timeout:* the system shows "Question generation is unavailable, try again". The lecturer's selections are kept (NFR-14).
- *LLM returns a question in an invalid format:* the system discards it and tells the lecturer how many questions were generated.

---

## UC-602: Review, edit and approve questions

- **Actor:** Lecturer
- **Description:** The lecturer checks each draft question. Only approved questions can be published.
- **Preconditions:** Draft questions exist (UC-601).
- **Postconditions:** Each question is approved, edited or deleted.

**Main Flow:**
1. Lecturer opens the draft list. Each question shows its text, options, correct or suggested answer, source material and topic.
2. Lecturer edits the question text, options, answer or topic where needed (FR-604).
3. Lecturer approves the question, or deletes it.
4. System saves the changes. Approved questions can be used in a quiz (UC-603).

**Exception Flows:**
- *Multiple-choice question has no correct answer selected:* the system does not allow approval.

---

## UC-603: Publish a quiz

- **Actor:** Lecturer, System
- **Description:** The lecturer turns approved questions into a quiz with a time limit and an open and close time.
- **Preconditions:** At least one approved question exists.
- **Postconditions:** The quiz is published. Enrolled students are notified.

**Main Flow:**
1. Lecturer selects approved questions and taps "Publish quiz".
2. Lecturer sets the time limit and the open and close date and time (FR-605).
3. System checks the lecturer teaches the course (NFR-05) and publishes the quiz.
4. System notifies the enrolled students of the new quiz with important priority (FR-211, UC-203).
5. Before the close time, the system sends the students who have not attempted the quiz a deadline reminder, with important priority (FR-211).

**Exception Flows:**
- *No approved question selected:* the system refuses to publish (FR-604).
- *Close time is earlier than open time:* the system asks the lecturer to correct the dates.

---

## UC-604: Take a quiz

- **Actor:** Student
- **Description:** The student views the published quizzes of their courses and makes one attempt within the time limit, on mobile or computer.
- **Preconditions:** The student is enrolled in the course and the quiz is open.
- **Postconditions:** The attempt is submitted and marked ready for grading.

**Main Flow:**
1. Student opens Quizzes. The list shows the published quizzes of the student's enrolled courses (FR-606), reachable within 3 taps (NFR-09).
2. Student selects an open quiz. The app shows the time limit and that only one attempt is allowed.
3. Student taps Start. System starts the attempt and the timer, which runs on the server (NFR-13) (FR-607).
4. Student answers the questions. The system saves each answer as the student answers (NFR-13). Correct answers are not shown.
5. Student taps Submit. System records the submission and starts grading (UC-605).

**Alternative Flows:**
- *Time limit expires:* the system submits the attempt automatically with the answers saved so far (FR-607).
- *Quiz closes before the time limit ends:* the attempt is submitted automatically at the close time.

**Exception Flows:**
- *Student has already attempted the quiz:* the system refuses a new attempt (FR-607).
- *Connection lost during the attempt:* the answers already saved are kept and the server timer continues. The student can reopen the quiz and carry on with the same attempt until time runs out (NFR-13).
- *Quiz not yet open or already closed:* the system shows the open and close times.

While an attempt is active, Module 8 can ask whether the student has an active graded attempt (FR-820, deferred).

---

## UC-605: Grade multiple-choice answers automatically

- **Actor:** System
- **Preconditions:** A student has submitted an attempt.
- **Postconditions:** Each multiple-choice question has a score. The attempt is "graded", or "waiting for scoring" if it has short-answer questions.

**Main Flow:**
1. System compares each multiple-choice answer with the correct answer (FR-608).
2. System saves the score of each question and the total.
3. If the quiz has no short-answer question, the attempt is marked "graded" and the student can view the result (UC-607).
4. System shares the result with Module 7 (UC-609).

**Alternative Flows:**
- *Quiz has short-answer questions:* the attempt stays "waiting for scoring" until the lecturer has scored all of them (UC-606).

---

## UC-606: Review and score short-answer responses

- **Actor:** Lecturer
- **Preconditions:** Students have submitted short-answer responses.
- **Postconditions:** Every short-answer response has a score, and the attempts are "graded".

**Main Flow:**
1. Lecturer opens the quiz and selects a short-answer question.
2. System lists the students' responses next to the suggested answer.
3. For each response, the system shows an AI-suggested score (FR-610, Could Have).
4. Lecturer accepts the suggested score or changes it, then saves (FR-609).
5. When all short-answer responses of an attempt are scored, the system marks the attempt "graded" and shares the result with Module 7 (UC-609).

**Exception Flows:**
- *AI suggestion unavailable:* the lecturer scores the responses without a suggestion (NFR-14).

---

## UC-607: View my quiz result

- **Actor:** Student
- **Preconditions:** The student has submitted the quiz and grading is complete.
- **Postconditions:** None.

**Main Flow:**
1. Student opens Quizzes and selects a submitted quiz.
2. System shows the total score and the result of each question: the student's answer, whether it was correct, and the correct answer (FR-611).

**Alternative Flows:**
- *Grading not complete:* the system shows "Waiting for grading" and no score.

---

## UC-608: View quiz results and difficult questions

- **Actor:** Lecturer
- **Preconditions:** Students have attempted the quiz.
- **Postconditions:** None.

**Main Flow:**
1. Lecturer opens the quiz results.
2. System shows each student's score and the class average (FR-612). The page loads within 5 seconds (NFR-17).
3. System lists the questions answered incorrectly by more than a configurable percentage of students (default 50%) (FR-613, NFR-24).
4. Lecturer can open a question to see its source material and topic.

**Alternative Flows:**
- *No attempt yet:* the system shows "No attempts yet".

---

## UC-609: Share quiz results with other modules

- **Actor:** System
- **Preconditions:** An attempt has been graded.
- **Postconditions:** Module 7 and Module 8 can read the results.

**Main Flow:**
1. System makes available the quiz results per student per question, with each question's topic and source material (FR-614).
2. Module 7 collects the results for the quiz scores and trend indicators (UC-701).
3. System tells Module 7 that the quiz has been graded, so it can evaluate the early warning conditions (FR-708, UC-706).
4. Module 8 will use the same results for weak-area recommendations when those requirements are built (FR-821, deferred).
