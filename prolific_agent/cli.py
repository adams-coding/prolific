from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
import sys
import time

from prolific_agent.config import default_config_path, default_state_dir, load_config, write_default_config
from prolific_agent.run_cycle import run_once
from prolific_agent.ui import launch as launch_ui


def _print_err(msg: str) -> None:
    print(msg, file=sys.stderr)


def cmd_init(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser() if args.config else default_config_path()
    if config_path.exists() and not args.force:
        _print_err(f"Config already exists: {config_path} (use --force to overwrite)")
        return 2

    scan_paths_in = args.scan_path if isinstance(args.scan_path, list) else [args.scan_path]
    scan_paths = [Path(p).expanduser() for p in scan_paths_in]
    repo_path = Path(args.repo_path).expanduser()
    for sp in scan_paths:
        if not sp.exists() or not sp.is_dir():
            _print_err(f"--scan-path must be an existing directory: {sp}")
            return 2
    if not repo_path.exists() or not repo_path.is_dir():
        _print_err(f"--repo-path must be an existing directory: {repo_path}")
        return 2
    write_default_config(config_path, scan_paths=scan_paths, repo_path=repo_path)
    print(f"Wrote config: {config_path}")
    return 0


def _last_run_path() -> Path:
    return default_state_dir() / "state" / "last_run.json"


def _read_last_run_ts(path: Path) -> float | None:
    """Return last run timestamp (seconds since epoch) or None."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data.get("last_run_ts", 0)) or None
    except Exception:
        return None


def _read_next_run_ts(path: Path) -> float | None:
    """Return next run timestamp (when random_delay_hours is used we store next_run_ts)."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return float(data.get("next_run_ts", 0)) or None
    except Exception:
        return None


def _write_last_run_ts(path: Path, ts: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_run_ts": ts}, indent=2), encoding="utf-8")


def _write_next_run_ts(path: Path, next_ts: float) -> None:
    """Save next_run_ts so we know when to run again. Also keep last_run_ts for compatibility."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_run_ts": time.time(), "next_run_ts": next_ts}, indent=2),
        encoding="utf-8",
    )


def cmd_run(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser() if args.config else default_config_path()
    if not config_path.exists():
        _print_err(f"Missing config: {config_path} (run `prolific-agent init`)")
        return 2

    cfg = load_config(config_path)

    # When random_delay_hours > 0: next run time was set when we last ran (last_run + interval + one random).
    # Minimum gap = interval_hours; maximum = interval_hours + random_delay_hours. Random is chosen once per run.
    random_delay_hours = getattr(cfg, "random_delay_hours", 0) or 0
    if random_delay_hours > 0:
        state_dir = default_state_dir()
        state_dir.mkdir(parents=True, exist_ok=True)
        last_run_path = _last_run_path()
        next_run_ts = _read_next_run_ts(last_run_path)
        now_ts = time.time()
        if next_run_ts is not None and now_ts < next_run_ts:
            return 0  # skip; not yet time (next run was scheduled when we last ran)

    # Optional random delay so scheduled runs don't always hit at the same time
    if getattr(cfg, "random_delay_minutes", 0) > 0:
        delay_sec = random.uniform(0, cfg.random_delay_minutes * 60)
        time.sleep(delay_sec)

    # Warning about risky watch folders (avoid watching entire drives/huge folders).
    for p in cfg.scan_paths:
        try:
            resolved = p.expanduser().resolve()
        except Exception:
            resolved = p
        # Heuristic: root of filesystem or root of drive (Windows).
        if str(resolved) in {str(resolved.anchor), "/", "\\", str(Path(resolved.anchor))}:
            _print_err(
                "Warning: You are watching a drive/root folder. This can cause high CPU/memory usage. "
                "Prefer a project folder instead."
            )
    result = run_once(cfg)

    # When using random_delay_hours: set next run = now + interval + random(0, random_delay_hours). One draw per run.
    if random_delay_hours > 0:
        gap_hours = cfg.interval_hours + random.uniform(0, random_delay_hours)
        next_run_ts = time.time() + gap_hours * 3600
        _write_next_run_ts(_last_run_path(), next_run_ts)

    print(f"event_id={result['event_id']}")
    print(f"net_loc_estimate={result['net_loc_estimate']}")
    print(f"churn_loc_estimate={result['churn_loc_estimate']}")
    print(f"total_delta_bytes={result['total_delta_bytes']}")
    print(f"skipped_paths={result['skipped_paths']}")
    print(f"report_json={result['report_json']}")
    print(f"report_md={result['report_md']}")
    print(f"viz_events={result['viz_events']}")
    print(f"state_dir={result['state_dir']}")
    if result.get("activity_repo_readme_created"):
        print(f"activity_repo_readme_created={result.get('activity_repo_readme')}")
    git = result.get("git") or {}
    if isinstance(git, dict):
        print(f"git_message={git.get('message')}")
        if git.get("error"):
            print(f"git_error={git.get('error')}")
        if git.get("commit_sha"):
            print(f"git_commit_sha={git.get('commit_sha')}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser() if args.config else default_config_path()
    if not config_path.exists():
        print(f"No config found at: {config_path}")
        return 1
    cfg = load_config(config_path)
    print(f"Config: {config_path}")
    print(f"scan_paths={','.join(str(p) for p in cfg.scan_paths)}")
    print(f"scan_paths={','.join(str(p) for p in cfg.scan_paths)}")
    print(f"repo_path={cfg.repo_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="prolific-agent", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Create a config file")
    p_init.add_argument(
        "--scan-path",
        required=True,
        action="append",
        help="Folder to monitor (metadata only). Repeat to add multiple watch folders.",
    )
    p_init.add_argument("--repo-path", required=True, help="Git repo to write reports/viz into")
    p_init.add_argument("--config", help="Config path (default: ~/.prolific/config.toml)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing config")
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="Run one scan/diff/report cycle")
    p_run.add_argument("--config", help="Config path (default: ~/.prolific/config.toml)")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Show config status")
    p_status.add_argument("--config", help="Config path (default: ~/.prolific/config.toml)")
    p_status.set_defaults(func=cmd_status)

    p_ui = sub.add_parser("ui", help="Launch the simple settings UI")
    p_ui.add_argument("--config", help="Config path (default: ~/.prolific/config.toml)")
    p_ui.set_defaults(
        func=lambda a: (launch_ui(Path(a.config).expanduser() if a.config else None) or 0)
    )

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    rc = int(args.func(args))
    raise SystemExit(rc)


if __name__ == "__main__":
    main()


