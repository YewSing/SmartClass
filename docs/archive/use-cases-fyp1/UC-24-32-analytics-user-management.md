# Use Cases: Analytics Dashboard & User Management

**Modules:** 7 (Real-time Analytics & Lecturer Dashboard), 8 (User Management)
**Owner:** Shino

---

## UC-24: View Real-time Attendance on Dashboard

- **Actor:** Lecturer (primary)
- **Description:** Lecturer views live attendance status of all enrolled students on the dashboard, without manual refresh. Updates automatically as recognition events arrive.
- **Preconditions:** Lecturer authenticated (NFR-04); an attendance session is active or recently closed; dashboard connected.
- **Postconditions:** Attendance panel accurately reflects Present, Absent, and Unidentified counts (FR-045); auto-updates within 2 seconds of any new detection event (NFR-27, FR-049).

**Main Flow:**
1. Navigate to attendance section from dashboard home screen (NFR-15).
2. System fetches current attendance state for the active session.
3. Dashboard renders attendance panel — student counts by status: Present, Absent, Unidentified (FR-045).
4. System subscribes dashboard to real-time attendance update events.
5. As UC-01 and UC-02 produce matches, dashboard auto-updates within 2 seconds (FR-049, NFR-27).
6. Lecturer may tap any student name to view detailed record or initiate UC-05.

**Exception Flows:**
- *No students detected within first 5 minutes:* Display visible warning prompting manual camera/environment verification (NFR-14).

---

## UC-25: View Quiz / Poll Results on Dashboard

- **Actor:** Lecturer, Student
- **Description:** Lecturer monitors real-time response analytics for active and recently closed quiz and poll questions. Results shown as percentage distribution per answer option.
- **Preconditions:** Lecturer authenticated (NFR-04); at least one quiz or poll pushed in current session (UC-20).
- **Postconditions:** Quiz/poll results panel shows current response distribution (FR-048); panel auto-updates within 2 seconds of any new student response (NFR-27).

**Main Flow:**
1. Navigate to quiz/poll results section.
2. Retrieve current tally for active or most recently closed question.
3. Render results chart showing percentage of students per answer option (FR-037, FR-048).
4. While question is open, chart auto-updates as new responses arrive from UC-16 (FR-049).
5. Lecturer may open detailed breakdown showing per-student correctness (FR-038).

**Alternative Flows:**
- *No question active or completed:* Display empty state with prompt to create a question.

**Exception Flows:**
- *Dashboard update delayed beyond 2 seconds:* Retry; raise connectivity warning if retry fails.

---

## UC-26: Monitor Confusion Rate and Alerts

- **Actor:** Lecturer (primary)
- **Description:** Lecturer monitors the aggregated anonymous confusion rate in real time. System automatically displays colour-coded alert indicators when rate reaches defined thresholds.
- **Preconditions:** Lecturer authenticated (NFR-04); session active and UC-20 running; dashboard open and connected.
- **Postconditions:** Confusion rate visible on dashboard and current within 3 seconds (NFR-22); yellow alert at ≥20%, red alert at ≥50% (FR-042); lecturer may reset counter at any time.

**Main Flow:**
1. View confusion rate panel on dashboard home screen (NFR-15).
2. System displays current confusion rate, updated within 3 seconds of each student IDU event (NFR-22).
3. Rate < 20%: no alert displayed.
4. Rate ≥ 20%: display yellow alert with colour and text indicators (FR-042, NFR-33).
5. Rate ≥ 50%: alert upgrades to red (FR-042).

---

## UC-27: View Environmental Data on Dashboard

- **Actor:** Lecturer (primary)
- **Description:** Lecturer views real-time classroom environmental conditions — temperature, humidity, light level, CO2 level, and occupancy — directly on the main dashboard without navigating away.
- **Preconditions:** Lecturer authenticated (NFR-04); at least temperature sensor and occupancy camera operational (UC-09).
- **Postconditions:** Environmental data panel reflects most recent sensor readings (FR-050); abnormal conditions raise dashboard alerts (FR-051).

**Main Flow:**
1. View environmental conditions panel on dashboard home screen (NFR-15, FR-050).
2. System displays latest readings: temperature, occupancy, light level, CO2.
3. Readings auto-update as UC-09 transmits new data (FR-049).
4. Any abnormal reading (e.g. temperature out of range, sensor offline) → display labelled alert with text and visual indicators (FR-051, NFR-33).

**Exception Flows:**
- *All sensors unresponsive:* Raise critical sensor failure alert (FR-051); display last known readings with stale-data indicator.

---

## UC-28: Filter and Export Analytics Reports

