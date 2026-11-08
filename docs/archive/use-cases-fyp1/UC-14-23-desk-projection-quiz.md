# Use Cases: Desk Projection, Gesture Interaction & Quiz Management

**Modules:** 5 (Desk Projection & Gesture Interaction), 6 (Quiz & Content Management)
**Owner:** Yew Sing

---

## UC-14: Project Content onto Desk Surface

- **Actor:** System (primary)
- **Description:** Renders learning content (instructional material, quizzes, polls, interactive controls) onto the student's desk surface via ceiling-mounted short-throw projector. Provides the visual foundation for all desk-based interaction.
- **Preconditions:** Desk unit projector and top-down camera powered and connected; coordinate calibration complete; content available from content management module.
- **Postconditions:** Content visible on desk surface; persistent IDU button displayed (FR-029); projected coordinates aligned with gesture detection (UC-15).

**Main Flow:**
1. Retrieve active content payload from content management module.
2. Compose projected layout including answer options, instructional text, and persistent IDU button (FR-024, FR-029).
3. Apply coordinate calibration to position layout on desk surface (FR-027).
4. Stream composed layout to short-throw projector (FR-024).
5. Ensure IDU button is visually distinct from quiz answer options (NFR-12).
6. Maintain projected display; refresh on content updates.

**Alternative Flows:**
- *No active content:* Project idle screen that still includes the IDU button (FR-029).
- *Quiz projection with timer:* Render countdown reflecting remaining response time (FR-036).

**Exception Flows:**
- *Projector unresponsive:* Alert dashboard (FR-051); continue capturing gesture events for diagnostic logging.
- *Calibration invalid:* Prompt admin to recalibrate before projection is allowed.
- *Connectivity loss:* Display last received content from local cache (NFR-19).

---

## UC-15: Detect Tap Gesture and Map to Selection

- **Actor:** System (primary)
- **Description:** Uses the top-down camera to recognise an intentional tap gesture on the projected desk surface, maps fingertip coordinates to the corresponding UI element, and routes the selection to the appropriate downstream handler. Includes UC-16 when the tapped element is an answer option.
- **Preconditions:** UC-14 actively projecting; top-down camera operational; calibration current and valid.
- **Postconditions:** Confirmed selection mapped to a specific UI element; immediate visual feedback displayed (FR-028); selection forwarded to appropriate downstream UC.

**Main Flow:**
1. Continuously capture frames from top-down camera.
2. Run hand-tracking model per frame to detect hand and finger positions (FR-025).
3. Identify candidate tap gestures — single extended finger with downward motion (FR-025).
4. Distinguish intentional tap from resting hand via finger extension and downward velocity (FR-026).
5. Complete gesture processing within 500ms of the gesture (NFR-28).
6. Apply calibration to translate fingertip position to projected screen coordinates (FR-027).
7. Identify projected UI element underneath fingertip.
8. Display immediate visual feedback (highlight) within 500ms (FR-028, NFR-11).
9. Route selection: answer option → UC-16; IDU button → UC-18; cancel control → UC-17 or UC-19.

**Alternative Flows:**
- *Tap on empty area:* Ignore gesture; no feedback.
- *Drag gesture detected:* Route to drag-and-arrange handlers (FR-032).

**Exception Flows:**
- *Camera feed lost:* Raise sensor failure alert (FR-051); disable gesture interaction until feed restored.
- *Gesture cannot be classified:* Discard candidate event within NFR-10 tolerance bounds.
- *Calibration drift:* Flag desk unit for recalibration.

---

## UC-16: Submit Quiz or Poll Answer

- **Actor:** Student (primary)
- **Description:** Student submits an answer to an active quiz or poll by tapping the corresponding option on the projected desk surface. Included by UC-15. May be extended by UC-17 within the active time limit.
- **Preconditions:** Active quiz or poll pushed to desk (UC-20) and within response time limit (FR-036); student has not yet finalised an answer; UC-15 confirmed tap on an answer option.
- **Postconditions:** Student's selection recorded as current pending response (FR-030); selection visible on projected surface (FR-028); response revisable via UC-17 until time limit expires.

**Main Flow:**
1. Receive confirmed selection event from UC-15.
2. Verify quiz or poll is within active time limit (FR-036).
3. Record student's selection as pending response.
4. Transmit pending selection to content management module in real time (FR-030).
5. Display visual confirmation on projected surface (FR-028).
6. Display cancel/undo control on projected surface (FR-043).
7. When time limit expires: finalise and log response with timestamp (FR-041).

**Alternative Flows:**
- *Student cancels or changes answer:* Student taps cancel/undo control → invoke UC-17 (FR-043).

