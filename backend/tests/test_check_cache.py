"""scripts/check.sh skips a re-run on code it already passed on, but only inside the task loop.

Runs the real check.sh in a throwaway git repo with stand-ins for python, ruff and npm that
count how often the checks ran. Never runs the real test suite.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")

FAKE_TOOL = """#!/usr/bin/env bash
echo "$(basename "$0") $*" >> "$FAKE_CALLS"
exit "${FAKE_FAIL:-0}"
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
    (root / "backend" / "app").mkdir(parents=True)
    (root / "backend" / "app" / "code.py").write_text("x = 1\n", newline="\n")
    for app in ("student", "lecturer"):
        (root / "mobile" / app).mkdir(parents=True)
    (root / "plan-shino.md").write_text("# plan\n", newline="\n")
    (root / ".gitignore").write_text(".claude/\n", newline="\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("python", "ruff", "npm", "npx"):
        path = bin_dir / name
        path.write_text(FAKE_TOOL, newline="\n")
        path.chmod(0o755)

    env = {k: v for k, v in os.environ.items() if not k.startswith(("SMARTCLASS_", "GIT_"))}
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        FAKE_CALLS=str(tmp_path / "calls.txt"),
        SMARTCLASS_LOOP="1",
        SMARTCLASS_BASE="base-commit",
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    for cmd in (["git", "init", "-q", "-b", "work"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "start"]):
        assert run(cmd, root, env).returncode == 0
    return root, env


def check(root, env):
    return run([BASH, "scripts/check.sh"], root, env)


def calls(env):
    path = Path(env["FAKE_CALLS"])
    return path.read_text().count("ruff check") if path.exists() else 0


def test_second_run_on_the_same_code_is_cached(repo):
    root, env = repo
    assert check(root, env).returncode == 0
    second = check(root, env)
    assert second.returncode == 0
    assert "already passed on this exact code" in second.stdout
    assert calls(env) == 1


def test_plan_and_progress_edits_keep_the_cache(repo):
    root, env = repo
    assert check(root, env).returncode == 0
    (root / "plan-shino.md").write_text("# plan\n- [x] S03\n", newline="\n")
    assert "already passed" in check(root, env).stdout
    assert calls(env) == 1


def test_code_edit_or_new_file_runs_the_checks_again(repo):
    root, env = repo
    assert check(root, env).returncode == 0
    (root / "backend" / "app" / "code.py").write_text("x = 2\n", newline="\n")
    assert "already passed" not in check(root, env).stdout
    (root / "backend" / "app" / "new.py").write_text("y = 1\n", newline="\n")
    assert "already passed" not in check(root, env).stdout
    assert calls(env) == 3


def test_new_round_base_runs_the_checks_again(repo):
    root, env = repo
    assert check(root, env).returncode == 0
    env["SMARTCLASS_BASE"] = "next-round"
    assert "already passed" not in check(root, env).stdout
    assert calls(env) == 2


def test_failed_check_is_not_cached(repo):
    root, env = repo
    env["FAKE_FAIL"] = "1"
    assert check(root, env).returncode != 0
    env["FAKE_FAIL"] = "0"
    assert "already passed" not in check(root, env).stdout


def test_outside_the_loop_it_always_runs(repo):
    root, env = repo
    env.pop("SMARTCLASS_LOOP")
    assert check(root, env).returncode == 0
    assert "already passed" not in check(root, env).stdout
    assert calls(env) == 2
