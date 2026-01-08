from __future__ import annotations

from dataclasses import dataclass

from prolific_agent.diff import DiffAggregates, DiffCounts
from prolific_agent.estimate import estimate_loc_from_language_deltas


@dataclass(frozen=True)
class LanguageSummary:
    language: str
    delta_bytes: int
    estimated_loc_delta: int


@dataclass(frozen=True)
class ActivitySummary:
    counts: DiffCounts
    total_delta_bytes: int
    unknown_delta_bytes: int
    net_loc: int
    churn_loc: int
    languages: list[LanguageSummary]


def build_activity_summary(
    diff: DiffAggregates,
    *,
    bytes_per_loc: dict[str, int],
) -> ActivitySummary:
    loc = estimate_loc_from_language_deltas(diff.language_delta_bytes, bytes_per_loc=bytes_per_loc)

    langs: list[LanguageSummary] = []
    for language, delta_bytes in sorted(diff.language_delta_bytes.items(), key=lambda kv: kv[0].lower()):
        bpl = int(bytes_per_loc.get(language) or 0)
        estimated = int(round(delta_bytes / bpl)) if bpl > 0 else 0
        langs.append(
            LanguageSummary(language=language, delta_bytes=int(delta_bytes), estimated_loc_delta=estimated)
        )

    return ActivitySummary(
        counts=diff.counts,
        total_delta_bytes=int(diff.total_delta_bytes),
        unknown_delta_bytes=int(diff.unknown_delta_bytes),
        net_loc=int(loc.net_loc),
        churn_loc=int(loc.churn_loc),
        languages=langs,
    )