**Exception Flows:**
- *Time limit expired:* Reject submission; notify student visually (FR-036).
- *Connectivity loss:* Store response locally; sync on reconnect (NFR-19).
- *Log write fails at finalisation:* Retry from local storage.

---

## UC-17: Cancel or Undo Selection

- **Actor:** Student (primary)
- **Description:** Student cancels or undoes a previously submitted quiz or poll answer, allowing them to change their response before the time limit expires. Extends UC-16.
- **Preconditions:** UC-16 has a pending response recorded; quiz or poll still within time limit (FR-036); cancel/undo control visible on projected surface (FR-043).
- **Postconditions:** Previously selected answer cleared or replaced; projected surface reflects updated state; most recent submission within the active window will be finalised at expiry.

**Main Flow:**
1. Receive confirmed tap on cancel/undo control from UC-15.
2. Verify quiz or poll is within active time limit (FR-036).
3. Clear student's pending response (FR-043).
4. Update projected surface — no answer currently selected.
5. Transmit cleared state to content management module (FR-030).
6. Student may invoke UC-16 again to submit a different answer.

**Alternative Flows:**
- *Direct re-tap on different answer:* Treat as undo of previous selection + fresh UC-16 invocation.

**Exception Flows:**
- *Time limit expired:* Reject cancellation; previously submitted response stands (FR-036).
- *Connectivity loss:* Update local state immediately; sync cleared state on reconnect (NFR-19).

---

## UC-18: Flag 'I Don't Understand'

- **Actor:** Student (primary)
- **Description:** Student anonymously flags confusion by tapping the persistent IDU button. Submission contributes to the aggregated confusion rate on the lecturer dashboard but cannot be traced to the individual student.
- **Preconditions:** UC-14 projecting with IDU button visible (FR-029); UC-15 confirmed tap on IDU button; IDU button visually distinct from answer options (NFR-12).
- **Postconditions:** Anonymous IDU event recorded; confusion rate updated on dashboard within 3 seconds (NFR-22); no mechanism to trace submission to individual student (NFR-02); short grace period open for UC-19.

**Main Flow:**
1. Receive confirmed tap on IDU button from UC-15.
2. Record anonymous IDU event; anonymise at point of aggregation (NFR-02).
3. Log event with timestamp for post-session review (FR-041).
4. Aggregate IDU events; compute confusion rate as percentage of students flagging confusion (FR-039).
5. Push updated confusion rate to lecturer dashboard within 3 seconds (NFR-22).
6. If rate ≥ 20% → yellow alert; if rate ≥ 50% → red alert (FR-042).
7. Display cancel control on projected surface for grace period (e.g. 3 seconds) (FR-044).

**Alternative Flows:**
- *Grace period elapses without cancel:* IDU submission stands until lecturer resets counter (UC-23).

**Exception Flows:**
- *Connectivity loss:* Store IDU event locally; sync on reconnect (NFR-19).
- *Anonymisation fails:* Discard event rather than risk leaking student identity (NFR-02).

---

## UC-19: Cancel 'I Don't Understand' Submission

- **Actor:** Student (primary)
- **Description:** Student cancels a recently submitted IDU flag within the short grace period. Extends UC-18. Anonymity preserved throughout.
- **Preconditions:** UC-18 recorded an IDU event within the configured grace period (FR-044); cancel control visible on projected surface.
- **Postconditions:** IDU event retracted from confusion rate (FR-044); dashboard updated within 3 seconds (NFR-22); anonymity preserved (NFR-02).

**Main Flow:**
1. Receive confirmed tap on IDU cancel control from UC-15 within the grace period.
2. Verify grace period has not yet expired (FR-044).
3. Retract most recent IDU event from this desk in the active grace window.
4. Update aggregated confusion rate (FR-039).
5. Push corrected rate to dashboard within 3 seconds (NFR-22).
6. Remove IDU cancel control from projected surface.

**Exception Flows:**
- *Grace period expired:* Reject cancellation; IDU event stands until lecturer resets (UC-23).
- *Connectivity loss:* Store cancellation locally; sync on reconnect (NFR-19).

---

## UC-20: Create and Push Quiz or Poll

- **Actor:** Lecturer (primary)
- **Description:** Lecturer composes a quiz or poll question with answer options, configures a time limit, and pushes it to all student desk surfaces. Includes UC-21 when the time limit elapses.
- **Preconditions:** Lecturer authenticated (NFR-04); has RBAC permissions (NFR-03); at least one desk unit operational and connected.
- **Postconditions:** Quiz or poll pushed to all connected desks and active (FR-035); countdown running (FR-036); student responses being collected via UC-16.

