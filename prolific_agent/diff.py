from __future__ import annotations

from dataclasses import dataclass

from prolific_agent.estimate import language_from_ext
from prolific_agent.scanner import FileMeta
from prolific_agent.state import Snapshot


@dataclass(frozen=True)
class DiffCounts:
    files_added: int
    files_removed: int
    files_modified: int
    folders_added: int
    folders_removed: int
    folders_modified: int
    assets_added: int
    assets_modified: int
    assets_removed: int


@dataclass(frozen=True)
class DiffAggregates:
    counts: DiffCounts
    language_delta_bytes: dict[str, int]
    unknown_delta_bytes: int
    total_delta_bytes: int


def _is_asset(meta: FileMeta) -> bool:
    if meta.is_dir:
        return False
    return language_from_ext(meta.ext) is None


def compute_diff(old: Snapshot | None, new: Snapshot) -> DiffAggregates:
    old_entries = old.entries if old else {}
    new_entries = new.entries

    old_keys = set(old_entries.keys())
    new_keys = set(new_entries.keys())

    added = new_keys - old_keys
    removed = old_keys - new_keys
    common = old_keys & new_keys

    files_added = files_removed = files_modified = 0
    folders_added = folders_removed = folders_modified = 0
    assets_added = assets_removed = assets_modified = 0

    language_delta_bytes: dict[str, int] = {}
    unknown_delta_bytes = 0
    total_delta_bytes = 0

    for rel in added:
        meta = new_entries[rel]
        if meta.is_dir:
            folders_added += 1
            continue
        files_added += 1
        delta = meta.size_bytes
        total_delta_bytes += delta
        lang = language_from_ext(meta.ext)
        if lang is None:
            assets_added += 1
            unknown_delta_bytes += delta
        else:
            language_delta_bytes[lang] = language_delta_bytes.get(lang, 0) + delta

    for rel in removed:
        meta = old_entries[rel]
        if meta.is_dir:
            folders_removed += 1
            continue
        files_removed += 1
        delta = -meta.size_bytes
        total_delta_bytes += delta
        lang = language_from_ext(meta.ext)
        if lang is None:
            assets_removed += 1
            unknown_delta_bytes += delta
        else:
            language_delta_bytes[lang] = language_delta_bytes.get(lang, 0) + delta

    for rel in common:
        old_meta = old_entries[rel]
        new_meta = new_entries[rel]

        # Type flip (file<->dir) treated as remove+add (rare; keep simple)
        if old_meta.is_dir != new_meta.is_dir:
            if old_meta.is_dir:
                folders_removed += 1
                files_added += 1
                delta = new_meta.size_bytes
            else:
                files_removed += 1
                folders_added += 1
                delta = -old_meta.size_bytes
            total_delta_bytes += delta
            continue

        if new_meta.is_dir:
            # Dir "modified" is not meaningful; count only if mtime changed.
            if new_meta.mtime_ns != old_meta.mtime_ns:
                folders_modified += 1
            continue

        # File modified if size or mtime changed.
        if (new_meta.size_bytes != old_meta.size_bytes) or (new_meta.mtime_ns != old_meta.mtime_ns):
            files_modified += 1
            delta = new_meta.size_bytes - old_meta.size_bytes
            total_delta_bytes += delta
            lang = language_from_ext(new_meta.ext)
            if lang is None:
                assets_modified += 1
                unknown_delta_bytes += delta
            else:
                language_delta_bytes[lang] = language_delta_bytes.get(lang, 0) + delta

    counts = DiffCounts(
        files_added=files_added,
        files_removed=files_removed,
        files_modified=files_modified,
        folders_added=folders_added,
        folders_removed=folders_removed,
        folders_modified=folders_modified,
        assets_added=assets_added,
        assets_modified=assets_modified,
        assets_removed=assets_removed,
    )
    return DiffAggregates(
        counts=counts,
        language_delta_bytes=language_delta_bytes,
        unknown_delta_bytes=unknown_delta_bytes,
        total_delta_bytes=total_delta_bytes,
    )


def merge_diff_aggregates(diffs: list[DiffAggregates]) -> DiffAggregates:
    if not diffs:
        zero = DiffCounts(
            files_added=0,
            files_removed=0,
            files_modified=0,
            folders_added=0,
            folders_removed=0,
            folders_modified=0,
            assets_added=0,
            assets_modified=0,
            assets_removed=0,
        )
        return DiffAggregates(counts=zero, language_delta_bytes={}, unknown_delta_bytes=0, total_delta_bytes=0)

    counts = DiffCounts(
        files_added=sum(d.counts.files_added for d in diffs),
        files_removed=sum(d.counts.files_removed for d in diffs),
        files_modified=sum(d.counts.files_modified for d in diffs),
        folders_added=sum(d.counts.folders_added for d in diffs),
        folders_removed=sum(d.counts.folders_removed for d in diffs),
        folders_modified=sum(d.counts.folders_modified for d in diffs),
        assets_added=sum(d.counts.assets_added for d in diffs),
        assets_modified=sum(d.counts.assets_modified for d in diffs),
        assets_removed=sum(d.counts.assets_removed for d in diffs),
    )

    lang_bytes: dict[str, int] = {}
    for d in diffs:
        for lang, delta in d.language_delta_bytes.items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + int(delta)

    return DiffAggregates(
        counts=counts,
        language_delta_bytes=lang_bytes,
        unknown_delta_bytes=sum(d.unknown_delta_bytes for d in diffs),
        total_delta_bytes=sum(d.total_delta_bytes for d in diffs),
    )


