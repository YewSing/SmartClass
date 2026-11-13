# T83: Review and finalise the Q&A evaluation set

**Task (PLAN.md):** `T83 [HUMAN] Review and finalise the Q&A evaluation set (correct answers, remove draft).`

**Why it matters:** the numbers in your FYP report for NFR-18 (answers grounded in course materials), NFR-19 (off-syllabus questions labelled) and NFR-14 (answer time ≤ 15 s) come from `scripts/eval_assistant.py` running this set.
Claude wrote the draft questions and reference answers. They only count as evidence once **you** confirm they match what the course actually teaches.

**File:** `backend/eval/qa_set.jsonl`. It has one question per line: 20 `in_syllabus` and 5 `off_syllabus`, all marked `"draft": true`.

**Course to evaluate against:** **WIF3001 Software Testing**. The questions are about software testing, and WIF3001 has 34 indexed materials in the dev database.

About 45–60 minutes.

---

## Step 1: Check each in-syllabus question is really in the WIF3001 materials

An `in_syllabus` question that the materials don't cover is unfair to the assistant. It will (correctly) answer from general knowledge, and the score will look worse than it is.

The quickest way to check is with the new lecturer feature from Loop B:

1. Log in to the lecturer web app as `lecturer1@example.com` → **Assistant** → **WIF3001** → **Ask my materials**.
2. Paste each question from the table below.
3. **Has citations** → the materials cover it. Keep it as `in_syllabus`.
   **Labelled general knowledge** → the materials don't cover it. Either rewrite the question to match what the materials do say, or remove it.

You can also open the cited slide to see the course's own wording. You'll use that in Step 2.

## Step 2: Check each reference answer matches the course

The reference answer is what the LLM judge compares against. Make it match **how WIF3001 teaches it**, which is mostly the ISTQB CTFL syllabus, not just any textbook.

### Questions I would look at first

| # | Question | Why to check |
|---|---|---|
| 2 | Values for a field 1–100 | The reference uses **3-value** BVA (0, 1, 2, 99, 100, 101). ISTQB CTFL 4.0 teaches **2-value** BVA (0, 1, 100, 101) as the default. Use whichever the lecture slides use. |
| 18 | "Two-point boundary rule" | This phrase may not appear in the slides at all. ISTQB calls it **2-value boundary value analysis**. Reword the question to the course's term, or drop it. |
| 20 | Fault, error, failure | ISTQB uses **error → defect → failure** ("defect" or "bug", not "fault"). Match the slide wording. |
| 6–9 | Statement and branch coverage | These are white-box techniques (CTFL chapter 4). The indexed WIF3001 files look like they cover weeks 1–4, so check they are actually there. |
| 12 | Decision tables | Same question: check chapter 4 material is indexed. |
| 10 | BVA + EP together | Fine in theory. Check the slides link them this way. |

### The full list

Tick when you've checked both the coverage (Step 1) and the reference (Step 2).

| # | Kind | Question | Covered? | Reference OK? |
|---|---|---|---|---|
| 1 | in | What is boundary value analysis and why is it used? | ☐ | ☐ |
| 2 | in | Which values should be tested for a field that accepts integers from 1 to 100? | ☐ | ☐ |
| 3 | in | What is equivalence partitioning? | ☐ | ☐ |
| 4 | in | How does equivalence partitioning reduce the number of test cases? | ☐ | ☐ |
| 5 | in | What are valid and invalid equivalence classes? Give an example. | ☐ | ☐ |
| 6 | in | What is statement coverage? | ☐ | ☐ |
| 7 | in | What is branch coverage and how does it differ from statement coverage? | ☐ | ☐ |
| 8 | in | Why is statement coverage considered a weak criterion? | ☐ | ☐ |
| 9 | in | Does 100% branch coverage imply 100% statement coverage? | ☐ | ☐ |
| 10 | in | How do boundary value analysis and equivalence partitioning work together? | ☐ | ☐ |
| 11 | in | What is the difference between black-box and white-box testing? | ☐ | ☐ |
| 12 | in | What is a decision table and when is it useful? | ☐ | ☐ |
| 13 | in | What is the difference between verification and validation? | ☐ | ☐ |
| 14 | in | What is regression testing? | ☐ | ☐ |
| 15 | in | What is a test case and what should it contain? | ☐ | ☐ |
| 16 | in | What is test coverage and why is it measured? | ☐ | ☐ |
| 17 | in | What is an equivalence class representative? | ☐ | ☐ |
| 18 | in | What does the two-point boundary rule test? | ☐ | ☐ |
| 19 | in | What is static testing? | ☐ | ☐ |
| 20 | in | What is the difference between a fault, an error and a failure? | ☐ | ☐ |
| 21 | off | What is the capital of France? | n/a | ☐ |
| 22 | off | Explain the process of photosynthesis. | n/a | ☐ |
| 23 | off | Who wrote the novel Nineteen Eighty-Four? | n/a | ☐ |
| 24 | off | What is the chemical formula of water? | n/a | ☐ |
| 25 | off | Describe the rules of chess. | n/a | ☐ |

**Off-syllabus questions:** these must be clearly *outside* software testing, which they all are. You could add one that is *near* the course but not in it (for example "What is a neural network?"). That is a harder and more convincing test that the assistant doesn't pretend the materials cover something.

**Nice to have for the report:** a few questions in the style real students ask, such as short, informal, or with a typo ("whats BVA", "difference EP and BVA?"). Mark them `in_syllabus` as usual.

## Step 3: Edit the file

Open `backend/eval/qa_set.jsonl` in VS Code. Each line is one JSON object:

```json
{"kind": "in_syllabus", "question": "...", "reference": "...", "draft": true}
```

- Fix a reference: edit the text inside `"reference": "..."`.
- Remove a question: delete the whole line.
- Add a question: copy a line and change it. Keep it on **one line**.
- **When you are done with a line, delete `, "draft": true`.** When the whole file is done, no line should contain `draft`.

Check that the file is still valid (from the repo root):

```bash
python -c "import json; rows=[json.loads(l) for l in open('backend/eval/qa_set.jsonl', encoding='utf-8') if l.strip()]; print(len(rows), 'questions,', sum('draft' in r for r in rows), 'still draft')"
```

You want `0 still draft`.

## Step 4: Run the evaluation

This uses the real LLM (DeepSeek): about 25 answers plus 25 judge calls, so roughly 50 calls costing a few cents. Make sure Docker postgres is up and the dev DB is current.

```bash
cd backend && python ../scripts/eval_assistant.py --course WIF3001 --out eval/results.json
```

Try `--limit 3` first if you want a quick dry run.

It prints:
- **Citation support:** the share of in-syllabus answers with at least one citation (NFR-18)
- **Off-syllabus label:** the share of off-syllabus answers labelled general knowledge (NFR-19)
- **Latency:** mean and p95 answer time; the target is ≤ 15 s (NFR-14)
- **Correctness:** the average LLM-judged score from 1 to 5 against your reference answers

`eval/results.json` contains text generated from the course materials, so **do not commit it** (copyright rule in CLAUDE.md).

## Step 5: Finish

Tell Claude "T83 done" and paste the printed numbers. Claude will:
- commit the finalised `qa_set.jsonl`
- record the numbers in `PROGRESS.md` for your report
- tick `T83` in `PLAN.md`

If the scores are low, check before blaming the assistant. Usually a reference answer doesn't match the slides (go back to Step 2), or a question isn't in the materials (Step 1).
