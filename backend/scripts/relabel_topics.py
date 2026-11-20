"""Relabel chat answers whose topic is a material file name (before 2026-11-13).

Course answers used to be tagged with the first cited file's title (e.g.
"CTFL-Chapter 4-Black-Box.pdf"), which showed up as a "topic" in the lecturer's question
trends. This gives each such answer the same short concept label new answers get.

Usage (from backend/, uses the real LLM, one short call per answer):
    python scripts/relabel_topics.py [--dry-run]
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.ai_chat import ChatMessage, ChatSession  # noqa: E402
from app.services.kb.assistant import _existing_topics, _label_topic  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print the new labels, change nothing")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        answers = (await db.execute(
            select(ChatMessage, ChatSession.course_id)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(ChatMessage.role == "assistant", ChatMessage.topic.is_not(None))
            .order_by(ChatMessage.id)
        )).all()
        changed = 0
        for msg, course_id in answers:
            titles = {c.get("title") for c in (msg.citations or [])}
            if msg.topic not in titles:
                continue
            question = (await db.execute(
                select(ChatMessage).where(ChatMessage.session_id == msg.session_id,
                                          ChatMessage.role == "user", ChatMessage.id < msg.id)
                .order_by(ChatMessage.id.desc()).limit(1)
            )).scalar_one_or_none()
            if question is None:
                continue
            existing = [t for t in await _existing_topics(db, course_id) if t not in titles]
            label = await _label_topic(question.retrieval_query or question.content, existing)
            print(f"{msg.id}: {msg.topic!r} -> {label!r}")
            if label and not args.dry_run:
                msg.topic = label
                await db.flush()   # so the next answer can reuse this label
                changed += 1
        if not args.dry_run:
            await db.commit()
        print(f"{changed} answer(s) relabelled")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
