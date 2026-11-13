# Use Cases: Module 7 — Learning Analytics and Early Warning

**Module:** 7 (Learning Analytics and Early Warning) | **Owner:** Shino
**Requirements:** FR-701–FR-710, FR-210, FR-313, FR-509, FR-614, NFR-05, NFR-06, NFR-17, NFR-20, NFR-23, NFR-24

---

## UC-701: Collect data and calculate engagement indicators

- **Actor:** System
- **Description:** The system gathers attendance, participation and quiz data and calculates the engagement indicators of each student in each course.
- **Preconditions:** At least one attendance session, interaction session or quiz has finished in the course.
- **Postconditions:** The indicators of every enrolled student in the course are up to date.

**Main Flow:**
1. An attendance session closes, an interaction session closes, or a quiz is graded.
2. System collects attendance records from Module 3 (FR-313), participation data from Module 5 (FR-509) and quiz results from Module 6 (FR-614) (FR-701).
3. System calculates for each student in the course (FR-702):
   - attendance rate,
   - absence frequency,
   - classroom participation frequency,
   - number of questions submitted,
   - number of "I Don't Understand" signals,
   - quiz scores and the trend across quizzes.
4. System saves the indicators for the dashboards (UC-702 to UC-705). The calculation runs in the background (NFR-23).
5. System starts the early warning check (UC-706).

**Alternative Flows:**
- *Student has no data for an indicator (for example no quiz yet):* the indicator shows "No data" instead of zero.

**Exception Flows:**
- *A source module's data cannot be read:* the system keeps the previous indicators and tries again at the next event.

Anonymous questions are counted in the student's number of questions submitted, but the system never links the count to a particular question (NFR-06).

---

## UC-702: View individual student indicators

- **Actor:** Lecturer
- **Preconditions:** The lecturer teaches the course.
- **Postconditions:** None.

**Main Flow:**
1. Lecturer opens Analytics and selects a course.
2. System shows the list of enrolled students with their main indicators (FR-703).
3. Lecturer selects a student.
4. System shows all the student's indicators (UC-701) and the quiz score trend. The page loads within 5 seconds (NFR-17).

**Exception Flows:**
- *Lecturer does not teach the course:* the request is refused (NFR-05).

---

## UC-703: View class engagement trend

- **Actor:** Lecturer
- **Preconditions:** The lecturer teaches the course and at least two sessions have finished.
- **Postconditions:** None.

**Main Flow:**
1. Lecturer opens the course's Analytics and selects "Class trend".
2. System shows the class attendance rate and participation across sessions, session by session (FR-704).
3. Each chart is also available as a table of values.

**Alternative Flows:**
- *Fewer than two sessions:* the system shows the available data and "Not enough sessions for a trend".

---

## UC-704: View assessment performance by topic and session

- **Actor:** Lecturer
- **Preconditions:** At least one quiz in the course has been graded.
- **Postconditions:** None.

**Main Flow:**
1. Lecturer opens the course's Analytics and selects "Assessment".
2. System shows the class's average score for each topic, using the topics tagged on the questions (FR-705).
3. System shows the class's average score for each quiz or session.

**Alternative Flows:**
- *No quiz graded yet:* the system shows "No assessment data yet".

---

## UC-705: View my engagement and performance

- **Actor:** Student
- **Preconditions:** The student is enrolled in the course.
- **Postconditions:** None.

**Main Flow:**
1. Student opens "My progress" and selects a course.
2. System shows the student's own attendance status, engagement summary (participation, questions, "I Don't Understand" signals) and quiz scores with trend (FR-706).

**Exception Flows:**
- *Student requests another student's indicators:* the system refuses it. A student can only see their own data (FR-706, NFR-05).

---

## UC-706: Detect at-risk students and alert the lecturer

- **Actor:** System
- **Description:** After each attendance session closes and each quiz is graded, the system checks the early warning conditions and alerts the lecturer.
- **Preconditions:** The indicators are up to date (UC-701).
- **Postconditions:** Flagged students are recorded. The lecturer has received an alert for each new flag.

**Main Flow:**
1. System evaluates the conditions for each student in the course (FR-707, FR-708). The values are configurable (NFR-24):
   - (a) the attendance rate is below a minimum percentage,
   - (b) the student has been absent for a set number of consecutive sessions,
   - (c) quiz scores have declined across a set number of consecutive quizzes,
   - (d) classroom participation has dropped by more than a set percentage compared with the previous period.
2. If any condition is met, the system flags the student as at-risk.
3. System creates an alert that states the student, the course and the condition met (FR-709).
4. System sends the alert to the lecturer through Module 2 with important priority (FR-210, UC-203).

**Alternative Flows:**
- *Student is already flagged for the same condition:* the flag is updated and no repeat alert is sent.
- *Condition is no longer met at a later check:* the flag for that condition is cleared.
- *Not enough data for a condition (for example fewer quizzes than the set number):* that condition is not evaluated.

---

## UC-707: View the at-risk student list

- **Actor:** Lecturer
- **Preconditions:** The lecturer teaches the course.
- **Postconditions:** None.

**Main Flow:**
1. Lecturer opens "At-risk students" and selects a course (FR-710).
2. System lists the flagged students with the condition that triggered each flag. The condition is written in text, not shown by colour alone (NFR-20).
3. Lecturer selects a student to see their indicators (UC-702).

**Alternative Flows:**
- *No student is flagged:* the system shows "No at-risk students".
