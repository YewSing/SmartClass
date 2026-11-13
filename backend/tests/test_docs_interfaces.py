"""T98: the docs match the code.

`docs/interfaces.md` promises Shino's modules some Python functions; these tests fail when a
documented function, argument or file is renamed without updating the page. The run
instructions in README.md / CLAUDE.md must point at scripts that exist.
"""
import importlib
import inspect
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INTERFACES = (ROOT / "docs" / "interfaces.md").read_text(encoding="utf-8")


def _params(func) -> list[str]:
    return list(inspect.signature(func).parameters)


def _functions_table() -> list[tuple[str, list[str]]]:
    """Rows of the attendance read interface's Functions table: (name, documented arg names)."""
    section = INTERFACES.split("### Functions", 1)[1].split("###", 1)[0]
    rows = []
    for m in re.finditer(r"^\| `(\w+)` \| `([^`]*)`", section, re.M):
        args = [a.split("=")[0].split(":")[0].strip() for a in m.group(2).split(",")]
        rows.append((m.group(1), args))
    return rows


def test_functions_table_is_parsed():
    names = [name for name, _ in _functions_table()]
    assert names == ["course_records", "student_records", "course_rates", "student_rates",
                     "consecutive_absences", "absence_streak"]


@pytest.mark.parametrize("name,args", _functions_table())
def test_attendance_read_functions_match_doc(name, args):
    mod = importlib.import_module("app.services.attendance_read")
    assert _params(getattr(mod, name)) == args


@pytest.mark.parametrize("module,func,args", [
    ("app.services.kb.retrieval_api", "search", ["course_id", "query", "k"]),
    ("app.services.notify", "emit", ["event", "user_ids", "payload"]),
    ("app.core.deps", "ensure_teaches_occurrence", ["db", "actor", "occurrence_id"]),
    ("app.core.deps", "require_role", ["roles"]),
    ("app.core.deps", "get_current_user", ["credentials", "db"]),
])
def test_documented_signatures_exist(module, func, args):
    fn = getattr(importlib.import_module(module), func)
    assert _params(fn) == args
    assert f"`{func}" in INTERFACES


def test_documented_dataclass_fields_exist():
    from dataclasses import fields

    from app.services.attendance_read import AbsenceStreak, AttendanceRate, AttendanceRow
    from app.services.kb.search import Passage

    for cls in (AttendanceRow, AttendanceRate, AbsenceStreak, Passage):
        names = {f.name for f in fields(cls)}
        heading = cls.__name__
        if cls is Passage:
            block = INTERFACES.split("Each `Passage`", 1)[1].split("\n\n", 2)[1]
        else:
            block = INTERFACES.split(f"`{heading}` —", 1)[1].split("\n\n", 2)[1]
        documented = set()
        for cell in re.findall(r"^\| ([^|]+) \|", block, re.M):
            documented.update(re.findall(r"`(\w+)`", cell))
        assert documented, heading
        assert documented <= names, f"{heading}: documented but missing {documented - names}"


def test_documented_events_are_raised_somewhere():
    app_code = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "backend" / "app").rglob("*.py"))
    lecturer_feed = INTERFACES.split("/ws/sessions/{id}", 1)[1].split("- Students:", 1)[0]
    for event in re.findall(r"`(\w+)`", lecturer_feed):
        assert f'"{event}"' in app_code, event
    assert '"attendance.recorded"' in app_code


def test_documented_files_exist():
    for rel in re.findall(r"`((?:backend/)?app/[\w/]+\.py)`", INTERFACES):
        path = ROOT / (rel if rel.startswith("backend/") else f"backend/{rel}")
        assert path.is_file(), rel


@pytest.mark.parametrize("doc", ["README.md", "CLAUDE.md"])
def test_run_instructions_point_at_real_scripts(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    for script in ["scripts/seed.py", "scripts/device_key.py", "scripts/reset_to_moodle.py"]:
        if script in text:
            assert (ROOT / "backend" / script).is_file(), script
    for script in re.findall(r"bash (scripts/[\w.-]+\.sh)", text):
        assert (ROOT / script).is_file(), script
    for script in re.findall(r"\./scripts/([\w.-]+\.sh)", text):
        assert (ROOT / "backend" / "moodle" / "scripts" / script).is_file(), script
    assert (ROOT / "backend" / "device_client" / "__main__.py").is_file()
    assert "face_worker" not in text   # retired in T46b; device_client is the only camera path
