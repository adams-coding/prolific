from __future__ import annotations

from dataclasses import asdict, dataclass
from fnmatch import fnmatch
from pathlib import Path
import stat
from typing import Iterable


@dataclass(frozen=True)
class FileMeta:
    rel_path: str
    is_dir: bool
    size_bytes: int
    mtime_ns: int
    ext: str

    def to_json(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ScanResult:
    root: Path
    entries: dict[str, FileMeta]  # keyed by rel_path
    skipped: int


def _is_excluded(rel_posix: str, exclude_globs: Iterable[str]) -> bool:
    # `rel_posix` is always posix-style regardless of platform.
    for pat in exclude_globs:
        # Support simple dir patterns like "node_modules/" by translating to "**/node_modules/**"
        if pat.endswith("/"):
            pat = f"**/{pat.rstrip('/')}/**"
        if fnmatch(rel_posix, pat):
            return True
    return False


def scan_folder_metadata_only(
    root: Path,
    *,
    exclude_globs: list[str] | None = None,
    max_depth: int | None = None,
) -> ScanResult:
    """
    Scan `root` using directory walking + stat only.

    Privacy guarantee:
      - This function never opens or reads file contents. It only lists directories
        and calls stat() to get size/mtime/is_dir.
    """
    user_excludes = exclude_globs or []
    root = root.expanduser().resolve()

    entries: dict[str, FileMeta] = {}
    skipped = 0

    # Default excludes (privacy + performance)
    default_excludes = [
        "**/.git/**",
        "**/.hg/**",
        "**/.svn/**",
        "**/.idea/**",
        "**/.vscode/**",
        "**/__pycache__/**",
        "**/.venv/**",
        "**/venv/**",
        "**/node_modules/**",
        "**/dist/**",
        "**/build/**",
    ]
    excludes = default_excludes + user_excludes

    def walk(dir_path: Path, depth: int) -> None:
        nonlocal skipped
        if max_depth is not None and depth > max_depth:
            return

        try:
            it = dir_path.iterdir()
        except (FileNotFoundError, PermissionError):
            skipped += 1
            return

        for child in it:
            try:
                rel = child.relative_to(root).as_posix()
            except ValueError:
                # Shouldn't happen given our traversal, but avoid leaking absolute paths.
                skipped += 1
                continue

            if _is_excluded(rel, excludes):
                continue

            try:
                st = child.stat(follow_symlinks=False)
            except (FileNotFoundError, PermissionError, OSError):
                skipped += 1
                continue

            # Use the stat result to avoid following symlinks.
            is_dir = stat.S_ISDIR(st.st_mode)
            ext = "" if is_dir else child.suffix.lower().lstrip(".")
            size = 0 if is_dir else int(st.st_size)
            mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000)))

            meta = FileMeta(
                rel_path=rel,
                is_dir=is_dir,
                size_bytes=size,
                mtime_ns=mtime_ns,
                ext=ext,
            )
            entries[rel] = meta

            if is_dir:
                walk(child, depth + 1)

    walk(root, 0)

    # Apply excludes one final time in case callers provided patterns not caught early.
    filtered_entries = {
        rel: meta for rel, meta in entries.items() if not _is_excluded(rel, excludes)
    }
    return ScanResult(root=root, entries=filtered_entries, skipped=skipped)


