"""Group parsed units into passages ("chunks") sized for retrieval.

Why chunk at all: search returns whole chunks, and the LLM only sees what search
returns. Too small and a chunk loses its context; too big and it mixes topics
(fuzzier search, more tokens per question). We aim for ~400 tokens.

Rules:
1. Consecutive short units (e.g. sparse slides) are merged until the target size,
   so a chunk can cover "slides 4-6". Merging never crosses a material.
2. A unit longer than the max is split on paragraph/sentence boundaries, with a
   small overlap so a definition cut in half still appears whole in one piece.
3. Overlap is only used inside a split unit: page/slide breaks are natural
   boundaries, and overlapping across them would blur the citation range.
"""
import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.kb.parsers import Unit


@dataclass
class Chunk:
    text: str
    location_type: str
    location_start: int
    location_end: int
    heading: str | None
    token_count: int


def count_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English.

    Exact counts depend on the tokenizer (the embedding model and the LLM use
    different ones); an estimate is enough for sizing chunks.
    """
    return max(1, len(text) // 4)


def chunk_units(
    units: list[Unit],
    target: int | None = None,
    max_tokens: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    target = target or settings.KB_CHUNK_TARGET_TOKENS
    max_tokens = max_tokens or settings.KB_CHUNK_MAX_TOKENS
    overlap = settings.KB_CHUNK_OVERLAP_TOKENS if overlap is None else overlap

    chunks: list[Chunk] = []
    buf: list[Unit] = []
    buf_tokens = 0

    def flush() -> None:
        nonlocal buf, buf_tokens
        if buf:
            text = "\n\n".join(u.text for u in buf)
            chunks.append(Chunk(
                text=text,
                location_type=buf[0].location_type,
                location_start=buf[0].number,
                location_end=buf[-1].number,
                heading=buf[0].heading,
                token_count=count_tokens(text),
            ))
        buf, buf_tokens = [], 0

    for unit in units:
        tokens = count_tokens(unit.text)
        if tokens > max_tokens:
            flush()
            for piece in _split_long(unit.text, target, overlap):
                chunks.append(Chunk(piece, unit.location_type, unit.number, unit.number,
                                    unit.heading, count_tokens(piece)))
            continue
        if buf and buf_tokens + tokens > target:
            flush()
        buf.append(unit)
        buf_tokens += tokens
    flush()
    return chunks


def _split_long(text: str, target: int, overlap: int) -> list[str]:
    """Split one long page into ~target-token pieces on sentence boundaries."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]
    pieces: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for sent in sentences:
        t = count_tokens(sent)
        if cur and cur_tokens + t > target:
            pieces.append(" ".join(cur))
            # carry the last sentences (up to `overlap` tokens) into the next piece
            carry: list[str] = []
            carry_tokens = 0
            for prev in reversed(cur):
                carry_tokens += count_tokens(prev)
                if carry_tokens > overlap:
                    break
                carry.insert(0, prev)
            cur, cur_tokens = carry, sum(count_tokens(s) for s in carry)
        cur.append(sent)
        cur_tokens += t
    if cur:
        pieces.append(" ".join(cur))
    return pieces
