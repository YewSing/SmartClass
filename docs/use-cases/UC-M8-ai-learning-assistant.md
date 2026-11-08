# Use Cases: Module 8 — Personalized Learning (AI Learning Assistant)

**Module:** 8 | **Owner:** Yew Sing
**Requirements:** FR-801–FR-814 (FR-820–FR-824 deferred until Module 6 exists), NFR-08, NFR-09, NFR-14, NFR-15, NFR-18, NFR-19, NFR-21, NFR-28

---

## UC-801: Sync course materials into the knowledge base

- **Actor:** System (scheduled), Lecturer (manual)
- **Description:** SmartClass reads the materials the lecturer already put on the Moodle course page and indexes them. Nothing is uploaded twice.
- **Preconditions:** Course exists in SmartClass and Moodle; Moodle service token configured.
- **Postconditions:** Each material has a status; indexed passages are searchable with their source file and page or slide.

**Main Flow:**
1. Triggered on a schedule or when the lecturer taps "Sync materials" (FR-803).
2. System lists the course's files from Moodle and compares them with what is indexed (new, changed, removed) (FR-801).
3. For each new or changed file: download, extract text, split into passages, embed, store with source location (FR-802).
4. Passages of removed files are deleted.
5. System records each material's status: indexed, no text, unsupported or error (FR-804).

**Exception Flows:**
- *Scanned PDF with no text layer:* status "no text"; lecturer sees it in the materials list.
- *Moodle unreachable:* keep the existing knowledge base, record the failure, retry next cycle.

---

## UC-802: Ask the assistant a question

- **Actor:** Student
- **Preconditions:** Student is enrolled in the course; the course has indexed materials.
- **Postconditions:** Question and answer saved in the chat session with citations.

**Main Flow:**
1. Student picks a course and opens or creates a chat session (FR-808).
2. Student types a question.
3. System rewrites follow-up questions into stand-alone queries using the chat history.
4. System retrieves the most relevant passages from that course's knowledge base only (FR-807).
5. LLM answers from the passages. Each claim carries a citation (file + page/slide) (FR-805).
6. App shows the answer. Tapping a citation opens the source at that page (FR-809).

**Alternative Flows:**
- *Not covered by the materials:* the answer comes from general knowledge and is labelled "Not from your course materials" (FR-806, NFR-19).
- *Student has an active graded quiz in this course:* refuse (FR-820, deferred until M6).

**Exception Flows:**
- *LLM error or timeout:* show "The assistant is unavailable, try again"; the question is not lost (NFR-21).
- *Course has no indexed materials:* say so, and still allow general-knowledge answers, labelled.

---

## UC-803: Manage chat sessions

- **Actor:** Student
- **Main Flow:** Student lists, renames or deletes their chat sessions for a course (FR-808). Only the student can see them (NFR-09).

---

## UC-804: Generate a summary or study guide

- **Actor:** Student
- **Main Flow:**
1. Student picks a material (or types a topic) and chooses "Summarise" or "Study guide".
2. System retrieves the relevant passages and generates a structured summary with citations (FR-810).
3. Student can save it into a chat session.

---

## UC-805: Practise with flashcards and practice questions

- **Actor:** Student
- **Main Flow:**
1. Student picks a material or topic and chooses "Flashcards" or "Practice questions" (FR-811).
2. System generates cards or questions with answers and citations. They are not graded and not seen by the lecturer.
3. Student flips cards or answers questions and sees the explanation with the source.

**Alternative Flows:**
- *Student asks for related videos:* system suggests YouTube videos and search keywords for the topic (FR-812, Could Have).

---

## UC-806: View anonymised question trends

- **Actor:** Lecturer
- **Preconditions:** Lecturer teaches the course.
- **Main Flow:**
1. Lecturer opens "What students ask" for the course.
2. System shows the most-asked topics and most-cited materials over a chosen period. Only topics asked by at least 3 distinct students appear, with no names or chat text (FR-813, NFR-09).
3. Lecturer can open the cited material sections to decide what to revisit in class.

---

## Deferred — after Module 6 (quiz) is available

- **UC-807 Weak-area recommendations** (FR-821, FR-822): after a quiz, the system works out each student's weak topics from their wrong answers and recommends material sections (and external resources).
- **UC-808 Explain a wrong answer** (FR-823).
- **UC-809 Class-level most-missed topics for the lecturer** (FR-824).

These need M6 quiz results tagged with topic or source material. The interface will be agreed with the M6 owner when M6 exists.
