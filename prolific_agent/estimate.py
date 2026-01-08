from __future__ import annotations

from dataclasses import dataclass


EXT_TO_LANGUAGE: dict[str, str] = {
    # Python
    "py": "Python",
    "pyi": "Python",
    # JS/TS
    "js": "JavaScript",
    "cjs": "JavaScript",
    "mjs": "JavaScript",
    "jsx": "JavaScript",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    # Web
    "html": "HTML",
    "htm": "HTML",
    "css": "CSS",
    "scss": "CSS",
    "sass": "CSS",
    "less": "CSS",
    # Backend / systems
    "go": "Go",
    "rs": "Rust",
    "java": "Java",
    "cs": "C#",
    "c": "C",
    "h": "C",
    "cc": "C++",
    "cpp": "C++",
    "cxx": "C++",
    "hpp": "C++",
    "hxx": "C++",
    # Data / scripts
    "sql": "SQL",
    "sh": "Shell",
    "bash": "Shell",
    "ps1": "Shell",
}


def language_from_ext(ext: str) -> str | None:
    if not ext:
        return None
    return EXT_TO_LANGUAGE.get(ext.lower())


@dataclass(frozen=True)
class LocEstimates:
    net_loc: int
    churn_loc: int


def estimate_loc_from_language_deltas(
    language_delta_bytes: dict[str, int],
    *,
    bytes_per_loc: dict[str, int],
) -> LocEstimates:
    net = 0
    churn = 0
    for lang, delta_bytes in language_delta_bytes.items():
        bpl = int(bytes_per_loc.get(lang) or 0)
        if bpl <= 0:
            continue
        net += int(round(delta_bytes / bpl))
        churn += int(round(abs(delta_bytes) / bpl))
    return LocEstimates(net_loc=net, churn_loc=churn)


