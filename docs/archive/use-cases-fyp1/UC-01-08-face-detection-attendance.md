# Use Cases: Face Detection & Attendance Management

**Modules:** 1 (Face Detection & Recognition), 2 (Attendance Logging & Management)
**Owner:** Yew Sing

---

## UC-01: Detect and Recognise Student Face

- **Actor:** System (primary)
- **Description:** The system continuously captures video frames from two ceiling-mounted front-facing cameras, detects faces, extracts embeddings, and matches against the enrolled student database. Includes UC-02 when a match is confirmed.
- **Preconditions:** Attendance session is open (UC-04); at least one camera operational; face database accessible; lighting within NFR-17 range.
- **Postconditions:** Each face classified as recognised or unrecognised; UC-02 invoked on match; UC-07 may be triggered on no-match.

**Main Flow:**
1. Capture live video continuously from both cameras (FR-006).
2. Detect all faces within 6 metres per frame (FR-001).
3. Extract face embedding; discard raw image immediately (NFR-01).
4. Compare embedding against student database for confidence score (FR-002).
5. Aggregate results across multiple frames (FR-004).
6. If aggregated score ≥ threshold → confirm match (FR-003).
7. Invoke UC-02 to record attendance.
8. Continue scanning for additional students.

**Alternative Flows:**
- *Unrecognised face:* Score below threshold → trigger UC-07.
- *Already marked present:* Skip UC-02 to prevent duplicate records.

**Exception Flows:**
- *One camera fails:* Log failure, alert dashboard (FR-051), continue with remaining camera.
- *Both cameras fail:* Halt pipeline, raise critical alert, prompt lecturer to use UC-05.
- *Face database unreachable:* Buffer embeddings locally; retry on reconnect (NFR-18).

---

## UC-02: Auto-mark Student as Present

- **Actor:** System (primary)
- **Description:** Upon a confirmed face match within an active session, automatically records the student's attendance as 'Present'. Included by UC-01.
- **Preconditions:** UC-01 produced a confirmed match above threshold; session window open; student enrolled in current class; student not already marked present.
- **Postconditions:** Attendance recorded as 'Present' (FR-011); dashboard updated in real time (FR-045, FR-049); timestamp logged.

**Main Flow:**
1. Receive confirmed match event from UC-01.
2. Verify session window is still open (FR-008).
3. Check student not already marked present.
4. Write 'Present' attendance record (FR-007).
5. Commit to database within 3 seconds of match (NFR-26).
6. Push updated count to lecturer dashboard (FR-045).

**Alternative Flows:**
- *Duplicate event:* Discard silently.

**Exception Flows:**
- *Database unreachable:* Store locally; sync on reconnect (NFR-18).
- *Session closed mid-write:* Discard event.

---

## UC-03: Auto-mark Student as Absent at Session End

- **Actor:** System (primary)
- **Description:** When the lecturer closes the session (UC-04), marks all enrolled students not detected as 'Absent'.
- **Preconditions:** Session was previously opened (UC-04); lecturer has just closed it; class roster accessible.
- **Postconditions:** All undetected students recorded as 'Absent' (FR-009); full session record stored (FR-011); dashboard shows final summary (FR-045).

**Main Flow:**
1. Receive session-closure event from UC-04.
2. Retrieve full class roster.
3. Retrieve list of students marked present.
4. Compute set difference (enrolled minus present).
5. Write 'Absent' record for each student in the set (FR-009).
6. Commit all absentee records to database.
7. Update dashboard with final attendance statistics (FR-045).

**Alternative Flows:**
- *All students present:* Record no absences; display completion message.

**Exception Flows:**
- *Database unreachable:* Store locally; sync on reconnect (NFR-18).
- *Roster retrieval fails:* Log failure, alert lecturer, prompt manual review via UC-05.

---

## UC-04: Open or Close Attendance Session

- **Actor:** Lecturer (primary)
- **Description:** Lecturer opens a session to begin automated attendance, and closes it to finalise records. Closing triggers UC-03.
- **Preconditions:** Lecturer authenticated (NFR-04); has RBAC permissions (NFR-03); class assigned.
- **Postconditions:** Open: session active, face recognition begins. Close: session closed, UC-03 invoked, records committed (FR-011).

**Main Flow:**
1. Lecturer navigates to attendance section within ≤3 interactions (NFR-08).
2. Selects class.
3. Open: taps 'Open Session' → system activates session → UC-01 begins (FR-008).
4. Class proceeds; system records attendance automatically.
5. Close: taps 'Close Session' → system invokes UC-03.
6. System displays confirmation and finalised attendance summary.

**Alternative Flows:**
- *Scheduled auto-open:* System activates at scheduled time and notifies lecturer.

