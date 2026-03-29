#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Set, Tuple

import yaml

BR_RE = re.compile(r"(?i)<br\s*/?>")
BLOCK_TAG_RE = re.compile(r"(?i)</?(?:div|p|li|ul|ol)\b[^>]*>")
TAG_RE = re.compile(r"<[^>]+>")
SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")
IMG_SRC_RE = re.compile(r'(?i)<img\b[^>]*?\bsrc=["\']([^"\']+)["\']')
GENERIC_SRC_RE = re.compile(r'(?i)\bsrc=["\']([^"\']+)["\']')
CLOZE_RE = re.compile(r"\{\{c(\d+)::")
HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchApplyError(ValueError):
    pass


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=100,
        ),
        encoding="utf-8",
    )


def html_to_text(value: str) -> str:
    if not value:
        return ""
    value = BR_RE.sub("\n", value)
    value = BLOCK_TAG_RE.sub("\n", value)
    value = TAG_RE.sub("", value)
    value = html.unescape(value).replace("\xa0", " ")
    value = re.sub(r"\n{2,}", "\n", value)
    return value.strip()


def sanitize_rel_posix(path_value: str) -> str:
    normalized = PurePosixPath(path_value.replace("\\", "/"))
    parts = [part for part in normalized.parts if part not in {"", ".", ".."}]
    return PurePosixPath(*parts).as_posix() if parts else "unnamed"


def safe_join(root: Path, relative_path: str) -> Path:
    return root.joinpath(*PurePosixPath(sanitize_rel_posix(relative_path)).parts)


def extract_media_refs_from_value(value: str) -> List[str]:
    refs: Set[str] = set()

    for pattern in (SOUND_RE, IMG_SRC_RE, GENERIC_SRC_RE):
        for match in pattern.findall(value or ""):
            raw_match = str(match).strip()
            if "://" in raw_match or raw_match.startswith(("data:", "mailto:")):
                continue
            candidate = sanitize_rel_posix(raw_match)
            refs.add(candidate)

    return sorted(refs)


def collect_media_refs(values: Iterable[str]) -> List[str]:
    refs: Set[str] = set()
    for value in values:
        refs.update(extract_media_refs_from_value(value))
    return sorted(refs)


def serialize_tags(tags: List[str]) -> str:
    cleaned = [tag.strip() for tag in tags if tag.strip()]
    return f" {' '.join(cleaned)} " if cleaned else ""


def field_checksum(value: str) -> int:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def extract_cloze_ords(values: Iterable[str]) -> List[int]:
    ords = {int(match) - 1 for value in values for match in CLOZE_RE.findall(value or "")}
    return sorted(ordinal for ordinal in ords if ordinal >= 0)


def current_epoch_seconds() -> int:
    from time import time

    return int(time())


def current_epoch_millis() -> int:
    from time import time

    return int(time() * 1000)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def apkg_member_name(index: int) -> str:
    return str(index)


def _parse_hunk_header(line: str) -> Tuple[int, int, int, int]:
    match = HUNK_HEADER_RE.match(line)
    if not match:
        raise PatchApplyError(f"Invalid unified diff hunk header: {line.rstrip()}")

    old_start = int(match.group(1))
    old_count = int(match.group(2) or "1")
    new_start = int(match.group(3))
    new_count = int(match.group(4) or "1")
    return old_start, old_count, new_start, new_count


def _source_line_matches_patch_line(source_line: str, patch_text: str, *, is_source_eof: bool) -> bool:
    if source_line == patch_text:
        return True
    return is_source_eof and patch_text.endswith("\n") and source_line == patch_text[:-1]


def _normalize_added_patch_line(
    text: str,
    *,
    source_had_trailing_newline: bool,
    source_index: int,
    source_line_count: int,
    next_patch_starts_new_hunk: bool,
) -> str:
    if (
        not source_had_trailing_newline
        and text.endswith("\n")
        and source_index >= source_line_count
        and next_patch_starts_new_hunk
    ):
        return text[:-1]
    return text


def apply_unified_diff(original_text: str, patch_text: str) -> str:
    if not patch_text.strip():
        return original_text

    patch_lines = patch_text.splitlines(keepends=True)
    source_lines = original_text.splitlines(keepends=True)
    source_had_trailing_newline = original_text.endswith("\n")
    output_lines: List[str] = []
    source_index = 0
    patch_index = 0
    saw_hunk = False

    while patch_index < len(patch_lines) and not patch_lines[patch_index].startswith("@@"):
        patch_index += 1

    while patch_index < len(patch_lines):
        header = patch_lines[patch_index]
        if not header.startswith("@@"):
            raise PatchApplyError(f"Unexpected line outside hunk: {header.rstrip()}")

        saw_hunk = True
        old_start, old_count, _new_start, new_count = _parse_hunk_header(header)
        target_index = max(old_start - 1, 0)
        if target_index < source_index:
            raise PatchApplyError("Unified diff hunks overlap or are out of order")

        output_lines.extend(source_lines[source_index:target_index])
        source_index = target_index
        patch_index += 1

        old_consumed = 0
        new_consumed = 0
        while patch_index < len(patch_lines) and not patch_lines[patch_index].startswith("@@"):
            raw_line = patch_lines[patch_index]
            if raw_line.startswith("\\ No newline at end of file"):
                patch_index += 1
                continue
            if not raw_line or raw_line[0] not in {" ", "+", "-"}:
                raise PatchApplyError(f"Invalid hunk line: {raw_line.rstrip()}")

            marker = raw_line[0]
            text = raw_line[1:]
            next_is_no_newline = (
                patch_index + 1 < len(patch_lines)
                and patch_lines[patch_index + 1].startswith("\\ No newline at end of file")
            )
            next_patch_starts_new_hunk = (
                patch_index + 1 >= len(patch_lines)
                or patch_lines[patch_index + 1].startswith("@@")
            )
            if next_is_no_newline and text.endswith("\n"):
                text = text[:-1]

            if marker == " ":
                source_line = source_lines[source_index] if source_index < len(source_lines) else None
                if source_line is None or not _source_line_matches_patch_line(
                    source_line,
                    text,
                    is_source_eof=source_index == len(source_lines) - 1,
                ):
                    raise PatchApplyError("Unified diff context does not match source text")
                output_lines.append(source_line)
                source_index += 1
                old_consumed += 1
                new_consumed += 1
            elif marker == "-":
                source_line = source_lines[source_index] if source_index < len(source_lines) else None
                if source_line is None or not _source_line_matches_patch_line(
                    source_line,
                    text,
                    is_source_eof=source_index == len(source_lines) - 1,
                ):
                    raise PatchApplyError("Unified diff deletion does not match source text")
                source_index += 1
                old_consumed += 1
            else:
                output_lines.append(
                    _normalize_added_patch_line(
                        text,
                        source_had_trailing_newline=source_had_trailing_newline,
                        source_index=source_index,
                        source_line_count=len(source_lines),
                        next_patch_starts_new_hunk=next_patch_starts_new_hunk,
                    )
                )
                new_consumed += 1

            patch_index += 1
            if next_is_no_newline:
                patch_index += 1

        if old_consumed != old_count:
            raise PatchApplyError(
                f"Unified diff consumed {old_consumed} source lines, expected {old_count}"
            )
        if new_consumed != new_count:
            raise PatchApplyError(
                f"Unified diff produced {new_consumed} lines, expected {new_count}"
            )

    if not saw_hunk:
        raise PatchApplyError("Unified diff did not contain any hunks")

    output_lines.extend(source_lines[source_index:])
    return "".join(output_lines)
