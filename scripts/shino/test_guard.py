"""Test guard: fail if tests were removed or skipped since the round started.

Compares the working tree (committed + uncommitted) against SMARTCLASS_BASE
(the commit the loop round started from; defaults to HEAD) and flags:
  - deleted test files under backend/tests/
  - removed `def test_...` functions
  - added skip/xfail markers or pytest.skip() calls
Allowed only when PROGRESS-SHINO.md gained a line starting with "TEST-CHANGE:" since the base,
explaining why (the reviewer then checks the reason).

Usage: python scripts/shino/test_guard.py   (run from anywhere inside the repo)
"""
import os
import re
import subprocess
import sys

TEST_DIR = "backend/tests/"
REMOVED_TEST = re.compile(r"^-\s*(async\s+)?def\s+(test_\w+)")
ADDED_SKIP = re.compile(r"^\+.*(pytest\.mark\.(skip|skipif|xfail)\b|pytest\.(skip|xfail)\(|unittest\.skip)")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def main() -> int:
    root = git("rev-parse", "--show-toplevel").strip()
    os.chdir(root)
    base = os.environ.get("SMARTCLASS_BASE") or "HEAD"

    problems: list[str] = []
    for line in git("diff", "--name-status", base, "--", TEST_DIR).splitlines():
        status, _, path = line.partition("\t")
        if status.startswith("D"):
            problems.append(f"deleted test file: {path}")

    diff = git("diff", "-U0", base, "--", TEST_DIR)
    current = ""
    removed: dict[str, str] = {}
    added_defs: set[str] = set()
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:]
            continue
        m = REMOVED_TEST.match(line)
        if m:
            removed[m.group(2)] = current
        m2 = re.match(r"^\+\s*(async\s+)?def\s+(test_\w+)", line)
        if m2:
            added_defs.add(m2.group(2))
        # conftest.py may hold the marker-based skip logic (live/moodle without config); the reviewer checks it.
        if ADDED_SKIP.match(line) and not current.endswith("conftest.py"):
            problems.append(f"added skip/xfail in {current}: {line[1:].strip()}")
    for name, path in removed.items():
        if name not in added_defs:  # a signature edit removes and re-adds the same name
            problems.append(f"removed test {name} ({path})")

    if not problems:
        return 0
    progress_diff = git("diff", base, "--", "PROGRESS-SHINO.md")
    if re.search(r"^\+.*TEST-CHANGE:", progress_diff, re.MULTILINE):
        print("test guard: test removals/skips found, justified by a TEST-CHANGE note in PROGRESS-SHINO.md:")
        for p in problems:
            print("  -", p)
        return 0
    print("test guard FAILED: tests were removed or skipped without justification.")
    for p in problems:
        print("  -", p)
    print("Restore them, or (only if genuinely required) add a line 'TEST-CHANGE: <test> - <why>' to PROGRESS-SHINO.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
