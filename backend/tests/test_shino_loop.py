"""scripts/shino/run-tasks.sh must run PLAN-SHINO.md tasks, picking S02 first and stopping cleanly.

Runs the real shino loop script in a throwaway git repo, with stand-ins for `claude` and
`docker`. Never calls Claude or touches the real repo.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")

# Each round's behaviour comes from the file rounds/<n>: everything but its last
# line is what Claude prints, and a last line of "commit" makes a commit.
FAKE_CLAUDE = """#!/usr/bin/env bash
n=$(( $(cat .fake-round 2>/dev/null || echo 0) + 1 )); echo "$n" > .fake-round
printf '%s\\n' "$*" > ".fake-args-$n"
git status --porcelain --untracked-files=no > ".fake-tree-$n"
sed '$d' "rounds/$n" 2>/dev/null
echo "work from round $n" >> tracked.txt
if [ "$(tail -n 1 "rounds/$n" 2>/dev/null)" = commit ]; then
  git add tracked.txt && git commit -q -m "T$n: done"
fi
exit 0
"""

FAKE_DOCKER = """#!/usr/bin/env bash
echo healthy
"""


def run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120)


@pytest.fixture
def loop(tmp_path):
    """Build the throwaway repo; return a function that runs the shino loop in it."""
    if BASH is None:
        pytest.fail("bash is needed to test scripts/shino/run-tasks.sh")

    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    (repo / "rounds").mkdir()
    (repo / ".claude").mkdir()
    shutil.copy(REPO_ROOT / "scripts" / "shino" / "run-tasks.sh", scripts / "run-tasks.sh")
    (scripts / "backup-data.sh").write_text("exit 0\n", newline="\n")
    (scripts / "check.sh").write_text("exit 0\n", newline="\n")

    # PLAN-SHINO.md with S01 done and S02 as the first runnable task.
    plan = (REPO_ROOT / "PLAN-SHINO.md").read_text(encoding="utf-8")
    plan = plan.replace("- [ ] **S01 [INFRA] Shino's own loop", "- [x] **S01 [INFRA] Shino's own loop", 1)
    (repo / "PLAN-SHINO.md").write_text(plan, encoding="utf-8")
    (repo / "PROGRESS-SHINO.md").write_text("# PROGRESS-SHINO\n", encoding="utf-8")
    (repo / "tracked.txt").write_text("start\n", newline="\n")
    (repo / ".gitignore").write_text(".fake-*\nrounds/\n.claude/\n", newline="\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("claude", FAKE_CLAUDE), ("docker", FAKE_DOCKER)):
        path = bin_dir / name
        path.write_text(body, newline="\n")
        path.chmod(0o755)

    env = {k: v for k, v in os.environ.items() if not k.startswith(("SMARTCLASS_", "GIT_"))}
    env.update(
        PATH=f"{bin_dir}{os.pathsep}{env['PATH']}",
        SMARTCLASS_LIMIT_WAIT_MIN="0",
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    for cmd in (
        ["git", "init", "-b", "work"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "start"],
    ):
        assert run(cmd, repo, env).returncode == 0

    def start(*rounds, n=1):
        for i, (last_line, commits) in enumerate(rounds, 1):
            body = f"{last_line}\n{'commit' if commits else 'none'}\n"
            (repo / "rounds" / str(i)).write_text(body, encoding="utf-8", newline="\n")
        result = run([BASH, "scripts/run-tasks.sh", str(n)], repo, env)
        return repo, result, env

    return start


def test_picks_s02_first_and_stops_cleanly_after_it(loop):
    # Round 1: /next-task picked S02 (first runnable task in PLAN-SHINO.md) and committed.
    # Round 2: nothing left to commit this round, so the loop stops cleanly.
    repo, result, _ = loop(("Picked S02 as the first runnable task (S01 done; deps all [x]).", True), ("", False), n=2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "committed: T1: done" in result.stdout, result.stdout
    assert "no commit this round - stopping" in result.stdout, result.stdout
    assert (repo / ".fake-round").read_text().strip() == "2"
    # Exactly one commit (S02) on top of the start commit.
    log = run(["git", "log", "--oneline"], repo).stdout
    assert log.count("\n") == 2, log


def test_s02_is_the_first_runnable_task():
    plan = (REPO_ROOT / "PLAN-SHINO.md").read_text(encoding="utf-8")

    def get_task(task_id):
        for line in plan.splitlines():
            if f"**{task_id} " in line:
                return line
        pytest.fail(f"{task_id} not found in PLAN-SHINO.md")

    s01_line = get_task("S01")
    s02_line = get_task("S02")

    # Task status appears before the task ID.
    assert "- [ ] **S01 " in s01_line, s01_line
    assert "- [ ] **S02 " in s02_line, s02_line

    # S02 depends only on S01.
    assert "Depends on: S01" in s02_line

