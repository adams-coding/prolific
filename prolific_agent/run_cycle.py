from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from prolific_agent.activity import build_activity_summary
from prolific_agent.config import AgentConfig, default_state_dir
from prolific_agent.diff import DiffAggregates, compute_diff, merge_diff_aggregates
from prolific_agent.git_ops import GitError, commit_and_push_reports
from prolific_agent.repo_bootstrap import ensure_activity_repo_readme
from prolific_agent.privacy import get_or_create_local_salt, project_id_for_watch_path
from prolific_agent.report import build_event_payload, format_event_id, utc_now, write_report_files
from prolific_agent.scanner import scan_folder_metadata_only
from prolific_agent.state import Snapshot, load_snapshot, save_snapshot, snapshot_from_scan
from prolific_agent.viz import append_event


def _state_path_for_watch_dir(state_dir: Path, watch_dir: Path) -> Path:
    # Per-watch state file to avoid mixing diffs across multiple roots.
    key = str(watch_dir.expanduser().resolve()).encode("utf-8")
    h = hashlib.sha1(key).hexdigest()[:16]
    return state_dir / "state" / f"{h}.json"


def _first_run_marker_path(state_dir: Path) -> Path:
    """Path to marker file that indicates first run has completed."""
    return state_dir / "known_projects.json"


def _is_first_run(state_dir: Path) -> bool:
    """Check if this is the first run (marker file doesn't exist)."""
    return not _first_run_marker_path(state_dir).exists()


def _mark_first_run_complete(state_dir: Path) -> None:
    """Create marker file to indicate first run has completed."""
    path = _first_run_marker_path(state_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"first_run_completed": True}, f, indent=2)


def run_once(cfg: AgentConfig, *, state_path: Path | None = None) -> dict:
    """
    Execute one full cycle (scan -> diff -> report -> viz -> save state).
    
    Auto-detects subdirectories and only creates project nodes for folders with activity.

    Returns a small dict for CLI output (does not include file paths from scan).
    """
    state_dir = default_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    diffs: list[DiffAggregates] = []
    total_skipped = 0
    project_ids: list[str] = []
    salt = get_or_create_local_salt()

    # Check if this is the first run
    is_first_run = _is_first_run(state_dir)
    
    first_scan_projects = []
    
    for watch_dir in cfg.scan_paths:
        parent = watch_dir.expanduser().resolve()
        
        # Auto-detect subdirectories
        if parent.is_dir():
            subdirs = [p for p in parent.iterdir() if p.is_dir() and not p.name.startswith('.')]
        else:
            subdirs = [parent]
        
        if not subdirs:
            subdirs = [parent]
        
        for subdir in subdirs:
            proj_id = project_id_for_watch_path(subdir, salt=salt)
            per_watch_state = state_path or _state_path_for_watch_dir(state_dir, subdir)
            per_watch_state.parent.mkdir(parents=True, exist_ok=True)

            prev: Snapshot | None = load_snapshot(per_watch_state)
            scan = scan_folder_metadata_only(subdir, exclude_globs=cfg.exclude_globs)
            total_skipped += int(scan.skipped)
            snap = snapshot_from_scan(scan)

            if prev is not None:
                # Has state file - compute diff and check for changes
                subdir_diff = compute_diff(prev, snap)
                
                has_changes = (
                    subdir_diff.counts.files_added > 0 or
                    subdir_diff.counts.files_modified > 0 or
                    subdir_diff.counts.files_removed > 0 or
                    subdir_diff.total_delta_bytes != 0
                )
                
                if has_changes:
                    diffs.append(subdir_diff)
                    project_ids.append(proj_id)
            else:
                # No state file
                if is_first_run:
                    # First run - just baseline everything
                    first_scan_projects.append(str(subdir))
                else:
                    # Not first run - this is a NEW project, compare to empty
                    empty_snapshot = Snapshot(
                        schema_version=1,
                        root=str(subdir),
                        created_at="",
                        entries={},
                    )
                    subdir_diff = compute_diff(empty_snapshot, snap)
                    has_files = (
                        subdir_diff.counts.files_added > 0 or
                        subdir_diff.total_delta_bytes != 0
                    )
                    if has_files:
                        diffs.append(subdir_diff)
                        project_ids.append(proj_id)
            
            save_snapshot(per_watch_state, snap)
    
    # Mark first run as complete
    if is_first_run:
        _mark_first_run_complete(state_dir)

    # If no changes detected, skip reporting
    if not diffs:
        return {
            "event_id": None,
            "message": "No activity detected - baseline only",
            "projects_with_activity": 0,
            "first_scan_projects": first_scan_projects,
            "state_dir": str(state_dir),
            "watch_folders": [str(p) for p in cfg.scan_paths],
        }

    diff = merge_diff_aggregates(diffs)
    summary = build_activity_summary(diff, bytes_per_loc=cfg.bytes_per_loc)

    ts = utc_now()
    event_id = format_event_id(ts)
    event_payload = build_event_payload(
        event_id=event_id,
        summary=summary,
        project_ids=project_ids,
    )

    # Write artifacts into repo (committed later by git step).
    readme_path, readme_created = ensure_activity_repo_readme(cfg.repo_path)
    json_path, md_path = write_report_files(cfg.repo_path, ts=ts, event_payload=event_payload)
    viz_path = append_event(cfg.repo_path, event_payload)

    git_status: dict[str, object] = {"enabled": True}
    try:
        gr = commit_and_push_reports(
            repo_path=cfg.repo_path,
            branch=cfg.branch,
            remote=cfg.remote,
            push=cfg.push,
            event_id=event_id,
        )
        git_status.update(
            {
                "committed": gr.committed,
                "pushed": gr.pushed,
                "commit_sha": gr.commit_sha,
                "message": gr.message,
            }
        )
    except GitError as e:
        # Non-fatal: keep artifacts + local state and let the next run retry.
        git_status.update({"committed": False, "pushed": False, "error": str(e)})

    return {
        "event_id": event_id,
        "report_json": str(json_path),
        "report_md": str(md_path),
        "viz_events": str(viz_path),
        "git": git_status,
        "activity_repo_readme": str(readme_path),
        "activity_repo_readme_created": bool(readme_created),
        "counts": asdict(summary.counts),
        "net_loc_estimate": summary.net_loc,
        "churn_loc_estimate": summary.churn_loc,
        "total_delta_bytes": summary.total_delta_bytes,
        "skipped_paths": int(total_skipped),
        "state_dir": str(state_dir),
        "watch_folders": [str(p) for p in cfg.scan_paths],
        "projects_with_activity": len(project_ids),
        "first_scan_projects": first_scan_projects,
    }


