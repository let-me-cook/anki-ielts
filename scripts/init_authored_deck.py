#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from anki_helpers import stable_int_id, write_yaml

DEFAULT_MODULES = [
    ("overview.yaml", "overview", ["overview"]),
    ("comparisons.yaml", "comparisons", ["comparison"]),
    ("trends.yaml", "trends", ["trend"]),
    ("maps.yaml", "maps", ["map"]),
]


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize an authored Anki deck workspace under editable/authored/."
    )
    parser.add_argument("deck_slug", help="Slug for the authored deck, for example ielts-writing-task-1-core.")
    parser.add_argument("--title", help="Human-readable deck title. Defaults to a titleized version of the slug.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("editable/authored"),
        help="Root directory for authored decks.",
    )
    parser.add_argument(
        "--source-deck",
        action="append",
        dest="source_decks",
        default=[],
        help="Source deck stem to record in the manifest. Can be passed multiple times.",
    )
    parser.add_argument(
        "--default-tag",
        action="append",
        dest="default_tags",
        default=[],
        help="Default tag to apply to every authored card. Can be passed multiple times.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def titleize_slug(value: str) -> str:
    return value.replace("-", " ").replace("_", " ").title()


def build_manifest(deck_slug: str, title: str, source_decks: list[str], default_tags: list[str]) -> dict:
    return {
        "authored_format_version": 1,
        "deck": {
            "slug": deck_slug,
            "title": title,
            "description": f"Curated authored deck for {title}.",
            "deck_id": stable_int_id(f"deck:{deck_slug}"),
        },
        "model": {
            "id": stable_int_id(f"model:{deck_slug}:cloze"),
            "name": f"{title} Cloze",
            "type": "cloze",
            "field_names": ["Text", "Extra"],
        },
        "release": {
            "repo": "let-me-cook/anki-ielts",
            "asset_name_template": f"{deck_slug}-{{version}}.apkg",
            "title_template": f"{title} {{version}}",
        },
        "default_tags": default_tags or ["authored"],
        "paths": {
            "modules_dir": "modules",
            "media_dir": "media",
        },
        "source_decks": [
            {
                "deck_stem": deck_stem,
                "decompiled_dir": f"decompiled/{deck_stem}",
            }
            for deck_stem in source_decks
        ],
    }


def build_module_payload(module_name: str, tags: list[str]) -> dict:
    return {
        "module": module_name,
        "tags": tags,
        "cards": [],
    }


def init_authored_deck(output_dir: Path, manifest: dict) -> Path:
    if output_dir.exists():
        raise FileExistsError(f"Authored deck already exists: {output_dir}")

    modules_dir = output_dir / "modules"
    media_dir = output_dir / "media"
    modules_dir.mkdir(parents=True, exist_ok=False)
    media_dir.mkdir(parents=True, exist_ok=False)

    write_yaml(output_dir / "manifest.yaml", manifest)
    for filename, module_name, tags in DEFAULT_MODULES:
        write_yaml(modules_dir / filename, build_module_payload(module_name, tags))
    return output_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    deck_slug = args.deck_slug.strip()
    if not deck_slug:
        raise ValueError("deck_slug must be non-empty")

    title = args.title.strip() if args.title else titleize_slug(deck_slug)
    output_dir = args.output_root / deck_slug
    manifest = build_manifest(deck_slug, title, args.source_decks, args.default_tags)
    created_dir = init_authored_deck(output_dir, manifest)
    print(f"initialized {created_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
