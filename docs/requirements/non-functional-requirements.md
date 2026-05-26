# Non-Functional Requirements

**Project:** SmartClass — UM FYP1
**NFR ownership:** Security, Usability, Reliability (Yew Sing) | Performance, Accessibility, Scalability (Shino)

---

## Security

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-01 | Data Privacy | The system shall store face data as mathematical embedding vectors only and shall discard raw facial images immediately after the embedding extraction step. | Must Have | FR-002, FR-013 |
| NFR-02 | Data Privacy | The system shall ensure that 'I Don't Understand' submissions are anonymised at the point of aggregation such that no mechanism exists to trace a submission back to an individual student. | Must Have | FR-041, FR-044 |
| NFR-03 | Access Control | The system shall enforce role-based access control (RBAC) with three distinct roles — Student, Lecturer, and Administrator — where each role can only access the functions and data assigned to it. | Must Have | FR-008, FR-010, FR-012, FR-013, FR-058 |
| NFR-04 | Access Control | The system shall require authenticated login for all Lecturer and Administrator functions; unauthenticated requests shall be rejected. | Must Have | FR-008, FR-040, FR-059 |
| NFR-05 | Audit Trail | The system shall log all attendance overrides with the actor identity, original status, new status, and timestamp; this log shall be immutable and non-deletable by any user role. | Must Have | FR-010, FR-046 |
| NFR-06 | Transmission Security | All data transmitted between desk units, sensors, the central server, and the Lecturer dashboard shall be encrypted in transit using TLS 1.2 or higher. | Must Have | FR-030, FR-041, FR-048 |
| NFR-07 | Credential Security | The system shall store all user passwords using a one-way cryptographic hash with salt and shall never store or transmit passwords in plain text. | Must Have | FR-059 |

## Usability

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-08 | Lecturer Workflow | The Lecturer shall be able to open or close an attendance session window within no more than 3 user interactions from the dashboard home screen. | Must Have | FR-008 |
| NFR-09 | Lecturer Workflow | The Lecturer shall be able to create a quiz or poll question with up to four answer options and push it to all desk surfaces within no more than 5 user interactions. | Must Have | FR-036, FR-037 |
| NFR-10 | Gesture Accuracy | The tap gesture recognition system shall achieve a false-positive rate of no more than 5% and a false-negative rate of no more than 10% under normal classroom lighting conditions. | Must Have | FR-025, FR-026, FR-027 |
| NFR-11 | Feedback Latency | The visual confirmation of a student's selection shall appear on the projected desk surface within 500 milliseconds of a confirmed tap gesture. | Must Have | FR-028 |
| NFR-12 | Button Distinction | The 'I Don't Understand' button shall be visually distinct from quiz answer options at all times through a combination of different colour, shape, and position. | Must Have | FR-029, FR-035 |
| NFR-13 | Dashboard Readability | The confusion rate alert indicators on the Lecturer dashboard shall meet a minimum contrast ratio of 4.5:1 (WCAG AA standard) and shall be distinguishable at a viewing distance of up to 3 metres. | Must Have | FR-044, FR-051 |
| NFR-14 | Error Visibility | If the face recognition pipeline detects no students within the first 5 minutes of an active session, the system shall display a visible warning on the Lecturer dashboard. | Could Have | FR-001, FR-007, FR-051 |
| NFR-15 | Dashboard Clarity | The Lecturer dashboard shall present attendance status, active student responses, and environmental conditions as clearly labelled sections accessible without navigating away from the main dashboard view. | Must Have | FR-058 |

