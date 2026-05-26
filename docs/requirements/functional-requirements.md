# Functional Requirements

**Project:** SmartClass — UM FYP1
**Modules owned:** 1, 2, 5, 6 (Yew Sing) | 3, 4, 7, 8 (Shino)

---

## Module 1 — Face Detection & Recognition

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-001 | The system shall detect human faces from the live camera feed at a distance of up to 6 metres. | Must Have | System |
| FR-002 | The system shall extract a face embedding from each detected face and compare it against the student database. | Must Have | System |
| FR-003 | The system shall confirm a face match only when the confidence score meets or exceeds a predefined threshold. | Must Have | System |
| FR-004 | The system shall sample multiple frames continuously and aggregate results before confirming a match, rather than relying on a single frame. | Must Have | System |
| FR-005 | The system shall flag unrecognised faces — detected but not matched to any record in the database — for manual review. | Should Have | System |
| FR-006 | The system shall operate across two ceiling-mounted front-facing cameras simultaneously to ensure full classroom coverage. | Must Have | System |

## Module 2 — Attendance Logging & Management

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-007 | The system shall automatically mark a student as present upon the first confirmed face match within the active session window. | Must Have | System |
| FR-008 | The system shall define an attendance session window that is opened and closed by the lecturer, during which attendance can be recorded. | Must Have | Lecturer |
| FR-009 | The system shall automatically mark students with no confirmed detection by the end of the session window as absent. | Must Have | System |
| FR-010 | The system shall allow the lecturer to manually override the attendance status of any student as a contingency for technical failure. | Should Have | Lecturer |
| FR-011 | The system shall maintain a historical record of attendance across all past sessions for each enrolled student. | Must Have | System |
| FR-012 | The system shall allow the lecturer to export attendance records for a selected session or date range. | Should Have | Lecturer |
| FR-013 | The system shall allow an administrator to enrol new students into the face database by registering their face samples at the start of each semester. | Must Have | Admin |

## Module 3 — Environmental Sensing

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-014 | The system shall measure the room temperature using a temperature sensor at regular intervals and transmit the readings to the ambient control module. | Must Have | System |
| FR-015 | The system shall count the number of people in the classroom using the existing camera infrastructure and transmit the occupancy data to the ambient control module. | Must Have | System |
| FR-016 | The system shall measure the light intensity level in the classroom using an LDR sensor at regular intervals and transmit the readings to the ambient control module. | Could Have | System |
| FR-017 | The system shall monitor the CO2 level in the classroom using a CO2 sensor at regular intervals and transmit the readings to the ambient control module. | Could Have | System |

## Module 4 — Automated Environment Actuation

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-018 | The system shall automatically adjust the air conditioning when the room temperature exceeds or falls below a predefined threshold. | Must Have | System |
| FR-019 | The system shall automatically turn off all electrical appliances when the room is detected as empty for longer than a predefined duration. | Must Have | System |
| FR-020 | The system shall allow the lecturer or administrator to manually override the automated environment controls at any time. | Should Have | Lecturer / Admin |
| FR-021 | The system shall automatically adjust classroom lighting based on the ambient light intensity detected by the LDR sensor. | Could Have | System |
| FR-022 | The system shall automatically turn on the classroom lights immediately when occupancy is first detected after the room has been empty. | Must Have | System |
| FR-023 | The system shall automatically turn on the air conditioning only when the number of detected occupants meets or exceeds a predefined threshold (e.g. 5 students) for a continuous duration (e.g. 1 minute). | Must Have | System |

## Module 5 — Desk Projection & Gesture Interaction

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-024 | The system shall project learning content onto the student's desk surface via a ceiling-mounted short-throw projector. | Must Have | System |
| FR-025 | The system shall detect an intentional tap gesture using a top-down camera by recognising a single extended finger with a downward motion. | Must Have | System |
| FR-026 | The system shall distinguish an intentional tap from a resting hand based on finger extension and downward velocity. | Must Have | System |
| FR-027 | The system shall map the detected fingertip position to the corresponding option on the projected desk surface using coordinate calibration. | Must Have | System |
| FR-028 | The system shall provide immediate visual feedback on the projected surface when a student's selection is registered, such as highlighting the selected option. | Must Have | System |
| FR-029 | The system shall display a persistent 'I Don't Understand' button on the projected desk surface throughout the session, allowing students to flag confusion at any time. | Must Have | Student |
| FR-030 | The system shall transmit the student's confirmed selection to the content management module in real time upon a confirmed tap gesture. | Must Have | System |
| FR-031 | The system shall be deployed as a single fully functional desk unit as proof of concept, with the architecture designed to scale by replicating the same hardware and software stack per additional desk. | Must Have | System |
| FR-032 | The system shall allow students to drag and arrange elements on the projected desk surface using finger gestures. | Should Have | Student |
| FR-033 | The system shall allow students to draw and construct UML diagrams on the projected desk surface using finger gestures, recognising basic UML shapes and connectors. | Could Have | Student |
| FR-043 | The system shall display a cancel or undo option on the projected desk surface after a selection is made, allowing the student to change their answer before the time limit expires. | Must Have | Student |
| FR-044 | The system shall allow a student to cancel an 'I Don't Understand' submission within a short grace period (e.g. 3 seconds) after tapping the button. | Must Have | Student |