**Main Flow:**
1. Navigate to quiz/poll creation section.
2. Compose question text and up to 4 answer options (FR-034, NFR-09).
3. Optionally mark correct answer; configure time limit (e.g. 15 or 30 seconds) (FR-036).
4. Push to all student desk surfaces within ≤5 interactions from dashboard home (NFR-09).
5. System displays question on all connected desks via UC-14 (FR-035).
6. Start response countdown (FR-036).
7. Students respond via UC-16 throughout the active window.
8. Time limit expires → invoke UC-21.

**Alternative Flows:**
- *Use saved quiz:* Load from saved library instead of composing from scratch.
- *Early manual close:* Lecturer manually closes before time limit → immediately invoke UC-21.

**Exception Flows:**
- *Desk units offline at push:* Push to all reachable desks; flag offline desks on dashboard (FR-051).
- *Desk unit loses connectivity after push:* Desk retains question and stores responses locally (NFR-19).
- *Incomplete question:* Block push; prompt lecturer to complete required fields.

---

## UC-21: Close Quiz and Display Results

- **Actor:** System (primary)
- **Description:** When the time limit expires (or lecturer manually closes), stops accepting responses, computes aggregate distribution, and displays results on both the dashboard and all student desk surfaces. Included by UC-20.
- **Preconditions:** Active quiz or poll pushed via UC-20; system has been collecting responses via UC-16.
- **Postconditions:** Quiz or poll closed (FR-036); aggregate distribution displayed on dashboard and all desks (FR-037); all responses and closure event logged (FR-041).

**Main Flow:**
1. Detect time limit expiry or receive early-close command from UC-20.
2. Stop accepting responses (FR-036).
3. Compute percentage of students per answer option.
4. Push aggregate distribution to lecturer dashboard (FR-037, FR-048).
5. Display aggregate distribution on all student desks via UC-14 (FR-037).
6. Log all individual responses and closure event with timestamps (FR-041).
7. Update dashboard with latest analytics (FR-048, FR-049).

**Alternative Flows:**
- *Lecturer-only result view:* Display results only on dashboard; configure at quiz creation time.

**Exception Flows:**
- *Desk units unreachable:* Display results on reachable desks; offline desks display from local cache on reconnect (NFR-19).
- *Log write fails:* Retry from local buffer; enforce 24-month retention (NFR-23).

---

## UC-22: View Individual Student Response Breakdown

- **Actor:** Lecturer (primary)
- **Description:** Lecturer opens a separate view listing per-student responses for a given quiz, showing who answered correctly and who did not. Not visible to students.
- **Preconditions:** Lecturer authenticated (NFR-04); has RBAC permissions (NFR-03); quiz exists with recorded individual student responses.
- **Postconditions:** Lecturer viewed per-student breakdown (FR-038); no modification to underlying records; breakdown not displayed to students.

**Main Flow:**
1. Navigate to analytics or quiz history section.
2. Select target quiz or poll session.
3. Open individual response breakdown view (FR-038).
4. Retrieve response log including each student's selected option and timestamp (FR-041).
5. Display per-student answer and correctness status.
6. Optionally filter by question, student, or correctness (FR-052).

**Alternative Flows:**
- *Export breakdown:* Export as PDF or CSV for offline review (FR-054).

**Exception Flows:**
- *Response records unavailable:* Display error; no partial breakdown shown.
- *Unauthorised quiz access:* Reject via RBAC (NFR-03).

---

## UC-23: Reset Confusion Alert and Counter

- **Actor:** Lecturer (primary)
- **Description:** Lecturer resets the aggregated IDU confusion rate and associated dashboard alert, typically after re-explaining a concept. Clears active confusion state; preserves historical IDU logs.
- **Preconditions:** Lecturer authenticated (NFR-04); has RBAC permissions (NFR-03); non-zero confusion rate or active yellow/red alert currently displayed (FR-039, FR-042).
- **Postconditions:** Active confusion rate reset to zero (FR-040); yellow/red alert cleared (FR-042); historical IDU logs preserved (FR-041, NFR-23).

**Main Flow:**
1. Locate confusion alert section on dashboard (NFR-15).
2. Tap 'Reset Confusion' control.
3. System prompts for confirmation.
4. Lecturer confirms.
5. System clears active confusion rate and dismisses alerts (FR-040, FR-042).
6. Record reset event with actor identity and timestamp.
7. Dashboard refreshed to show zero confusion rate.

**Alternative Flows:**
- *Cancel reset at confirmation prompt:* Confusion rate and alert remain unchanged.

**Exception Flows:**
- *Server unreachable:* Queue reset locally; apply on reconnect (NFR-18).
- *Audit log write fails:* Roll back reset to maintain consistency between displayed state and audit trail.
