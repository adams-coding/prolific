from __future__ import annotations

from prolific_agent.activity import build_activity_summary
from prolific_agent.diff import compute_diff
from prolific_agent.report import build_event_payload
from prolific_agent.scanner import FileMeta
from prolific_agent.state import Snapshot


def test_report_payload_does_not_include_paths_or_filenames() -> None:
    # Simulate a snapshot diff with specific file names. The committed payload must not contain them.
    old = Snapshot(
        schema_version=1,
        root="/secret/project",
        created_at="t0",
        entries={
            "private/a.py": FileMeta(rel_path="private/a.py", is_dir=False, size_bytes=10, mtime_ns=1, ext="py"),
        },
    )
    new = Snapshot(
        schema_version=1,
        root="/secret/project",
        created_at="t1",
        entries={
            "private/a.py": FileMeta(rel_path="private/a.py", is_dir=False, size_bytes=50, mtime_ns=2, ext="py"),
            "private/secrets.txt": FileMeta(
                rel_path="private/secrets.txt", is_dir=False, size_bytes=5, mtime_ns=2, ext="txt"
            ),
        },
    )
    diff = compute_diff(old, new)
    summary = build_activity_summary(diff, bytes_per_loc={"Python": 40})
    payload = build_event_payload(
        event_id="2026-01-07T00:00:00Z",
        summary=summary,
        project_ids=["Project-abc123def0"],
    )

    as_text = str(payload)
    assert "private/a.py" not in as_text
    assert "secrets.txt" not in as_text
    assert "/secret/project" not in as_text


