# Use Cases: Module 2 — Dashboard and Notifications

**Module:** 2 (Dashboard and Notifications) | **Owner:** Shino
**Requirements:** FR-201–FR-212, NFR-05, NFR-09, NFR-14, NFR-17, NFR-20

---

## UC-201: View student dashboard

- **Actor:** Student
- **Description:** The student sees on one screen their attendance status, upcoming deadlines, latest announcements, notifications and ongoing classroom activities.
- **Preconditions:** The student is logged in and enrolled in at least one course.
- **Postconditions:** The dashboard shows only the data of the student's own courses.

**Main Flow:**
1. Student opens the mobile or web app. The dashboard is the home screen (NFR-09).
2. System shows urgent and important notifications at the top, above general notifications (FR-204).
3. System loads, for the student's enrolled courses only (FR-203, NFR-05):
   - attendance status and attendance rate per course (from Module 3),
   - upcoming deadlines, such as quiz closing times (from Module 6),
   - latest announcements,
   - ongoing classroom activities, such as an open interaction session (Module 5) or an open quiz (Module 6).
4. The dashboard finishes loading within 5 seconds (NFR-17) (FR-201).
5. Student taps an item to open the related screen (for example an open quiz opens UC-604).

**Alternative Flows:**
- *Student is enrolled in no course:* the dashboard shows "No courses found" and the notification feed.
- *No ongoing activity:* the activity section shows "No activity right now".

**Exception Flows:**
- *One section cannot be loaded:* that section shows "Unavailable, pull to refresh" and the other sections still display.

---

## UC-202: View lecturer dashboard

- **Actor:** Lecturer
- **Description:** The lecturer sees an overview of class attendance, student participation, assessment activities and notifications for the courses they teach.
- **Preconditions:** The lecturer is logged in and teaches at least one course.
- **Postconditions:** The dashboard shows only the lecturer's own courses.

**Main Flow:**
1. Lecturer opens the app. The dashboard is the home screen (NFR-09).
2. System shows urgent and important notifications at the top (FR-204). These include at-risk alerts (FR-210) and pending face verification reviews (FR-212).
3. System loads, for the courses the lecturer teaches only (FR-203, NFR-05):
   - class attendance overview, such as the attendance rate of the latest sessions (from Module 3),
   - student participation in recent interaction sessions (from Module 5),
   - assessment activities, such as open quizzes and short answers waiting to be scored (from Module 6) (FR-202).
4. The dashboard finishes loading within 5 seconds (NFR-17).
5. Lecturer taps an item to open the related screen (for example a pending short answer opens UC-606).

**Exception Flows:**
- *One section cannot be loaded:* same as UC-201.

---

## UC-203: Deliver a notification

- **Actor:** System (triggered by events from Modules 1, 3, 4, 6 and 7)
- **Description:** When another module raises an event, the system works out the recipients and priority and delivers the notification.
- **Preconditions:** The triggering event has happened and the recipient has an active account.
- **Postconditions:** The notification is in the recipient's feed. Urgent and important notifications are also pushed or emailed.

**Main Flow:**
1. A module raises an event (see the table below).
2. System decides the recipients and assigns one priority: urgent, important or general (FR-205).
3. System saves the notification to each recipient's notification feed (FR-206).
4. If the priority is urgent or important, the system sends a push notification or email within the configured time (default 60 seconds) (FR-207).
5. General notifications appear in the feed only (FR-207).

| Event | Raised by | Recipient | Default priority | FR |
|-------|-----------|-----------|------------------|----|
| `attendance.recorded` | Module 4 (FR-406) | Student | Important | FR-209 |
| Student flagged at-risk | Module 7 (FR-709) | Lecturer | Important | FR-210 |
| Quiz published, quiz deadline approaching | Module 6 (FR-605) | Enrolled students | Important | FR-211 |
| `face_enrolment.result` | Module 1 (FR-114) | Student | Important | FR-212 |
| `face_enrolment.pending_review` | Module 1 (FR-113) | Lecturers of the student's courses | General | FR-212 |
| `face.unrecognised` | Module 4 (FR-407) | Lecturer | Important | FR-212 |

The default priority of each event is a configuration value, not hard-coded. The priorities for FR-210 and FR-211 are fixed by those requirements.

**Alternative Flows:**
- *Recipient uses Android:* a push notification is sent (FR-208).
- *Recipient uses iOS:* the notification is shown in the app and sent by email, because iOS push is not supported (FR-208).
- *Recipient uses the web app:* the notification is shown in the app, and urgent and important ones are also sent by email.

**Exception Flows:**
- *Push or email service is unavailable:* the notification stays in the in-app feed and the failure is logged (NFR-14).
- *Recipient has deactivated their account:* no notification is sent.

---

## UC-204: View notification feed

- **Actor:** Student, Lecturer
- **Description:** The user reads all notifications they have received, with the most important first.
- **Preconditions:** The user is logged in.
- **Postconditions:** None.

**Main Flow:**
1. User opens Notifications.
2. System lists the user's notifications ordered by priority (urgent, important, general) and then by time received, newest first (FR-206).
3. Each item shows its priority as a text label or icon as well as a colour (NFR-20), the message, and the time.
4. User taps a notification and the app opens the related screen (for example the attendance history, a quiz, or the at-risk list).

**Alternative Flows:**
- *No notifications:* the feed shows "You're all caught up".
- *Related item no longer exists (for example a deleted quiz):* the app shows "This item is no longer available".
