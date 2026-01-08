from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from prolific_agent.scanner import FileMeta
from prolific_agent.scanner import ScanResult


def default_state_path() -> Path:
    return Path.home() / ".prolific" / "state.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class Snapshot:
    schema_version: int
    root: str
    created_at: str
    entries: dict[str, FileMeta]


def snapshot_from_scan(scan: ScanResult) -> Snapshot:
    return Snapshot(
        schema_version=1,
        root=str(scan.root),
        created_at=utc_now_iso(),
        entries=dict(scan.entries),
    )


def load_snapshot(path: Path) -> Snapshot | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, FileMeta] = {}
    for rel, meta in raw.get("entries", {}).items():
        entries[rel] = FileMeta(
            rel_path=str(meta["rel_path"]),
            is_dir=bool(meta["is_dir"]),
            size_bytes=int(meta["size_bytes"]),
            mtime_ns=int(meta["mtime_ns"]),
            ext=str(meta.get("ext", "")),
        )
    return Snapshot(
        schema_version=int(raw.get("schema_version", 1)),
        root=str(raw.get("root", "")),
        created_at=str(raw.get("created_at", "")),
        entries=entries,
    )


def save_snapshot(path: Path, snapshot: Snapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        "schema_version": int(snapshot.schema_version),
        "root": snapshot.root,
        "created_at": snapshot.created_at,
        "entries": {rel: meta.to_json() for rel, meta in snapshot.entries.items()},
    }
    path.write_text(json.dumps(raw, indent=2, sort_keys=True), encoding="utf-8")


