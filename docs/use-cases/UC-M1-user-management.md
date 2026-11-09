# Use Cases: Module 1 — User Management

**Module:** 1 (User Management) | **Owner:** Yew Sing
**Requirements:** FR-101–FR-118, NFR-01, NFR-03–NFR-06

---

## UC-101: Log in with SPeCTRUM (Moodle) credentials

- **Actor:** Student, Lecturer
- **Description:** The user signs in with their SPeCTRUM username and password. SmartClass checks them against Moodle and creates the SmartClass account on first login.
- **Preconditions:** The user has an account in (simulated) SPeCTRUM; Moodle is reachable.
- **Postconditions:** The user holds access and refresh tokens; the SmartClass account exists with the right role; courses and enrolments are up to date.

**Main Flow:**
1. User enters username and password in the mobile or web app.
2. Backend requests a Moodle web-service token with these credentials (FR-101). The password is not stored or logged (NFR-05).
3. Backend gets the Moodle user's profile and course list with that token.
4. If no SmartClass account exists, the system creates one (FR-102). The role is lecturer if the user teaches any course, otherwise student.
5. System syncs the user's courses and enrolments (FR-104).
6. System issues access and refresh tokens (FR-106) and opens the role's home screen.

**Alternative Flows:**
- *Existing account:* step 4 updates name, email and role from Moodle instead of creating an account.
- *User enrolled in no course:* the account is created as student; the home screen says no courses were found.

**Exception Flows:**
- *Wrong credentials:* Moodle refuses the token; show "Invalid username or password" (don't say which one was wrong).
- *Moodle unreachable:* show "SPeCTRUM is unavailable, try again later". Users already logged in keep working via refresh tokens (NFR-20).
- *Account deactivated by admin:* login is refused even with valid Moodle credentials, and the user is told the account is deactivated. This message only appears after the password is confirmed.

---

## UC-102: Administrator login and account management

- **Actor:** Admin
- **Description:** The admin signs in with a local email and password and manages accounts.
- **Preconditions:** An admin account exists (seeded, or created by another admin).
- **Postconditions:** Account changes are saved and audited (FR-118).

**Main Flow:**
1. Admin logs in to the web app with email and password (FR-103).
2. Admin opens Users and searches or filters accounts (FR-108).
3. Admin deactivates or reactivates an account, or creates another admin.
4. System records an audit entry (FR-118).

**Exception Flows:**
- *Wrong credentials:* generic error; repeated failures are rate-limited.
- *Admin deactivates their own account:* refused.

---

## UC-103: Sync courses and enrolments from Moodle

- **Actor:** System (scheduled), Lecturer or Admin (manual)
- **Description:** Brings SmartClass's courses, class lists and lecturer assignments in line with Moodle.
- **Preconditions:** The Moodle service token is configured.
- **Postconditions:** Courses, enrolments and lecturer assignments match Moodle.

**Main Flow:**
1. Triggered on login (for that user), on a schedule, or by a "Sync now" action (FR-104).
2. System fetches the courses and enrolled users from Moodle.
3. System adds new courses and enrolments, and removes enrolments no longer in Moodle.
4. System records the sync time and result.

**Exception Flows:**
- *Moodle unreachable:* keep current data, record the failure, retry next cycle.

---

## UC-104: Self-enrol face data with matric-card verification

- **Actor:** Student (primary), System
- **Description:** The student registers their face in the mobile app. The system checks the selfies against the photo and matric number on their UM matric card, with no staff involved when both checks pass.
- **Preconditions:** Student is logged in; face status is "not enrolled" or "rejected".
- **Postconditions:** Status is "active" (embeddings registered) or "pending review" (UC-105). Images are deleted after the decision (NFR-01).

**Main Flow:**
1. Student opens Face Enrolment and reads the PDPA consent notice.
2. Student accepts. System records consent version and timestamp (FR-109).
3. App guides the student through several selfies (front, slight left, slight right) (FR-110).
4. App asks for a photo of the front of the matric card.
5. Backend detects the face on the card and compares it with the selfies (FR-111a).
6. Backend runs OCR on the card and checks the matric number (and name) against the logged-in account (FR-111b).
7. Both checks pass → system stores the selfie embeddings and sets status to "active" (FR-112).
8. System deletes the selfie and card images (NFR-01) and tells the student enrolment is complete (FR-114).

**Alternative Flows:**
- *Either check fails (low similarity, unreadable or mismatched matric number):* status → "pending review"; UC-105 starts. Student sees "Your submission is being checked by a lecturer".
- *Poor image quality (no face found, blurry):* the app asks the student to retake before submitting.

**Exception Flows:**
- *Student declines consent:* no capture; status stays "not enrolled". Attendance falls back to lecturer override.
- *Upload fails:* nothing is stored; student can retry.

---

## UC-105: Review a face enrolment submission

- **Actor:** Lecturer (primary), Admin (fallback)
- **Description:** A lecturer of one of the student's courses decides on a submission that failed automatic verification, by comparing the selfie with the card. No one has to recognise the student from memory.
- **Preconditions:** A submission is "pending review".
- **Postconditions:** Status is "active" or "rejected" with a reason; decision audited; images deleted.

**Main Flow:**
1. Lecturer opens the Face Verification queue (FR-113).
2. System shows selfie and card side by side, the OCR result, the account's matric number and name, and the similarity score.
3. Lecturer approves or rejects with a reason.
4. Approve → embeddings registered, status "active". Reject → status "rejected" with reason.
5. System notifies the student (FR-114), writes an audit entry (FR-118) and deletes the images (NFR-01).

**Alternative Flows:**
- *No lecturer acts:* an admin can make the same decision (FR-117).

---

## UC-106: Withdraw consent / reset face data

- **Actor:** Student (withdraw), Admin (reset)
- **Preconditions:** Student has face data.
- **Postconditions:** Embeddings deleted; status "not enrolled"; audited.

**Main Flow:**
1. Student chooses "Withdraw consent" in Profile and confirms (FR-116); or the admin chooses "Reset face data" (FR-117).
2. System deletes the student's embeddings at once (NFR-03).
3. System writes an audit entry and tells the student that attendance will need manual marking.

---

## UC-107: View profile

- **Actor:** Student, Lecturer
- **Main Flow:** User opens Profile. System shows name, matric/staff number, email, faculty, courses (read-only, from Moodle) and face enrolment status (students) (FR-107, FR-115).
