from __future__ import annotations

from prolific_agent.diff import compute_diff
from prolific_agent.scanner import FileMeta
from prolific_agent.state import Snapshot


def test_compute_diff_aggregates_language_deltas() -> None:
    old = Snapshot(
        schema_version=1,
        root="/x",
        created_at="t0",
        entries={
            "a.py": FileMeta(rel_path="a.py", is_dir=False, size_bytes=10, mtime_ns=1, ext="py"),
            "b.png": FileMeta(rel_path="b.png", is_dir=False, size_bytes=100, mtime_ns=1, ext="png"),
        },
    )
    new = Snapshot(
        schema_version=1,
        root="/x",
        created_at="t1",
        entries={
            "a.py": FileMeta(rel_path="a.py", is_dir=False, size_bytes=30, mtime_ns=2, ext="py"),
            "c.ts": FileMeta(rel_path="c.ts", is_dir=False, size_bytes=90, mtime_ns=1, ext="ts"),
        },
    )

    agg = compute_diff(old, new)
    assert agg.counts.files_modified == 1
    assert agg.counts.files_removed == 1
    assert agg.counts.files_added == 1

    # a.py grew by +20 bytes, c.ts added +90 bytes, b.png removed -100 bytes (asset)
    assert agg.language_delta_bytes["Python"] == 20
    assert agg.language_delta_bytes["TypeScript"] == 90
    assert agg.unknown_delta_bytes == -100
    assert agg.total_delta_bytes == 10


