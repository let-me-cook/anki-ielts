#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Optional

import yaml

from anki_helpers import load_json, write_yaml


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract reviewable candidate sentences from decompiled source decks."
    )
    parser.add_argument(
        "decompiled_dirs",
        nargs="+",
        type=Path,
        help="One or more directories produced by decompile_apkg.py.",
    )
    parser.add_argument("--output", type=Path, help="Optional YAML file to write the extracted candidates to.")
    return parser.parse_args(list(argv) if argv is not None else None)


def extract_candidates(decompiled_dir: Path) -> dict:
    summary = load_json(decompiled_dir / "summary.json")
    notes = load_json(decompiled_dir / "notes.json")

    candidates = []
    for note in notes:
        text = (note.get("plain_fields_by_name", {}).get("Text") or "").strip()
        extra = (note.get("plain_fields_by_name", {}).get("Extra") or "").strip()
        if not text:
            continue
        candidates.append(
            {
                "note_id": note["id"],
                "model_name": note.get("model_name"),
                "tags": note.get("tags", []),
                "text": text,
                "extra": extra,
            }
        )

    return {
        "deck_stem": decompiled_dir.name,
        "source_apkg": summary.get("source_apkg"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    payload = {
        "source_decks": [extract_candidates(path) for path in args.decompiled_dirs],
    }

    if args.output:
        write_yaml(args.output, payload)
    else:
        yaml.safe_dump(payload, sys.stdout, sort_keys=False, allow_unicode=True, width=100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
