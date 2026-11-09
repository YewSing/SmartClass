"""scripts/run-tasks.sh must wait through a Claude usage limit, not quit.

Runs the real script in a throwaway git repo, with stand-ins for `claude` and
`docker` and a zero-minute wait. Never calls Claude or touches the real repo.
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
    """Build the throwaway repo; return a function that runs the loop in it."""
    if BASH is None:
        pytest.fail("bash is needed to test scripts/run-tasks.sh")

    repo = tmp_path / "repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    (repo / "rounds").mkdir()
    (repo / ".claude").mkdir()
    shutil.copy(REPO_ROOT / "scripts" / "run-tasks.sh", scripts / "run-tasks.sh")
    (scripts / "backup-data.sh").write_text("exit 0\n", newline="\n")
    (scripts / "check.sh").write_text("exit 0\n", newline="\n")
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
        ["git", "init", "-q", "-b", "work"],
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


@pytest.mark.parametrize(
    "message",
    [
        "You've hit your session limit · resets 7am (Asia/Kuala_Lumpur)",  # CLI 2.1.283, 2026-11-09
        "You've hit your 5-hour limit · resets 7am (Asia/Kuala_Lumpur)",  # CLI 2.1.319, 2026-11-09
        "You've hit your weekly limit · resets Mon 7am",
        "You've hit your Opus limit · resets 7am",
    ],
)
def test_limit_message_waits_then_finishes_the_round(loop, message):
    repo, result, _ = loop((message, False), ("done", True))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "waiting" in result.stdout
    assert "committed: T2: done" in result.stdout
    assert (repo / ".fake-round").read_text().strip() == "2"


def test_retry_keeps_the_partial_work_and_is_told_about_it(loop):
    repo, result, env = loop(("You've hit your 5-hour limit · resets 7am", False), ("done", True))
    assert result.returncode == 0, result.stdout + result.stderr

    # Nothing hidden away: the second round found round 1's edit in the tree.
    assert "tracked.txt" in (repo / ".fake-tree-2").read_text()
    assert run(["git", "stash", "list"], repo, env).stdout == ""
    assert "work from round 1" in (repo / "tracked.txt").read_text()

    # Only the retry gets the note, because only it has work to continue.
    assert "unfinished work" not in (repo / ".fake-args-1").read_text()
    assert "unfinished work" in (repo / ".fake-args-2").read_text()


def test_note_is_dropped_once_a_round_commits(loop):
    repo, result, _ = loop(("You've hit your session limit · resets 7am", False), ("done", True), ("done", True), n=2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unfinished work" in (repo / ".fake-args-2").read_text()
    assert "unfinished work" not in (repo / ".fake-args-3").read_text()


def test_round_that_only_mentions_a_limit_does_not_wait(loop):
    """A stuck round discussing a Gemini rate limit must stop, not sleep for 6 hours."""
    repo, result, _ = loop(("Gemini hit a rate limit earlier.\nI could not finish.", False))
    assert "waiting" not in result.stdout
    assert "no commit this round - stopping" in result.stdout
    assert (repo / ".fake-round").read_text().strip() == "1"


def test_round_with_no_commit_and_no_limit_stops(loop):
    repo, result, _ = loop(("Something else went wrong.", False))
    assert "waiting" not in result.stdout
    assert "no commit this round - stopping" in result.stdout
    assert (repo / ".fake-round").read_text().strip() == "1"
