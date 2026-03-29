#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from anki_helpers import collect_media_refs, load_json, write_yaml


DEFAULT_RELEASE_REPO = "let-me-cook/anki-ielts"
PATCH_README = """# Card Text Patches

Create one unified diff patch per note in this directory.

Rules:

- File name: `<note-id>.patch`
- Target field: `fields.Text`
- Base text comes from `editable/notes/<note-id>.yaml`
- Patches are applied only at build time

Example header:

```diff
--- a/text
+++ b/text
@@ -1 +1 @@
-old line
+new line
```
"""


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn decompiled deck JSON into an editable YAML workspace."
    )
    parser.add_argument(
        "decompiled_dirs",
        nargs="+",
        type=Path,
        help="One or more directories produced by decompile_apkg.py.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("editable"),
        help="Root directory for editable YAML output.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def resolve_source_apkg(summary: Dict[str, Any], decompiled_dir: Path) -> Path:
    source_apkg = Path(summary["source_apkg"])
    candidates = [
        source_apkg,
        Path.cwd() / source_apkg,
        decompiled_dir.parent.parent / source_apkg,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"Unable to resolve source apkg for {decompiled_dir}: {source_apkg}")


def extract_base_collection(source_apkg: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source_apkg) as archive:
        with archive.open("collection.anki2") as source, target_path.open("wb") as target:
            shutil.copyfileobj(source, target)


def build_manifest(
    deck_stem: str,
    summary: Dict[str, Any],
    collection: Dict[str, Any],
    source_apkg: Path,
) -> Dict[str, Any]:
    model_entries = []
    for model_id, model in sorted(collection["models"].items(), key=lambda item: int(item[0])):
        model_entries.append(
            {
                "id": int(model_id),
                "name": model.get("name"),
                "type": model.get("type"),
                "sort_field_index": model.get("sortf", 0),
                "field_names": [field.get("name") for field in model.get("flds", [])],
                "template_names": [template.get("name") for template in model.get("tmpls", [])],
            }
        )

    deck_entries = []
    for deck_id, deck in sorted(collection["decks"].items(), key=lambda item: int(item[0])):
        deck_entries.append(
            {
                "id": int(deck_id),
                "name": deck.get("name"),
            }
        )

    return {
        "editable_format_version": 1,
        "deck_stem": deck_stem,
        "source": {
            "decompiled_dir": str(summary["output_dir"]),
            "source_apkg": str(source_apkg),
        },
        "release": {
            "repo": DEFAULT_RELEASE_REPO,
            "asset_name_template": f"{deck_stem}-{{version}}.apkg",
            "title_template": f"{deck_stem} {{version}}",
        },
        "constraints": {
            "content_only": True,
            "allow_add_remove_notes": False,
            "allow_model_changes": False,
            "allow_deck_changes": False,
            "text_patch_overlay": True,
            "allow_card_regeneration_from_text_patches": True,
        },
        "counts": {
            "notes": summary["notes"],
            "cards": summary["cards"],
            "media_files": summary["media_files"],
        },
        "models": model_entries,
        "decks": deck_entries,
        "paths": {
            "notes_dir": "notes",
            "media_dir": "media",
            "base_dir": "_base",
            "changes_cards_dir": "changes/cards",
        },
        "patches": {
            "format": "unified_diff",
            "target_field": "Text",
        },
    }


def simplify_decompiled_dir(decompiled_dir: Path, output_root: Path) -> Path:
    summary = load_json(decompiled_dir / "summary.json")
    collection = load_json(decompiled_dir / "collection.json")
    notes = load_json(decompiled_dir / "notes.json")
    cards = load_json(decompiled_dir / "cards.json")
    media_map = load_json(decompiled_dir / "media-map.json")

    source_apkg = resolve_source_apkg(summary, decompiled_dir)
    deck_stem = decompiled_dir.name
    editable_dir = output_root / deck_stem
    notes_dir = editable_dir / "notes"
    media_dir = editable_dir / "media"
    base_dir = editable_dir / "_base"
    changes_cards_dir = editable_dir / "changes" / "cards"

    notes_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    changes_cards_dir.mkdir(parents=True, exist_ok=True)

    card_ords_by_note = defaultdict(list)
    for card in cards:
        card_ords_by_note[card["note_id"]].append(card["template_ord"])

    manifest = build_manifest(deck_stem, summary, collection, source_apkg)
    write_yaml(editable_dir / "manifest.yaml", manifest)

    for note in notes:
        note_payload = {
            "id": note["id"],
            "guid": note["guid"],
            "model_id": note["model_id"],
            "model_name": note["model_name"],
            "tags": note["tags"],
            "expected_card_ords": sorted(card_ords_by_note.get(note["id"], [])),
            "fields": note["fields_by_name"],
            "plain_fields": note["plain_fields_by_name"],
            "media_refs": collect_media_refs(note["fields_by_name"].values()),
        }
        write_yaml(notes_dir / f"{note['id']}.yaml", note_payload)

    if (decompiled_dir / "media").exists():
        shutil.copytree(decompiled_dir / "media", media_dir, dirs_exist_ok=True)

    shutil.copy2(decompiled_dir / "collection.json", base_dir / "collection.json")
    shutil.copy2(decompiled_dir / "notes.json", base_dir / "notes.json")
    shutil.copy2(decompiled_dir / "cards.json", base_dir / "cards.json")
    shutil.copy2(decompiled_dir / "media-map.json", base_dir / "media-map.json")
    shutil.copy2(decompiled_dir / "summary.json", base_dir / "summary.json")
    extract_base_collection(source_apkg, base_dir / "collection.anki2")
    (changes_cards_dir / "README.md").write_text(PATCH_README, encoding="utf-8")

    return editable_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    for decompiled_dir in args.decompiled_dirs:
        output_dir = simplify_decompiled_dir(decompiled_dir, args.output_root)
        print(f"simplified {decompiled_dir} -> {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
