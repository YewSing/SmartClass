# Checking Loop B (Module 8: T100, T101, T91, T90, T102, T92)

Loop B was built by OpenCode on 2026-11-13 and merged into `fyp2-loop` (commit `3d52178`).
The automated tests and E2E flows passed. This guide is the hands-on check that it makes sense to a real user.

About 20 minutes. Tick each box as you go.

## Before you start

- [ ] Docker postgres is up, the backend runs on `:8000`, and the lecturer web app and the student Expo app are running.
      After the merge, refresh the lecturer web page (Ctrl+Shift+R) and reload the student app (shake → Reload).
- [ ] The dev database is on the newest migration. `cd backend && alembic current` should print `f3a4b5c6d7e8 (head)`.

Accounts (passwords are the ones you set in the local Moodle):

| Who | Login | Why this one |
|---|---|---|
| Lecturer | `lecturer1@example.com` | Teaches WIF3001 Software Testing (34 indexed materials) and WIF3004 |
| Student | `student1@example.com` | Enrolled in WIF3001 and WIF3004 |

Use **WIF3001** for most checks. Its materials are software testing notes, so questions like "boundary value analysis" have real answers.

---

## 1. Lecturer: AI Assistant tab (T91)

Lecturer web app → bottom tab **Assistant** (sparkles icon).

- [ ] The course list shows only **WIF3001** and **WIF3004**, the courses lecturer1 teaches. WIA2005 must **not** appear.
- [ ] Open WIF3001. The **Materials** section lists the files with a status (indexed / failed / no text).
- [ ] Press **Sync now**. It finishes without an error, and the list refreshes. Nothing new should appear unless you changed Moodle.
- [ ] **What students ask** shows three lists: *Most asked topics*, *Most cited materials*, *Topics the materials don't cover*.
      These lists are probably empty or short. That is correct: a topic only appears once **3 different students** have asked about it (NFR-09 privacy rule).

> **Optional, to see real trends:** log in as 3 different WIF3001 students in the student app and ask each one
> "What is boundary value analysis?". Then refresh the lecturer's Assistant tab. *boundary value analysis* should appear under Most asked topics, with no student names anywhere.

## 2. Lecturer: Ask my materials (T100, T102)

On the WIF3001 assistant screen, tap **Ask my materials**.

- [ ] Ask: `What is boundary value analysis?`
      Expected: an answer with numbered citations [1], [2] pointing to WIF3001 files.
- [ ] Tap a citation. The source file opens (T102 `LecturerSource`), at the right page or slide where the format allows.
- [ ] Ask something off-topic: `What is the capital of France?`
      Expected: an answer clearly labelled as **general knowledge**, with **no** citations.
- [ ] Ask a follow-up: `Give me an example of it` (after a testing question).
      Expected: it stays on the same topic.
- [ ] Go back and open the chat again. Your earlier questions are still there.
- [ ] **Privacy check:** your lecturer questions must **not** appear under *What students ask*. Only student chats count.

## 3. Lecturer: Before next class (T101, T102)

On the WIF3001 assistant screen, tap **Before next class**.

- [ ] With few student questions, you see a polite "not enough questions yet" message instead of an invented summary. This is correct behaviour.
- [ ] If you did the optional 3-student step above, you see a short note with a **Revisit** section and possibly a **Not covered by the materials** section.
      It must not contain any student names, question texts or counts.
- [ ] Open it twice in a row. The second time is instant, because the result is cached until the trends change.

## 4. Student: Study tools (T90)

Student app → **Assistant** tab → WIF3001 → **Study tools · summarise, flashcards, practice**.

Type the topic `boundary value analysis`, then try each of the four buttons:

- [ ] **Summary**: short markdown text with citations.
- [ ] **Study guide**: longer, structured text with headings.
- [ ] **Flashcards**: cards with a front and a back. Tapping a card shows its back.
- [ ] **Practice**: multiple-choice questions. Picking an answer shows whether it is right, with an explanation.
- [ ] Try a topic that is not in the materials, such as `quantum entanglement`. It should say the materials don't cover it rather than invent citations.

Known limit (from Loop B's notes): you **type** a topic. There is no material picker yet, because no student-side "list materials" endpoint exists. That is noted as a follow-up and is not a bug.

## 5. YouTube suggestions (T92, optional)

T92 is a *Could Have* feature with **no screen yet**, and it stays **off** until a key is set.

- [ ] Without a key: open `http://localhost:8000/docs`, authorise as student1, and call `POST /student/assistant/youtube` with
      `{"course_id": <WIF3001 id>, "topic": "boundary value analysis"}`. You get `enabled: false`, an empty `videos` list and 3 search keywords.
- [ ] With a key (optional): create a YouTube Data API v3 key in Google Cloud and add `YOUTUBE_API_KEY=...` to `backend/.env` yourself.
      Restart the backend and repeat the call. You get up to 5 videos with titles and links.

## 6. Access checks (quick)

- [ ] As **lecturer2** (teaches WIA2005 only), the Assistant tab shows WIA2005 only, not WIF3001.
- [ ] As **student1**, Study tools for WIA2005 should not be reachable, because student1 isn't enrolled in it.

---

## If something is wrong

Write down the screen, what you did, what you expected and what happened, then tell Claude.
Small issues become `REVIEW:` lines under `## Next` in `PROGRESS.md`. A broken feature means its task box is set back to `[ ]` so the next loop redoes it.