## Module 6 — Quiz & Content Management

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-034 | The system shall allow the lecturer to create quiz and poll questions including the question text and answer options. | Must Have | Lecturer |
| FR-035 | The system shall display quiz and poll content on the student's desk surface when activated by the lecturer. | Must Have | System |
| FR-036 | The system shall enforce a configurable time limit per quiz or poll (e.g. 15 or 30 seconds), after which the question automatically closes and no further responses are accepted. | Must Have | System |
| FR-037 | The system shall display quiz or poll results on the lecturer's dashboard and on all student desk surfaces upon closing of the time limit, showing the percentage of students who selected each option. | Must Have | System |
| FR-038 | The system shall allow the lecturer to view a breakdown of individual student responses showing who answered correctly and incorrectly in a separate menu. | Must Have | Lecturer |
| FR-039 | The system shall anonymously aggregate 'I Don't Understand' responses and display the current confusion rate as a percentage on the lecturer's dashboard in real time. | Must Have | System |
| FR-040 | The system shall allow the lecturer to reset the confusion alert and counter at any time, such as after re-explaining a concept. | Should Have | Lecturer |
| FR-041 | The system shall log all quiz responses, poll responses, and 'I Don't Understand' events with timestamps for post-session review. | Should Have | System |
| FR-042 | The system shall trigger a yellow alert on the lecturer's dashboard when the confusion rate reaches or exceeds 20% of students, and a red alert when it reaches or exceeds 50%. | Must Have | System |

## Module 7 — Real-time Analytics & Lecturer Dashboard

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-045 | The system shall display real-time attendance statistics, including present, absent, and unidentified students during an active class session. | Must Have | Lecturer |
| FR-046 | The system shall allow lecturers to manually modify attendance records when face recognition results are inaccurate or incomplete. | Must Have | Lecturer |
| FR-047 | The system shall visualize classroom analytics using charts, graphs, and heatmaps for attendance, participation, and engagement. | Should Have | Lecturer |
| FR-048 | The system shall display real-time student response analytics from the Interactive Learning Platform, including poll results and quiz answer distributions. | Must Have | Lecturer, Student |
| FR-049 | The system shall update dashboard information automatically without requiring manual refresh. | Must Have | System |
| FR-050 | The system shall display classroom environmental data, including temperature, humidity, lighting level, and occupancy status in real time. | Should Have | System |
| FR-051 | The system shall generate alerts when abnormal conditions are detected, such as low attendance, poor engagement, high temperature, or sensor failure. | Should Have | System |
| FR-052 | The system shall allow lecturers to filter analytics data by class, session date, student, or module activity. | Should Have | Lecturer |
| FR-053 | The system shall provide historical analytics reports for attendance, environmental conditions, and student participation trends. | Could Have | Lecturer |
| FR-054 | The system shall support exporting analytics reports in PDF or CSV format. | Could Have | Lecturer |
| FR-055 | The system shall allow students to view their own attendance history across all past sessions. | Should Have | Student |
| FR-056 | The system shall allow lecturers to view the confusion rate in the dashboard. | Should Have | Lecturer |

## Module 8 — User Management

| ID | Description | Priority | Actor |
|----|-------------|----------|-------|
| FR-057 | The system shall allow administrators to create, update, and delete user accounts for lecturers, students, and administrators. | Must Have | Admin |
| FR-058 | The system shall support role-based access control to restrict system features based on user roles. | Must Have | System |
| FR-059 | The system shall authenticate users using secure username/email and password login credentials. | Must Have | System |
| FR-060 | The system shall maintain user profile information including name, matric ID, contact information, and assigned classes. | Should Have | System |
| FR-061 | The system shall allow administrators to enroll student face data into the face recognition database at the beginning of each semester. | Must Have | Admin |
| FR-062 | The system shall allow administrators to remove or update student enrollment records and face data when students change classes or semesters. | Must Have | Admin |

---

## Notes

- Modules 1 and 2 share the same front-ceiling camera hardware. Module 3 reuses the same camera infrastructure for occupancy counting — no additional cameras are required.
- Module 5 uses a separate top-down camera per desk unit, distinct from the front-ceiling cameras. These two camera layers serve opposing angles and cannot be shared.
- FR-022 and FR-023 implement tiered actuation logic — lights respond immediately to occupancy while AC requires sustained occupancy above a threshold (deliberate energy efficiency decision).
- FR-039 and FR-042 implement anonymous, aggregated confusion tracking. Individual student identities are not revealed when the 'I Don't Understand' button is triggered.
- FR-031 scopes Module 5 to a single desk unit for FYP. Scalability is argued architecturally.
- FR-061 (Module 8) and FR-013 (Module 2) both address face enrolment at different scopes; both are retained.
- Specific threshold values (temperature range, occupancy count, confusion percentage, timer duration) are configurable parameters defined during implementation.
