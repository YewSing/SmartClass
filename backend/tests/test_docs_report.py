"""T104: the AP2 report (`docs/report/ap2-report.html`, uploaded as a Google Doc) matches the repo.

The report cites requirement IDs, test names, diagram files and test counts. These tests fail
when the report drifts: an FR missing from the status table, a cited test renamed, a figure
pointing at a missing PNG, or a summary count that no longer adds up.
"""
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "report" / "ap2-report.html"
FR_DOC = ROOT / "docs" / "requirements" / "functional-requirements.md"


def _report() -> str:
    return REPORT.read_text(encoding="utf-8")


def _status_rows() -> dict[str, str]:
    """FR id -> status cell, from the report's FR table rows."""
    rows = re.findall(r"<tr><td>(FR-\d{3})</td><td>.*?</td><td>.*?</td><td>(.*?)</td>", _report())
    ids = [fr for fr, _ in rows]
    assert len(ids) == len(set(ids)), [i for i, n in Counter(ids).items() if n > 1]
    return dict(rows)


def test_every_fr_of_my_modules_has_a_status():
    spec = set(re.findall(r"^\| (FR-[1348]\d{2}) \|", FR_DOC.read_text(encoding="utf-8"), re.M))
    assert spec, "no FRs parsed from the FR doc"
    assert set(_status_rows()) == spec


def test_statuses_use_the_report_words_and_the_summary_adds_up():
    counts = Counter(_status_rows().values())
    assert set(counts) <= {"Done", "Partly", "Not done", "Deferred on M6"}, counts
    m = re.search(r"(\d+) functional requirements in my modules\. (\d+) Done, (\d+) Partly .*?"
                  r"(\d+) Not done .*?(\d+) Deferred on M6", _report())
    assert m, "summary line not found"
    total, done, partly, not_done, deferred = map(int, m.groups())
    assert total == sum(counts.values())
    assert (done, partly, not_done, deferred) == (
        counts["Done"], counts["Partly"], counts["Not done"], counts["Deferred on M6"])


def test_deferred_frs_are_the_m6_ones():
    deferred = {fr for fr, s in _status_rows().items() if s == "Deferred on M6"}
    assert deferred == {"FR-820", "FR-821", "FR-822", "FR-823", "FR-824"}


def test_cited_tests_exist():
    names = set(re.findall(r"\b(test_\w+?)(?:\.py)?\b", _report()))
    sources = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "backend" / "tests").glob("test_*.py"))
    files = {p.stem for p in (ROOT / "backend" / "tests").glob("test_*.py")}
    missing = [n for n in names if n not in files and f"def {n}(" not in sources]
    assert not missing, missing


def test_cited_diagrams_exist():
    figs = re.findall(r"docs/diagrams/([\w-]+\.png)", _report())
    assert len(figs) == 11
    for name in figs:
        assert (ROOT / "docs" / "diagrams" / name).is_file(), name


def test_e2e_counts_match_the_flow_files():
    m = re.search(r"(\d+) flows \(student (\d+), lecturer (\d+)\)", _report())
    assert m, "Maestro count not found"
    student = len(list((ROOT / "mobile" / "student" / "e2e").glob("*.yaml")))
    lecturer = len(list((ROOT / "mobile" / "lecturer" / "e2e").glob("*.yaml")))
    assert tuple(map(int, m.groups())) == (student + lecturer, student, lecturer)
    specs = len(list((ROOT / "mobile" / "lecturer" / "e2e-web").glob("*.spec.js")))
    assert f"{specs} spec files" in _report()


def test_no_embedded_images_or_secrets():
    html = _report()
    assert "<img" not in html  # no face, card or material images in the report source
    for marker in ("MOODLE_TOKEN=", "API_KEY=", "SECRET_KEY", "password:"):
        assert marker not in html
