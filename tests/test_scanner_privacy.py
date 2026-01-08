from __future__ import annotations

import builtins
from pathlib import Path

import pytest

from prolific_agent.scanner import scan_folder_metadata_only


def test_scan_does_not_open_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_bytes(b"print('hi')\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.ts").write_bytes(b"const x = 1;\n")

    original_open = builtins.open

    def guarded_open(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        p = Path(file) if isinstance(file, (str, Path)) else None
        if p is not None:
            try:
                if tmp_path in p.resolve().parents or p.resolve() == tmp_path:
                    raise AssertionError("Scanner must not open any scanned files")
            except Exception:
                # If resolve fails, still fail safe.
                raise AssertionError("Scanner attempted to open an unexpected path")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)

    result = scan_folder_metadata_only(tmp_path)
    assert "a.py" in result.entries
    assert "sub/b.ts" in result.entries
    assert result.entries["a.py"].ext == "py"
    assert result.entries["sub/b.ts"].ext == "ts"


def test_scan_excludes_git_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_bytes(b"[core]\n")
    (tmp_path / "x.py").write_bytes(b"print(1)\n")

    result = scan_folder_metadata_only(tmp_path)
    assert "x.py" in result.entries
    assert not any(rel.startswith(".git/") for rel in result.entries)