- **Actor:** Lecturer (primary)
- **Description:** Lecturer filters historical analytics data by class, session date, student, or module activity, and exports as PDF or CSV.
- **Preconditions:** Lecturer authenticated (NFR-04); historical session data exists for selected filters.
- **Postconditions:** Filtered analytics report generated and available for download (FR-054); exported data accurately reflects records at time of export.

**Main Flow:**
1. Navigate to analytics and reports section.
2. Select filter criteria: class, session date range, individual student, or module activity (FR-052).
3. Retrieve matching records from historical database (FR-053).
4. Present filtered data preview using charts, graphs, or tables (FR-047).
5. Select export format (PDF or CSV) and confirm (FR-054).
6. Generate export file and present for download.

**Alternative Flows:**
- *No records match filters:* Notify lecturer; prompt adjustment of filter parameters.

**Exception Flows:**
- *Export generation fails:* Display error; prompt retry.

---

## UC-29: Manage User Accounts

- **Actor:** Admin (primary)
- **Description:** Administrator creates, updates, and deletes user accounts for lecturers, students, and admins. Each account has a role governing access via RBAC.
- **Preconditions:** Admin authenticated with Admin role (NFR-03, NFR-04).
- **Postconditions:** Account created, updated, or deleted as specified (FR-057); RBAC permissions correctly applied (FR-058); profile stored including name, matric ID, contact info, assigned classes (FR-060).

**Main Flow:**
1. Navigate to user management section.
2. Select operation: create, update, or delete (FR-057).
3. *Create:* Enter profile fields and select user role (FR-060).
4. *Update:* Locate target account; modify relevant fields.
5. *Delete:* Select target account; confirm deletion.
6. Save changes; enforce role-based permissions immediately (FR-058).
7. Confirm action and return to user management view.

**Alternative Flows:**
- *Admin cancels operation:* No changes made; return to user management view.

**Exception Flows:**
- *Duplicate matric ID or email on creation:* Display validation error; prompt correction; block account creation until resolved.

---

## UC-30: Manage Student Class Enrolment and Face Data

- **Actor:** Admin (primary)
- **Description:** Administrator manages student class assignments and face recognition enrolment data — enrolling students into classes, updating assignments when students change classes, and removing outdated face data.
- **Preconditions:** Admin authenticated with Admin role (NFR-03, NFR-04); target student has an existing user account (UC-29).
- **Postconditions:** Student class assignments updated (FR-062); if face enrolment performed, new embedding stored and previous one replaced (FR-061, FR-062); student correctly associated with appropriate class sessions.

**Main Flow:**
1. Navigate to student enrolment management section.
2. Locate target student's account.
3. Update student's class assignments — add or remove class associations (FR-062).
4. If face data must be registered or updated, invoke UC-08 (FR-061).
5. Save updated class assignments and face data linkage.
6. Confirm changes; updated profile now active.

**Alternative Flows:**
- *Remove student from all classes:* Retain account and historical records; exclude from future session enrolment lists.

**Exception Flows:**
- *Remove face embedding without re-enrollment:* Delete stored embedding (FR-062); student will not be recognisable until re-enrolled.

---

## UC-31: Login to System

- **Actor:** Lecturer, Student, Admin
- **Description:** All users must authenticate with a valid username/email and password before accessing any protected function. RBAC enforced on successful login.
- **Preconditions:** User has an active account (UC-29); system login interface reachable.
- **Postconditions:** User authenticated; session token issued; UI presents only role-permitted features and data (FR-058); unauthenticated access blocked (NFR-04).

**Main Flow:**
1. User opens system login interface.
2. User enters username/email and password (FR-059).
3. System validates credentials.
4. On success: create authenticated session; issue session token.
5. Load dashboard view appropriate for user's role — Student, Lecturer, or Admin (FR-058).

**Exception Flows:**
- *Invalid credentials:* Display generic failure message without disclosing which field was incorrect; allow retry.
- *Account does not exist or is deactivated:* Display same generic failure message; do not confirm whether account exists.

---

## UC-32: View Personal Attendance and Participation

- **Actor:** Student (primary)
- **Description:** Student views their own attendance history across all past sessions and personal participation records (quiz and poll responses). No other student's data accessible.
- **Preconditions:** Student authenticated via UC-31; at least one session record exists for student's enrolled class.
- **Postconditions:** Student can view attendance status per session across enrolled classes (FR-055); student can view quiz and poll response history; no other student's data accessible (NFR-03).

**Main Flow:**
1. Navigate to personal attendance and participation section after login.
2. System retrieves all attendance records linked to the authenticated student across enrolled classes (FR-055).
3. Display attendance history — session dates, classes, and Present/Absent status in a clearly labelled view.
4. Student may view quiz and poll response history per session.

**Alternative Flows:**
- *No historical records yet:* Display empty state with informational message.
