"""S03: one sample test per helper in tests/shino_helpers.py."""
import json
import smtplib
from email.message import EmailMessage

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.core.deps import ensure_teaches_occurrence
from app.models.audit import AuditLog
from app.models.class_ import Enrollment
from app.models.session import AttendanceSession
from app.models.user import User
from app.services.kb import llm
from tests.shino_helpers import EXPO_PUSH_URL, LLMReplay, prompt_sha

# ── shino_class ────────────────────────────────────────────────────────────────


@pytest.mark.db
async def test_shino_class_has_roles_enrolment_and_an_open_session(shino_class):
    c = shino_class
    assert len(c.student_user_ids) >= 4
    async with AsyncSessionLocal() as db:
        enrolled = set((await db.execute(
            select(Enrollment.student_id).where(Enrollment.occurrence_id == c.occurrence_id)
        )).scalars())
        assert enrolled == set(c.student_ids)
        assert c.outsider_student_id not in enrolled

        session = await db.get(AttendanceSession, c.session_id)
        assert session.status == "open" and session.occurrence_id == c.occurrence_id
        assert session.lecturer_id == c.lecturer_id
        # opened by M3's own Start now, so its audit entry exists like for a real class
        started = await db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "SESSION_START_NOW", AuditLog.target_id == str(c.session_id)))
        assert started == 1

        lecturer = await db.get(User, c.lecturer_user_id)
        assert (await ensure_teaches_occurrence(db, lecturer, c.occurrence_id)).id == c.lecturer_id
        other = await db.get(User, c.other_lecturer_user_id)
        with pytest.raises(HTTPException) as denied:
            await ensure_teaches_occurrence(db, other, c.occurrence_id)
        assert denied.value.status_code == 403

    async with c.client(c.lecturer_user_id, "lecturer") as lec, \
            c.client(c.student_user_ids[0], "student") as stu:
        assert (await lec.get("/lecturer/sessions")).status_code == 200
        assert (await stu.get("/lecturer/sessions")).status_code == 403


# ── fake_expo_push ─────────────────────────────────────────────────────────────


async def test_fake_expo_push_records_and_reports_unregistered_tokens(fake_expo_push):
    fake_expo_push.unregistered.add("ExponentPushToken[gone]")
    async with httpx.AsyncClient() as http:
        resp = await http.post(EXPO_PUSH_URL, json=[
            {"to": "ExponentPushToken[ok]", "title": "Hi", "body": "There"},
            {"to": "ExponentPushToken[gone]", "title": "Hi", "body": "There"},
        ])
    tickets = resp.json()["data"]
    assert tickets[0]["status"] == "ok"
    assert tickets[1]["details"]["error"] == "DeviceNotRegistered"
    assert fake_expo_push.tokens == ["ExponentPushToken[ok]", "ExponentPushToken[gone]"]
    assert len(fake_expo_push.batches) == 1

    fake_expo_push.fail_network = True
    async with httpx.AsyncClient() as http:
        with pytest.raises(httpx.ConnectError):
            await http.post(EXPO_PUSH_URL, json={"to": "ExponentPushToken[ok]"})
        # anything else outgoing is blocked, so a test can't reach the real internet by mistake
        with pytest.raises(Exception):
            await http.get("https://example.com/")


# ── fake_smtp ──────────────────────────────────────────────────────────────────


def test_fake_smtp_keeps_messages_fails_on_demand_and_never_keeps_passwords(fake_smtp):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = "smartclass@um.edu.my", "student@siswa.um.edu.my", "Urgent"
    msg.set_content("Class moved")
    with smtplib.SMTP("smtp.example.com", 587) as smtp:
        smtp.starttls()
        smtp.login("mailer", "s3cret-password")
        smtp.send_message(msg)
    sent = fake_smtp.sent[0]
    assert (sent.recipients, sent.subject, sent.used_tls, sent.username) == (
        ["student@siswa.um.edu.my"], "Urgent", True, "mailer")
    assert "s3cret-password" not in repr(fake_smtp)

    fake_smtp.fail_next = 1
    with pytest.raises(smtplib.SMTPServerDisconnected):
        with smtplib.SMTP_SSL("smtp.example.com", 465) as smtp:
            smtp.sendmail("a@um.edu.my", "b@um.edu.my", "Subject: retry\n\nbody")
    with smtplib.SMTP_SSL("smtp.example.com", 465) as smtp:
        smtp.sendmail("a@um.edu.my", "b@um.edu.my", "Subject: retry\n\nbody")
    assert fake_smtp.attempts == 3 and len(fake_smtp.sent) == 2
    assert fake_smtp.sent[1].subject == "retry" and fake_smtp.sent[1].used_tls


# ── shino_llm ──────────────────────────────────────────────────────────────────

MESSAGES = [{"role": "user", "content": "Make one quiz question as JSON"}]


async def test_shino_llm_replays_a_recording_through_chat_json(monkeypatch, tmp_path):
    (tmp_path / "one_question.json").write_text(json.dumps({"name": "one_question", "calls": [
        {"prompt_sha256": prompt_sha(MESSAGES), "raw": '```json\n{"questions": [{"text": "Q1"}]}\n```'},
    ]}), encoding="utf-8")
    replay = LLMReplay(monkeypatch, "replay", tmp_path).use("one_question")
    assert await llm.chat_json(MESSAGES) == {"questions": [{"text": "Q1"}]}
    assert replay.calls == [MESSAGES]
    with pytest.raises(AssertionError, match="recorded only 1"):
        await llm.chat(MESSAGES)


async def test_shino_llm_records_only_a_passing_test(monkeypatch, tmp_path):
    async def provider(messages, max_tokens=None, temperature=0.2):
        return '{"ok": true}'

    monkeypatch.setattr(llm, "chat", provider)   # stands in for the real provider
    failed = LLMReplay(monkeypatch, "record", tmp_path).use("draft")
    await llm.chat(MESSAGES)
    assert failed.finish(passed=False) is None and not (tmp_path / "draft.json").exists()

    monkeypatch.setattr(llm, "chat", provider)
    passed = LLMReplay(monkeypatch, "record", tmp_path).use("draft")
    assert await llm.chat_json(MESSAGES) == {"ok": True}
    path = passed.finish(passed=True)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["calls"] == [{"prompt_sha256": prompt_sha(MESSAGES), "raw": '{"ok": true}'}]


def test_shino_llm_without_a_recording_fails_with_how_to_record(monkeypatch, tmp_path):
    with pytest.raises(pytest.fail.Exception, match="--record-llm"):
        LLMReplay(monkeypatch, "replay", tmp_path).use("missing")


def test_shino_llm_fixture_replays_by_default(shino_llm):
    assert shino_llm.mode == "replay"
