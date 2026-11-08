# Use Cases: Modules 3 & 4 — Attendance Management and Facial Recognition Verification

**Modules:** 3 (Attendance Management), 4 (Facial Recognition Attendance Verification) | **Owner:** Yew Sing
**Requirements:** FR-301–FR-314, FR-401–FR-411, NFR-02, NFR-06, NFR-07, NFR-10–NFR-13, NFR-16, NFR-20, NFR-22–NFR-25

---

## UC-301: Open an attendance session

- **Actor:** Lecturer
- **Preconditions:** Lecturer is logged in and teaches the course; a class is scheduled.
- **Postconditions:** Session is open; the room's camera device starts capturing (UC-401).

**Main Flow:**
1. Lecturer taps the scheduled class on the dashboard, then "Start attendance" (≤ 3 taps, NFR-25).
2. System opens the session (FR-301) and links it to the room's camera device.
3. System shows the live session view (UC-303).

**Exception Flows:**
- *Session already open for this class:* show the existing session.
- *Room's device offline:* open anyway, warn the lecturer, suggest the backup webcam (FR-409, NFR-23).

---

## UC-401: Recognise a student at the entrance

- **Actor:** System (Raspberry Pi device + backend)
- **Description:** The Pi at the door detects faces and sends crops to the backend, which identifies the student and records attendance.
- **Preconditions:** A session is open for the device's room; students have active face data (UC-104).
- **Postconditions:** Recognised students are Present (UC-402); unmatched faces are flagged (UC-404).

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

## UC-402: Record Present and give feedback

- **Actor:** System
- **Preconditions:** UC-401 confirmed a student; session still open.
- **Postconditions:** Present record with timestamp and device ID; student and lecturer informed.

**Main Flow:**
1. System writes Present for the student and session, unless one already exists (FR-302, NFR-22).
2. Lecturer's live view updates without refresh (FR-306).
3. Student is told on their phone "Attendance recorded for <course>" (FR-406). This is delivered through Module 2's notification event; until M2 exists, it shows as a live update in the student app.

**Exception Flows:**
- *Session closed in the meantime:* event discarded.

---

## UC-303: Monitor a live session

- **Actor:** Lecturer
- **Main Flow:**
1. Lecturer opens the live session view.
2. System shows Present and Not-yet-recognised students, counts, device status, and pending unrecognised faces. These update live (FR-306).

---

## UC-404: Resolve an unrecognised face

- **Actor:** Lecturer
- **Preconditions:** A face was detected but not matched during a session (FR-407).
- **Postconditions:** Face assigned to a student (marked Present) or dismissed; crop deleted (FR-410, NFR-02).

**Main Flow:**
1. Lecturer opens Unrecognised Faces from the live view.
2. System shows each crop with time and similarity to the closest candidate.
3. Lecturer assigns the crop to an enrolled student who is not yet present. System records Present with "manual (face review)" as the source and writes an audit entry.
4. System deletes the crop.

**Alternative Flows:**
- *Dismiss (not a student of this class, false detection):* crop deleted, nothing recorded.

---

## UC-304: Close the session

- **Actor:** Lecturer
- **Postconditions:** Every enrolled student is Present or Absent; Moodle sync queued (UC-306).

**Main Flow:**
1. Lecturer taps "End attendance".
2. System marks every enrolled student without a Present record as Absent (FR-303).
3. The device stops capturing.
4. System queues the Moodle sync (FR-311).

---

## UC-305: Override attendance

- **Actor:** Lecturer
- **Preconditions:** Session belongs to the lecturer's course (open or closed).
- **Postconditions:** Status changed; audit entry written; re-sync queued if already synced.

**Main Flow:**
1. Lecturer selects a student in a session and switches Present ↔ Absent.
2. System requires a reason (FR-305).
3. System saves the change and audits actor, old status, new status, reason and time (NFR-06).
4. If the session was already synced, system queues a re-sync (FR-312).

---

## UC-306: Sync finalised attendance to Moodle

- **Actor:** System
- **Preconditions:** Session closed; the Moodle course has an Attendance activity.
- **Postconditions:** The Moodle Attendance session holds the same Present/Absent statuses; SmartClass marks the sync "synced".

**Main Flow:**
1. System finds, or creates, the Moodle Attendance session for this class date and time (FR-311).
2. System maps Present/Absent to the activity's Present/Absent statuses and sends each student's status.
3. System marks the session "synced" with a timestamp (FR-312).

**Exception Flows:**
- *Moodle unreachable or error:* mark "failed", retry with backoff (NFR-20); lecturer sees the status and can "Retry now".
- *Student unknown to Moodle:* skip them and report them in the sync result.

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