## Reliability

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-16 | Availability | The system shall maintain an uptime of at least 99% during scheduled class hours (Monday–Friday, 08:00–18:00). | Must Have | All modules |
| NFR-17 | Face Recognition Accuracy | The face recognition pipeline shall achieve a true positive rate of at least 95% and a false positive rate of no more than 2% under controlled classroom lighting at up to 6 metres. | Must Have | FR-001, FR-002, FR-003, FR-004 |
| NFR-18 | Network Resilience — Attendance | If the system loses network connectivity during an active attendance session, it shall continue to record detections locally and synchronise them to the central database upon reconnection without data loss. | Should Have | FR-007, FR-011 |
| NFR-19 | Network Resilience — Desk Unit | If a desk unit loses connectivity to the central server during an active quiz, it shall retain the active question and continue to accept and store student responses locally until the connection is restored. | Should Have | FR-037, FR-038 |
| NFR-20 | Actuation Response Time | Actuation commands to air conditioning and lighting shall be delivered and acknowledged within 2 seconds of the trigger condition being met under normal network conditions. | Must Have | FR-018, FR-019, FR-022, FR-023 |
| NFR-21 | Failure Isolation | A failure in any single module shall not cause other modules to become unavailable; each module shall degrade independently without affecting the rest of the system. | Must Have | All modules |
| NFR-22 | Confusion Rate Freshness | The confusion rate displayed on the Lecturer dashboard shall update within 3 seconds of a student submitting an 'I Don't Understand' event. | Must Have | FR-041, FR-044, FR-049 |
| NFR-23 | Data Retention | All attendance records, quiz logs, poll logs, and confusion event logs shall be retained and remain queryable for a minimum of 24 months. | Should Have | FR-011, FR-043, FR-053 |
| NFR-24 | Recovery Time | Following an unplanned system restart or crash, all modules shall return to an operational state within 3 minutes without requiring manual intervention beyond power restoration. | Should Have | All modules |

## Performance

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-25 | Face Recognition Processing Speed | The system shall complete face detection, embedding extraction, and matching within 1 second per frame under normal classroom conditions. | Must Have | FR-001, FR-002, FR-003 |
| NFR-26 | Attendance Confirmation Time | The system shall mark a student as present within 3 seconds after a successful face match is confirmed. | Must Have | FR-007 |
| NFR-27 | Dashboard Update Latency | The system shall update lecturer dashboard analytics (attendance, quiz results, environment data) within 2 seconds in real time. | Must Have | FR-045, FR-048, FR-049 |
| NFR-28 | Gesture Processing Speed | The system shall process and confirm tap gesture recognition within 500 milliseconds. | Must Have | FR-025, FR-026, FR-027 |
| NFR-29 | Sensor Data Processing Delay | The system shall process and transmit environmental sensor readings within 5 seconds of collection. | Must Have | FR-014, FR-015, FR-016, FR-017 |
| NFR-30 | Concurrent Desk Processing | The system shall support at least 30 simultaneous desk units without exceeding 10% performance degradation. | Should Have | FR-031, FR-037 |

## Accessibility

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-31 | Touch Target Accessibility | All interactive UI elements shall have a minimum touch target size of 48×48 dp. | Must Have | FR-034, FR-045 |
| NFR-32 | Visual Contrast Compliance | All UI components shall meet WCAG 2.1 AA contrast standards for readability. | Must Have | FR-045, FR-047 |
| NFR-33 | Alert Visibility | All alerts shall be displayed using both text and visual indicators. | Must Have | FR-042, FR-051 |

## Scalability

| ID | Category | Description | Priority | Linked FR |
|----|----------|-------------|----------|-----------|
| NFR-34 | Multi-Class Support | The system shall support managing multiple classes without requiring logout. | Must Have | FR-058 |
| NFR-35 | Concurrent User Capacity | The system shall support at least 1,000 concurrent users without more than 10% performance degradation. | Must Have | FR-045, FR-048 |
| NFR-36 | Data Storage Capacity | The system shall support at least 10,000 student records and 24 months of historical logs. | Must Have | FR-011, FR-053 |
| NFR-37 | Real-Time Synchronisation Scalability | The system shall support real-time data synchronisation across multiple sessions and devices. | Should Have | FR-014, FR-048 |
| NFR-38 | Modular Expansion | The system shall allow new modules to be added without modifying existing core modules. | Must Have | FR-021, FR-050 |
| NFR-39 | Platform Expansion | The system shall support deployment across multiple operating systems without functional loss. | Must Have | FR-031 |
