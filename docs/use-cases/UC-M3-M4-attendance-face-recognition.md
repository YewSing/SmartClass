# Use Cases: Modules 3 & 4 — Attendance Management and Facial Recognition Verification

**Modules:** 3 (Attendance Management), 4 (Facial Recognition Attendance Verification) | **Owner:** Yew Sing
**Requirements:** FR-301–FR-320, FR-401–FR-411, NFR-02, NFR-06, NFR-07, NFR-10–NFR-13, NFR-16, NFR-20, NFR-22–NFR-25

---

## UC-301: A class session opens from its schedule

- **Actor:** System; Lecturer for changes
- **Preconditions:** The class has a weekly schedule (FR-315).
- **Postconditions:** Session is open; the room's camera device starts capturing (UC-401).

**Main Flow:**
1. At the configured time before the class (default 15 minutes), system opens the session (FR-301) and links it to the room's camera device.
2. Lecturer can open the live session view at any time (UC-303).

**Alternative Flows:**
- *Time changed or forgot to update:* before or during the class, lecturer changes the time for this class only; the Late clock follows the new start (FR-316).
- *Unscheduled or make-up class:* lecturer taps "Start now".
- *Class cancelled:* lecturer cancels it, and no attendance is recorded.

**Exception Flows:**
- *Room's device offline:* session opens anyway; warn the lecturer and suggest the backup webcam (FR-409, NFR-23).


---

## UC-401: Recognise a student at the entrance

- **Actor:** System (Raspberry Pi device + backend)
- **Description:** The Pi at the door detects faces and sends crops to the backend, which identifies the student and records attendance.
- **Preconditions:** A session is open for the device's room; students have active face data (UC-104).
- **Postconditions:** Recognised students are Present or Late (UC-402); unmatched faces are flagged (UC-404).

**Main Flow:**
1. The Pi polls for an open session for its room and starts capturing (FR-401).
2. The Pi detects faces in each frame and sends the crops with its device key (FR-402, NFR-07).
3. The backend computes an embedding and compares it with the enrolled students of that course (FR-403).
4. When the same student matches above the threshold in N consecutive frames (default 3), the system confirms them (FR-404).
5. The system submits the recognition to Module 3 (FR-405 → UC-402).

**Alternative Flows:**
- *Already Present:* ignored (NFR-22).
- *Match is a student not enrolled in this course:* not marked; logged.
- *Below threshold for several frames:* UC-404.

**Exception Flows:**
- *Backend unreachable:* the Pi buffers crops and resends them with original timestamps (FR-411, Could Have); otherwise crops are dropped and the lecturer sees the device warning.
- *Invalid device key:* backend rejects the request (401).

---

## UC-402: Record Present or Late and give feedback

- **Actor:** System
- **Preconditions:** UC-401 confirmed a student; session still open.
- **Postconditions:** Present or Late record with timestamp and device ID; student and lecturer informed.

**Main Flow:**
1. System writes Present, or Late if past the configured time (FR-302), for the student and session, unless one already exists (FR-302, NFR-22).
2. Lecturer's live view updates without refresh (FR-306).
3. Student is told on their phone "Attendance recorded for <course>" (FR-406). This is delivered through Module 2's notification event; until M2 exists, it shows as a live update in the student app.

**Exception Flows:**
- *Session closed in the meantime:* event discarded.

---

## UC-303: Monitor a live session

- **Actor:** Lecturer
- **Main Flow:**
1. Lecturer opens the live session view.
2. System shows Present, Late and Not-yet-recognised students, counts, device status, and pending student flags. These update live (FR-306).

---

## UC-404: Student flags "not recognised"; lecturer resolves

- **Actor:** Student, Lecturer
- **Preconditions:** Session is open; the student is enrolled and has no record (FR-318).
- **Postconditions:** Flag confirmed (Present or Late) or rejected; any matching crop deleted (FR-410, NFR-02).

**Main Flow:**
1. Student taps "I'm here but wasn't recognised".
2. Lecturer gets an alert in the live view, showing the student's name, matric number and the closest unmatched face, if any.
3. Lecturer checks in the room, for example by asking the student to raise a hand or show their matric card.
4. Lecturer confirms. System records Present or Late from the flag time, with "student flag" as the source, and writes an audit entry (FR-319).
5. Student sees the result.

**Alternative Flows:**
- *Student isn't in the room:* lecturer rejects with a reason; the student stays without a record.
- *Not resolved before the class ends:* student is Absent, and the flag stays in the lecturer's list. Confirming later updates the record and re-syncs to Moodle.
- *Unmatched face nobody claims:* lecturer does nothing; the crop is deleted within 7 days.


---

## UC-304: Close the session

- **Actor:** System; Lecturer if ending early
- **Postconditions:** Every enrolled student has a status (Present, Late, Excused or Absent); Moodle sync queued (UC-306).

**Main Flow:**
1. The scheduled end arrives, or the lecturer taps "End attendance".
2. System marks every enrolled student without a Present or Late record as Absent (FR-303).
3. The device stops capturing.
4. System queues the Moodle sync (FR-311).

**Exception Flows:**
- *No recognitions and no lecturer action:* nobody is marked Absent and nothing syncs. Lecturer is asked whether the class was held (FR-317).


---

## UC-305: Override attendance

- **Actor:** Lecturer
- **Preconditions:** Session belongs to the lecturer's course (open or closed).
- **Postconditions:** Status changed; audit entry written; re-sync queued if already synced.

**Main Flow:**
1. Lecturer selects a student in a session and changes their status to Present, Late, Excused or Absent.
2. Lecturer may add a reason (optional, FR-305).
3. System saves the change and audits actor, old status, new status, reason (if given) and time (NFR-06).
4. If the session was already synced, system queues a re-sync (FR-312).

---

## UC-306: Sync finalised attendance to Moodle

- **Actor:** System
- **Preconditions:** Session closed; the Moodle course has an Attendance activity.
- **Postconditions:** The Moodle Attendance session holds the same statuses; SmartClass marks the sync "synced".

**Main Flow:**
1. System finds, or creates, the Moodle Attendance session for this class date and time (FR-311).
2. System maps the four statuses one-to-one to the activity's statuses and sends each student's status.
3. System marks the session "synced" with a timestamp (FR-312).

**Exception Flows:**
- *Moodle unreachable or error:* mark "failed", retry with backoff (NFR-20); lecturer sees the status and can "Retry now".
- *Student unknown to Moodle:* skip them and report them in the sync result.
- *Status changed in Moodle:* don't overwrite it; show the lecturer both values and let them choose (FR-320).

---

## UC-307: View attendance history and reports

- **Actor:** Student (own records), Lecturer (their courses)

**Main Flow (Student):**
1. Student opens Attendance.
2. System shows each course's attendance rate and session-by-session history (FR-308, FR-309).

**Main Flow (Lecturer):**
1. Lecturer opens Reports and picks a session or a course and date range (FR-310).
2. System shows the table of students × sessions with rates.
3. Lecturer taps Export → CSV download (PDF is Could Have, FR-314).

---

## UC-405: Manage camera devices

- **Actor:** Admin
- **Main Flow:**
1. Admin registers a device (name, room) and receives its key once (FR-408).
2. Admin sees each device's online/offline status from heartbeats and can regenerate a key, which revokes the old one.
