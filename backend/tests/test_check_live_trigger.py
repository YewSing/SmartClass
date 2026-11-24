"""scripts/check.sh runs the live LLM suite when app/services/quiz/ (M6 prompts) changes, the
same once-per-state way as app/services/kb/ (S03, T82).

Runs the real check.sh in a throwaway git repo. The stand-in `python` runs `-c` snippets (the
hash) with the real interpreter and only logs everything else, so the real tests never run.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")

FAKE_PYTHON = """#!/usr/bin/env bash
echo "python $*" >> "$FAKE_CALLS"
if [ "$1" = "-c" ]; then exec "$REAL_PYTHON" "$@"; fi
exit 0
"""
FAKE_TOOL = """#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "$FAKE_CALLS"
exit 0
"""


def run(cmd, cwd, env):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)


@pytest.fixture
def repo(tmp_path):
    if BASH is None:
        pytest.fail("bash is needed to test scripts/check.sh")
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "scripts" / "check.sh", root / "scripts" / "check.sh")
    for d in ("app/services/kb", "app/other"):
        (root / "backend" / d).mkdir(parents=True)
    (root / "backend" / "app" / "services" / "kb" / "llm.py").write_text("x = 1\n", newline="\n")
    (root / "backend" / "app" / "other" / "code.py").write_text("x = 1\n", newline="\n")
    for app in ("student", "lecturer"):
        (root / "mobile" / app).mkdir(parents=True)
    (root / ".gitignore").write_text(".claude/\n", newline="\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("python", FAKE_PYTHON), ("ruff", FAKE_TOOL), ("npm", FAKE_TOOL), ("npx", FAKE_TOOL)):
        path = bin_dir / name
        path.write_text(body, newline="\n")
        path.chmod(0o755)

    env = {k: v for k, v in os.environ.items() if not k.startswith(("SMARTCLASS_", "GIT_"))}
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        FAKE_CALLS=str(tmp_path / "calls.txt"),
        REAL_PYTHON=Path(sys.executable).as_posix(),
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    for cmd in (["git", "init", "-q", "-b", "work"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "start"]):
        assert run(cmd, root, env).returncode == 0
    env["SMARTCLASS_BASE"] = run(["git", "rev-parse", "HEAD"], root, env).stdout.strip()
    return root, env


def check(root, env):
    result = run([BASH, "scripts/check.sh"], root, env)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def live_runs(env):
    path = Path(env["FAKE_CALLS"])
    return path.read_text().count("-m pytest -m live") if path.exists() else 0


def test_unrelated_change_does_not_run_live(repo):
    root, env = repo
    (root / "backend" / "app" / "other" / "code.py").write_text("x = 2\n", newline="\n")
    assert "live LLM tests" not in check(root, env)
    assert live_runs(env) == 0


def test_new_quiz_file_runs_live_once_per_state(repo):
    root, env = repo
    quiz = root / "backend" / "app" / "services" / "quiz"
    quiz.mkdir()
    (quiz / "draft.py").write_text("PROMPT = 'a'\n", newline="\n")   # untracked: still counts
    assert "live LLM tests (kb/quiz changed)" in check(root, env)
    assert live_runs(env) == 1
    check(root, env)                                  # same quiz code: the pass is remembered
    assert live_runs(env) == 1

    run(["git", "add", "-A"], root, env)
    run(["git", "commit", "-q", "-m", "quiz"], root, env)
    (quiz / "draft.py").write_text("PROMPT = 'b'\n", newline="\n")   # committed, then edited
    check(root, env)
    assert live_runs(env) == 2


def test_kb_change_still_runs_live(repo):
    root, env = repo
    (root / "backend" / "app" / "services" / "kb" / "llm.py").write_text("x = 2\n", newline="\n")
    check(root, env)
    assert live_runs(env) == 1


# ── S41: a quiz-only change runs only Shino's M6 live tests ───────────────────

def live_commands(env):
    lines = Path(env["FAKE_CALLS"]).read_text().splitlines()
    return [line for line in lines if "-m pytest -m live" in line]


@pytest.fixture
def live_files(repo):
    """Both suites' live tests and an M6 prompt, committed; only `quiz`/`kb` edits come after."""
    root, env = repo
    live = root / "backend" / "tests" / "live"
    live.mkdir(parents=True)
    for name in ("test_live_qa.py", "test_live_quiz_draft.py", "test_live_quiz_grading.py"):
        (live / name).write_text("", newline="\n")
    quiz = root / "backend" / "app" / "services" / "quiz"
    quiz.mkdir()
    (quiz / "draft.py").write_text("PROMPT = 'a'\n", newline="\n")
    for cmd in (["git", "add", "-A"], ["git", "commit", "-q", "-m", "live tests"]):
        assert run(cmd, root, env).returncode == 0
    env["SMARTCLASS_BASE"] = run(["git", "rev-parse", "HEAD"], root, env).stdout.strip()
    return quiz / "draft.py", root / "backend" / "app" / "services" / "kb" / "llm.py"


def test_quiz_only_change_runs_only_the_m6_live_tests(repo, live_files):
    root, env = repo
    live_files[0].write_text("PROMPT = 'b'\n", newline="\n")
    assert "M6 only" in check(root, env)
    [command] = live_commands(env)
    assert "tests/live/test_live_quiz_draft.py" in command and "tests/live/test_live_quiz_grading.py" in command
    assert "test_live_qa.py" not in command


def test_kb_change_runs_the_whole_live_suite_even_with_a_quiz_change(repo, live_files):
    root, env = repo
    live_files[0].write_text("PROMPT = 'b'\n", newline="\n")
    live_files[1].write_text("x = 2\n", newline="\n")
    assert "whole suite" in check(root, env)
    [command] = live_commands(env)
    assert "tests/live" not in command
    check(root, env)
    assert live_runs(env) == 1


def test_an_m6_pass_does_not_count_as_a_pass_of_the_whole_suite(repo, live_files):
    root, env = repo
    before_kb = env["SMARTCLASS_BASE"]
    live_files[1].write_text("x = 2\n", newline="\n")      # a kb change that arrives as a commit (a merge)
    for cmd in (["git", "add", "-A"], ["git", "commit", "-q", "-m", "kb"]):
        assert run(cmd, root, env).returncode == 0
    env["SMARTCLASS_BASE"] = run(["git", "rev-parse", "HEAD"], root, env).stdout.strip()
    live_files[0].write_text("PROMPT = 'b'\n", newline="\n")
    check(root, env)
    assert live_runs(env) == 1 and "test_live_quiz" in live_commands(env)[0]

    env["SMARTCLASS_BASE"] = before_kb                     # same code, but kb is in the range now
    assert "whole suite" in check(root, env)
    assert live_runs(env) == 2

    env["SMARTCLASS_BASE"] = run(["git", "rev-parse", "HEAD"], root, env).stdout.strip()
    check(root, env)                                       # the whole suite's pass covers M6 too
    assert live_runs(env) == 2
