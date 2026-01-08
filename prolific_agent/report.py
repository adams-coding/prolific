from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from prolific_agent.activity import ActivitySummary


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def format_event_id(ts: datetime) -> str:
    # Example: 2026-01-07T19:22:00Z
    return ts.isoformat().replace("+00:00", "Z")


def report_paths(repo_path: Path, ts: datetime) -> tuple[Path, Path]:
    day = ts.date().isoformat()
    hhmmss = ts.strftime("%H%M%S")
    base = repo_path / "reports" / day
    return base / f"{hhmmss}.json", base / f"{hhmmss}.md"


def build_event_payload(
    *,
    event_id: str,
    summary: ActivitySummary,
    project_ids: list[str] | None = None,
) -> dict:
    # IMPORTANT: This payload is designed to be committed to git.
    # It must not include file names, file paths, or file content.
    return {
        "schema_version": 1,
        "event_id": event_id,
        # Important: these are anonymized project IDs (not folder names/paths).
        "watch_folders": list(project_ids or ["Project-unknown"]),
        "counts": asdict(summary.counts),
        "total_delta_bytes": summary.total_delta_bytes,
        "unknown_delta_bytes": summary.unknown_delta_bytes,
        "net_loc_estimate": summary.net_loc,
        "churn_loc_estimate": summary.churn_loc,
        "languages": [asdict(l) for l in summary.languages],
    }


def build_markdown_report(event: dict) -> str:
    counts = event["counts"]
    lines: list[str] = []
    lines.append(f"## Prolific: Git Active — {event['event_id']}")
    lines.append("")
    lines.append("### Summary")
    lines.append(f"- Watch folders: {', '.join(event.get('watch_folders', []))}")
    lines.append(f"- Estimated net LOC: {event['net_loc_estimate']}")
    lines.append(f"- Estimated churn LOC: {event['churn_loc_estimate']}")
    lines.append(f"- Total delta bytes: {event['total_delta_bytes']}")
    lines.append("")
    lines.append("### Counts")
    lines.append(
        "- Files: "
        f"+{counts['files_added']} "
        f"~{counts['files_modified']} "
        f"-{counts['files_removed']}"
    )
    lines.append(
        "- Folders: "
        f"+{counts['folders_added']} "
        f"~{counts['folders_modified']} "
        f"-{counts['folders_removed']}"
    )
    lines.append(
        "- Assets (non-code): "
        f"+{counts['assets_added']} "
        f"~{counts['assets_modified']} "
        f"-{counts['assets_removed']}"
    )
    lines.append("")

    lines.append("### Languages")
    if not event["languages"]:
        lines.append("- (none detected)")
    else:
        for lang in event["languages"]:
            lines.append(
                f"- {lang['language']}: delta_bytes={lang['delta_bytes']}, "
                f"estimated_loc_delta={lang['estimated_loc_delta']}"
            )
    lines.append("")
    lines.append("Privacy: generated from file metadata only (size/mtime/extensions); no file contents read.")
    lines.append("")
    return "\n".join(lines)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, payload: dict) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def write_report_files(repo_path: Path, *, ts: datetime, event_payload: dict) -> tuple[Path, Path]:
    json_path, md_path = report_paths(repo_path, ts)
    _atomic_write_json(json_path, event_payload)
    _atomic_write_text(md_path, build_markdown_report(event_payload))
    return json_path, md_path


