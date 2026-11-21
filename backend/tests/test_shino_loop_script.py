"""scripts/shino/run-tasks.sh (Shino's plan-shino.md loop) runs the Shino commands and keeps the
same safety rules as Yew Sing's loop: wait through a Claude usage limit, stop on a round with no
commit, refuse main, and never run while another loop holds the shared lock.

Runs the real script in a throwaway git repo with stand-ins for `claude` and `docker`.
Never calls Claude or touches the real repo.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")

# Each round's behaviour comes from rounds/<n>: everything but its last line is what Claude
# prints, and a last line of "commit" makes a commit.
FAKE_CLAUDE = """#!/usr/bin/env bash
if [ "$1" = auth ]; then echo "{\\"loggedIn\\": ${FAKE_LOGGED_IN:-true}}"; exit 0; fi
n=$(( $(cat .fake-round 2>/dev/null || echo 0) + 1 )); echo "$n" > .fake-round
printf '%s\\n' "$*" > ".fake-args-$n"
sed '$d' "rounds/$n" 2>/dev/null
echo "work from round $n" >> tracked.txt
if [ "$(tail -n 1 "rounds/$n" 2>/dev/null)" = commit ]; then
  git add tracked.txt && git commit -q -m "S$n: done"
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
    """Build the throwaway repo; return (start, repo, env)."""
    if BASH is None:
        pytest.fail("bash is needed to test scripts/shino/run-tasks.sh")

    repo = tmp_path / "repo"
    (repo / "scripts" / "shino").mkdir(parents=True)
    (repo / "rounds").mkdir()
    (repo / ".claude").mkdir()
    shutil.copy(REPO_ROOT / "scripts" / "shino" / "run-tasks.sh", repo / "scripts" / "shino" / "run-tasks.sh")
    (repo / "scripts" / "backup-data.sh").write_text("exit 0\n", newline="\n")
    (repo / "scripts" / "check.sh").write_text("exit 0\n", newline="\n")
    (repo / "tracked.txt").write_text("start\n", newline="\n")
    (repo / "plan-shino.md").write_text("# plan\n", newline="\n")
    (repo / "progress-shino.md").write_text("# progress\n\n## Log\n", newline="\n")
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
    for cmd in (["git", "init", "-q", "-b", "work"], ["git", "add", "-A"], ["git", "commit", "-q", "-m", "start"]):
        assert run(cmd, repo, env).returncode == 0

    def start(*rounds, n=1):
        for i, (last_line, commits) in enumerate(rounds, 1):
            body = f"{last_line}\n{'commit' if commits else 'none'}\n"
            (repo / "rounds" / str(i)).write_text(body, encoding="utf-8", newline="\n")
        return run([BASH, "scripts/shino/run-tasks.sh", str(n)], repo, env)

    return start, repo, env


def test_round_runs_shino_next_task_and_commits(loop):
    start, repo, _ = loop
    result = start(("done", True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "committed: S1: done" in result.stdout
    args = (repo / ".fake-args-1").read_text()
    assert "/shino-next-task" in args
    assert "Bash(git push*)" in args  # the session itself may not push
    assert "progress-shino.md" in result.stdout  # the summary points at Shino's log


def test_usage_limit_waits_then_retries_with_resume_note(loop):
    start, repo, _ = loop
    result = start(("You've hit your 5-hour limit · resets 7am", False), ("done", True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "waiting" in result.stdout
    assert "committed: S2: done" in result.stdout
    assert "plan-shino.md already ticks it" in (repo / ".fake-args-2").read_text()


def test_round_with_no_commit_stops(loop):
    start, repo, _ = loop
    result = start(("Something went wrong.", False), ("done", True), n=2)
    assert "no commit this round - stopping" in result.stdout
    assert (repo / ".fake-round").read_text().strip() == "1"


def test_refuses_to_run_on_main(loop):
    start, repo, env = loop
    assert run(["git", "branch", "-m", "main"], repo, env).returncode == 0
    result = start(("done", True))
    assert result.returncode != 0
    assert "Refusing to run on main" in result.stdout
    assert not (repo / ".fake-round").exists()


def test_does_not_start_while_another_loop_holds_the_shared_lock(loop):
    start, repo, _ = loop
    lock = repo / ".claude" / ".loop.lock"
    # A live bash writes its own pid, as Yew Sing's scripts/run-tasks.sh would: the two loops
    # share this lock because they share the test database.
    holder = subprocess.Popen([BASH, "-c", f"echo $$ > '{lock.as_posix()}'; sleep 60"])
    try:
        for _ in range(100):
            if lock.exists() and lock.read_text().strip():
                break
            time.sleep(0.1)
        result = start(("done", True))
    finally:
        holder.kill()
    assert result.returncode != 0
    assert "Another loop is already running" in result.stdout
    assert not (repo / ".fake-round").exists()


def test_stops_before_the_backup_when_claude_is_not_logged_in(loop):
    start, repo, env = loop
    env["FAKE_LOGGED_IN"] = "false"
    result = start(("done", True))
    assert result.returncode != 0
    assert "not logged in" in result.stdout
    assert "Backing up" not in result.stdout
    assert not (repo / ".fake-round").exists()
