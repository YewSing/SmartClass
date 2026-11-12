# Interfaces between SmartClass modules

Internal interfaces one module exposes for another. Each lists the function, its
signature, what it returns, and which module consumes it. Owners of the consuming
module read the relevant section instead of reaching into another module's tables.

---

## Module 8 → Module 6 — course knowledge base retrieval (FR-814)

**File:** `backend/app/services/kb/retrieval_api.py`

```python
async def search(course_id: int, query: str, k: int = 8) -> list[Passage]
```

Returns the top-k passages for `query` within one course. Module 6 (AI quiz generation)
uses this to draft questions from a course's materials without parsing them itself.

Each `Passage` (from `app.services.kb.search`) carries its source so citations and quiz
question references can point at the material:

| Field | Meaning |
|---|---|
| `material_id`, `title` | the source file |
| `section_name` | the Moodle section (e.g. "Week 3") |
| `location_type` | `page`, `slide` or `section` |
| `location_start`, `location_end` | the page/slide/section number(s) |
| `heading`, `text` | the passage itself |
| `score`, `vector_similarity` | retrieval confidence (RRF score, cosine similarity) |

The search is hybrid (vector + keyword) and is scoped to `course_id`, so Module 6 gets
only the materials of the course it is generating for. The function owns its own
database session; the caller passes no session.
