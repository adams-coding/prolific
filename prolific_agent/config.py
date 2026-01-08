from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tomllib


def default_state_dir() -> Path:
    return Path.home() / ".prolific"


def default_config_path() -> Path:
    return default_state_dir() / "config.toml"


DEFAULT_BYTES_PER_LOC: dict[str, int] = {
    # Slightly optimistic defaults (lower bytes/LOC => higher LOC estimate).
    # Users can calibrate these in config.toml per language.
    "Python": 34,
    "TypeScript": 38,
    "JavaScript": 38,
    "Go": 38,
    "Rust": 38,
    "Java": 46,
    "C#": 46,
    "C": 38,
    "C++": 42,
    "HTML": 50,
    "CSS": 50,
    "SQL": 38,
    "Shell": 30,
}


@dataclass(frozen=True)
class AgentConfig:
    scan_paths: list[Path]
    repo_path: Path
    interval_hours: int = 2  # scheduling is external; kept for reference/validation
    branch: str = "main"
    remote: str = "origin"
    push: bool = True
    exclude_globs: list[str] = field(default_factory=list)
    bytes_per_loc: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_BYTES_PER_LOC))
    bubble_metric: str = "net_loc"  # "net_loc" | "churn_loc" | "bytes"

    def validate(self) -> None:
        if not (1 <= int(self.interval_hours) <= 4):
            raise ValueError("interval_hours must be between 1 and 4")
        if not self.scan_paths:
            raise ValueError("scan_paths must include at least one directory")
        for p in self.scan_paths:
            if not p.exists():
                raise ValueError(f"scan_path does not exist: {p}")
            if not p.is_dir():
                raise ValueError(f"scan_path is not a directory: {p}")
        if not self.repo_path.exists():
            raise ValueError(f"repo_path does not exist: {self.repo_path}")
        if not self.repo_path.is_dir():
            raise ValueError(f"repo_path is not a directory: {self.repo_path}")
        if self.bubble_metric not in {"net_loc", "churn_loc", "bytes"}:
            raise ValueError("bubble_metric must be one of: net_loc, churn_loc, bytes")

    def to_toml(self) -> str:
        # Keep serialization intentionally simple and predictable.
        lines: list[str] = []
        lines.append("# Prolific: Git Active — config")
        lines.append("")
        lines.append("[agent]")
        lines.append("scan_paths = [")
        for p in self.scan_paths:
            lines.append(f'  "{p.as_posix()}",')
        lines.append("]")
        lines.append(f'repo_path = "{self.repo_path.as_posix()}"')
        lines.append(f"interval_hours = {int(self.interval_hours)}")
        lines.append(f'branch = "{self.branch}"')
        lines.append(f'remote = "{self.remote}"')
        lines.append(f"push = {str(bool(self.push)).lower()}")
        lines.append(f'bubble_metric = "{self.bubble_metric}"')
        lines.append("")
        lines.append("[agent.excludes]")
        lines.append("globs = [")
        for g in self.exclude_globs:
            lines.append(f'  "{g}",')
        lines.append("]")
        lines.append("")
        lines.append("[agent.bytes_per_loc]")
        for k in sorted(self.bytes_per_loc.keys()):
            lines.append(f'"{k}" = {int(self.bytes_per_loc[k])}')
        lines.append("")
        return "\n".join(lines)


def load_config(path: Path) -> AgentConfig:
    raw = tomllib.loads(path.read_bytes().decode("utf-8"))
    agent = raw.get("agent", {})
    excludes = agent.get("excludes", {})
    bytes_per_loc = agent.get("bytes_per_loc", {})

    # Backward compatibility: support older `scan_path` (single).
    scan_paths_raw = agent.get("scan_paths")
    if scan_paths_raw is None:
        scan_path_single = agent.get("scan_path")
        if scan_path_single is None:
            raise ValueError("Config missing agent.scan_paths (or legacy agent.scan_path)")
        scan_paths = [Path(scan_path_single).expanduser()]
    else:
        scan_paths = [Path(p).expanduser() for p in list(scan_paths_raw)]

    cfg = AgentConfig(
        scan_paths=scan_paths,
        repo_path=Path(agent["repo_path"]).expanduser(),
        interval_hours=int(agent.get("interval_hours", 2)),
        branch=str(agent.get("branch", "main")),
        remote=str(agent.get("remote", "origin")),
        push=bool(agent.get("push", True)),
        bubble_metric=str(agent.get("bubble_metric", "net_loc")),
        exclude_globs=list(excludes.get("globs", [])),
        bytes_per_loc={**DEFAULT_BYTES_PER_LOC, **{str(k): int(v) for k, v in bytes_per_loc.items()}},
    )
    cfg.validate()
    return cfg


def write_default_config(path: Path, *, scan_paths: list[Path], repo_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cfg = AgentConfig(scan_paths=scan_paths, repo_path=repo_path)
    path.write_text(cfg.to_toml(), encoding="utf-8")