**Exception Flows:**
- *No students detected after 5 minutes:* Display warning prompting manual verification (NFR-14).
- *Network loss at close:* Queue close event locally; sync on reconnect (NFR-18).
- *Lecturer auth expires during session:* Preserve open session state; resume on re-auth without data loss (NFR-04, NFR-18).

---

## UC-05: Manually Override Attendance

- **Actor:** Lecturer (primary)
- **Description:** Lecturer manually modifies a student's attendance status as contingency for technical failure or incorrect recognition. All overrides logged in immutable audit trail.
- **Preconditions:** Lecturer authenticated (NFR-04); has RBAC permissions (NFR-03); attendance record for target student exists.
- **Postconditions:** Student status updated (FR-010, FR-046); immutable audit log entry created (NFR-05); dashboard updated (FR-045).

**Main Flow:**
1. Navigate to attendance management view.
2. Select session and target student.
3. System displays current status.
4. Lecturer selects new status and confirms.
5. System updates record in database (FR-010, FR-046).
6. Write immutable audit log entry (NFR-05).
7. Refresh dashboard.

**Alternative Flows:**
- *Batch override:* Select multiple students; system applies same status and logs each individually.

**Exception Flows:**
- *Database unreachable:* Store locally; sync on reconnect (NFR-18).
- *Unauthorised class access:* Reject via RBAC (NFR-03).
- *Audit log write fails:* Roll back the status change to preserve audit trail integrity.

---

## UC-06: Export Attendance Records

- **Actor:** Lecturer (primary)
- **Description:** Lecturer exports attendance records for a selected session or date range in PDF or CSV format.
- **Preconditions:** Lecturer authenticated (NFR-04); has RBAC permissions (NFR-03); at least one attendance record exists.
- **Postconditions:** Export file generated and delivered; export operation logged; no modification to underlying records.

**Main Flow:**
1. Navigate to attendance management view.
2. Select export option.
3. Specify scope (single session or date range) and optionally filter (FR-052).
4. Select export format — PDF or CSV (FR-054).
5. Confirm export request.
6. System retrieves records from historical database (FR-011).
7. Generate and deliver export file (FR-012).

**Exception Flows:**
- *No records found:* Inform lecturer; abort export.
- *File generation fails:* Display error; prompt retry.
- *Export volume exceeds limit:* Queue export; notify when ready.

---

## UC-07: Flag Unrecognised Face for Review

- **Actor:** System (primary)
- **Description:** When a face embedding does not match any enrolled student above the confidence threshold, the system flags it for manual review. Extends UC-01.
- **Preconditions:** UC-01 actively processing frames; face detected but no match above threshold found.
- **Postconditions:** Entry created in manual review queue (FR-005); unidentified count updated on dashboard (FR-045); raw image discarded (NFR-01).

**Main Flow:**
1. Receive unmatched face event from UC-01.
2. Create review queue entry (embedding, timestamp, source camera).
3. Increment 'unidentified students' count on dashboard (FR-045).
4. Retain entry until manually processed (via UC-05 or UC-08).

**Alternative Flows:**
- *Duplicate unrecognised face:* Increment occurrence counter on existing entry rather than creating a duplicate.

**Exception Flows:**
- *Review queue storage unreachable:* Buffer locally; sync on reconnect (NFR-18).
- *Malformed embedding:* Discard event.

---

## UC-08: Enrol Student Face Data

- **Actor:** Administrator (primary)
- **Description:** Administrator registers a new student into the face recognition database by capturing multiple face samples and storing embeddings as reference vectors. Also used for promoting entries from the UC-07 review queue.
- **Preconditions:** Admin authenticated (NFR-04); holds Admin role (NFR-03); student record exists in user management (FR-057).
- **Postconditions:** Face embeddings stored in database (FR-013, FR-061); raw images discarded (NFR-01); student eligible for recognition in future sessions.

**Main Flow:**
1. Navigate to user management; select 'Enrol Face Data' for target student (FR-061).
2. System displays capture interface; admin positions student.
3. System captures multiple samples across variations in pose and expression.
4. Extract embedding per sample; discard raw image immediately (NFR-01).
5. Aggregate embeddings into reference set; link to student record (FR-013).
6. Store reference embeddings in face recognition database.
7. Confirm successful enrolment to admin.

**Alternative Flows:**
- *Update existing face data:* New embeddings replace previously stored set (FR-061).
- *Promote from review queue:* Reuse queued embeddings as initial reference set.

**Exception Flows:**
- *No face detected during capture:* Prompt admin to adjust positioning and retry.
- *Face database unreachable:* Abort enrolment; no partial state preserved; notify admin to retry.
- *Student not registered in user management:* Reject; prompt admin to create student record first (FR-057).
