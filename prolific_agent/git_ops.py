from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from prolific_agent.config import default_state_dir


def _log_path() -> Path:
    return default_state_dir() / "agent.log"


def _append_log(line: str) -> None:
    p = _log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


@dataclass(frozen=True)
class GitResult:
    committed: bool
    pushed: bool
    commit_sha: str | None
    message: str


class GitError(RuntimeError):
    pass


def _run_git(repo_path: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    # Hide console window on Windows
    kwargs = {
        "text": True,
        "capture_output": True,
        "check": False,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    
    return subprocess.run(
        ["git", "-C", str(repo_path), *args],
        **kwargs,
    )


def ensure_git_repo(repo_path: Path) -> None:
    cp = _run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    if cp.returncode != 0 or "true" not in (cp.stdout or "").strip():
        raise GitError(f"Not a git repo: {repo_path}\n{cp.stderr}".rstrip())


def current_branch(repo_path: Path) -> str:
    cp = _run_git(repo_path, ["branch", "--show-current"])
    if cp.returncode != 0:
        raise GitError(f"Failed to read current branch:\n{cp.stderr}".rstrip())
    return (cp.stdout or "").strip()


def checkout_branch(repo_path: Path, branch: str) -> None:
    cp = _run_git(repo_path, ["checkout", branch])
    if cp.returncode != 0:
        raise GitError(f"Failed to checkout branch '{branch}':\n{cp.stderr}".rstrip())


def has_changes(repo_path: Path) -> bool:
    cp = _run_git(repo_path, ["status", "--porcelain"])
    if cp.returncode != 0:
        raise GitError(f"Failed to check status:\n{cp.stderr}".rstrip())
    return bool((cp.stdout or "").strip())


def commit_and_push_reports(
    *,
    repo_path: Path,
    branch: str,
    remote: str,
    push: bool,
    event_id: str,
) -> GitResult:
    """
    Stage and commit only `reports/` and `viz/` (if changed). Optionally push.

    Push failures are non-fatal: we keep the local commit and log the error so
    the next run can retry.
    """
    ensure_git_repo(repo_path)

    cur = current_branch(repo_path)
    if cur and cur != branch:
        checkout_branch(repo_path, branch)

    # Stage only what we own (including README.md created for the activity repo).
    cp_add = _run_git(repo_path, ["add", "--", "README.md", "reports", "viz", "docs"])
    if cp_add.returncode != 0:
        raise GitError(f"git add failed:\n{cp_add.stderr}".rstrip())

    if not has_changes(repo_path):
        return GitResult(committed=False, pushed=False, commit_sha=None, message="No changes to commit.")

    msg = f"Prolific activity: {event_id}"
    cp_commit = _run_git(repo_path, ["commit", "-m", msg])
    if cp_commit.returncode != 0:
        raise GitError(f"git commit failed:\n{cp_commit.stderr}".rstrip())

    sha = None
    cp_sha = _run_git(repo_path, ["rev-parse", "HEAD"])
    if cp_sha.returncode == 0:
        sha = (cp_sha.stdout or "").strip() or None

    if not push:
        return GitResult(committed=True, pushed=False, commit_sha=sha, message="Committed (push disabled).")

    cp_push = _run_git(repo_path, ["push", remote, branch])
    if cp_push.returncode != 0:
        _append_log(f"[git_push_failed] event_id={event_id} stderr={cp_push.stderr.strip()}")
        return GitResult(
            committed=True,
            pushed=False,
            commit_sha=sha,
            message="Committed, but push failed (will retry next run).",
        )

    return GitResult(committed=True, pushed=True, commit_sha=sha, message="Committed and pushed.")


