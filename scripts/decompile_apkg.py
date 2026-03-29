#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional

BR_RE = re.compile(r"(?i)<br\s*/?>")
BLOCK_TAG_RE = re.compile(r"(?i)</?(?:div|p|li|ul|ol)\b[^>]*>")
TAG_RE = re.compile(r"<[^>]+>")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decompile an Anki .apkg into readable JSON and extracted media."
    )
    parser.add_argument(
        "apkg_paths",
        nargs="+",
        type=Path,
        help="One or more .apkg files to decompile.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("decompiled"),
        help="Root folder for decompiled output.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def parse_json_blob(value: str) -> Any:
    return json.loads(value) if value else {}


def split_fields(value: str) -> List[str]:
    return value.split("\x1f") if value else []


def parse_tags(value: str) -> List[str]:
    return [tag for tag in value.strip().split() if tag]


def html_to_text(value: str) -> str:
    if not value:
        return ""
    value = BR_RE.sub("\n", value)
    value = BLOCK_TAG_RE.sub("\n", value)
    value = TAG_RE.sub("", value)
    value = html.unescape(value).replace("\xa0", " ")
    value = re.sub(r"\n{2,}", "\n", value)
    return value.strip()


def safe_media_path(root: Path, raw_name: str) -> Path:
    sanitized = PurePosixPath(raw_name.replace("\\", "/"))
    parts = [part for part in sanitized.parts if part not in {"", ".", ".."}]
    if not parts:
        parts = ["unnamed"]
    return root.joinpath(*parts)


def build_model_maps(models: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    output: Dict[int, Dict[str, Any]] = {}
    for model_id, model in models.items():
        try:
            numeric_id = int(model_id)
        except (TypeError, ValueError):
            continue

        field_names = [field.get("name", f"field_{index}") for index, field in enumerate(model.get("flds", []))]
        template_names = [
            template.get("name", f"card_{index}") for index, template in enumerate(model.get("tmpls", []))
        ]
        output[numeric_id] = {
            "id": numeric_id,
            "name": model.get("name"),
            "type": model.get("type"),
            "field_names": field_names,
            "template_names": template_names,
            "raw": model,
        }
    return output


def build_deck_maps(decks: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    output: Dict[int, Dict[str, Any]] = {}
    for deck_id, deck in decks.items():
        try:
            numeric_id = int(deck_id)
        except (TypeError, ValueError):
            continue

        output[numeric_id] = {
            "id": numeric_id,
            "name": deck.get("name"),
            "raw": deck,
        }
    return output


def export_collection(apkg_path: Path, output_root: Path) -> Path:
    apkg_stem = apkg_path.stem
    output_dir = output_root / apkg_stem
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        with zipfile.ZipFile(apkg_path) as archive:
            archive.extract("collection.anki2", temp_dir)
            media_map = parse_json_blob(archive.read("media").decode("utf-8"))

            media_dir = output_dir / "media"
            media_dir.mkdir(parents=True, exist_ok=True)
            extracted_media: List[Dict[str, Any]] = []

            for zip_name, original_name in sorted(media_map.items(), key=lambda item: int(item[0])):
                if zip_name not in archive.namelist():
                    extracted_media.append(
                        {
                            "zip_member": zip_name,
                            "original_name": original_name,
                            "output_path": None,
                            "missing_from_archive": True,
                        }
                    )
                    continue

                destination = safe_media_path(media_dir, str(original_name))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(zip_name))
                extracted_media.append(
                    {
                        "zip_member": zip_name,
                        "original_name": original_name,
                        "output_path": str(destination.relative_to(output_dir)),
                        "missing_from_archive": False,
                    }
                )

        connection = sqlite3.connect(temp_dir / "collection.anki2")
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()

        col_row = cursor.execute("SELECT * FROM col").fetchone()
        if col_row is None:
            raise RuntimeError(f"{apkg_path} does not contain an Anki collection row")

        models = parse_json_blob(col_row["models"])
        decks = parse_json_blob(col_row["decks"])
        dconf = parse_json_blob(col_row["dconf"])
        conf = parse_json_blob(col_row["conf"])
        tags = parse_json_blob(col_row["tags"])

        model_map = build_model_maps(models)
        deck_map = build_deck_maps(decks)

        notes_rows = cursor.execute(
            """
            SELECT id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data
            FROM notes
            ORDER BY id
            """
        ).fetchall()
        notes_export: List[Dict[str, Any]] = []
        note_model_lookup: Dict[int, int] = {}

        for row in notes_rows:
            model_info = model_map.get(row["mid"], {})
            field_names = list(model_info.get("field_names", []))
            raw_fields = split_fields(row["flds"])
            if len(field_names) < len(raw_fields):
                field_names.extend(
                    f"field_{index}" for index in range(len(field_names), len(raw_fields))
                )

            fields_by_name = {
                field_names[index]: raw_fields[index] for index in range(len(raw_fields))
            }
            plain_fields_by_name = {
                field_name: html_to_text(field_value)
                for field_name, field_value in fields_by_name.items()
            }

            note_export = {
                "id": row["id"],
                "guid": row["guid"],
                "model_id": row["mid"],
                "model_name": model_info.get("name"),
                "modified": row["mod"],
                "update_sequence_number": row["usn"],
                "tags": parse_tags(row["tags"]),
                "sort_field": row["sfld"],
                "checksum": row["csum"],
                "flags": row["flags"],
                "data": row["data"],
                "raw_fields": raw_fields,
                "fields_by_name": fields_by_name,
                "plain_fields_by_name": plain_fields_by_name,
            }
            notes_export.append(note_export)
            note_model_lookup[row["id"]] = row["mid"]

        cards_rows = cursor.execute(
            """
            SELECT id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses,
                   left, odue, odid, flags, data
            FROM cards
            ORDER BY id
            """
        ).fetchall()
        cards_export: List[Dict[str, Any]] = []

        for row in cards_rows:
            model_id = note_model_lookup.get(row["nid"])
            model_info = model_map.get(model_id, {})
            template_names = list(model_info.get("template_names", []))
            template_name = (
                template_names[row["ord"]]
                if isinstance(row["ord"], int) and 0 <= row["ord"] < len(template_names)
                else None
            )
            deck_info = deck_map.get(row["did"], {})

            cards_export.append(
                {
                    "id": row["id"],
                    "note_id": row["nid"],
                    "deck_id": row["did"],
                    "deck_name": deck_info.get("name"),
                    "template_ord": row["ord"],
                    "template_name": template_name,
                    "modified": row["mod"],
                    "update_sequence_number": row["usn"],
                    "type": row["type"],
                    "queue": row["queue"],
                    "due": row["due"],
                    "interval": row["ivl"],
                    "factor": row["factor"],
                    "repetitions": row["reps"],
                    "lapses": row["lapses"],
                    "left": row["left"],
                    "original_due": row["odue"],
                    "original_deck_id": row["odid"],
                    "flags": row["flags"],
                    "data": row["data"],
                }
            )

        collection_export = {
            "id": col_row["id"],
            "created": col_row["crt"],
            "modified": col_row["mod"],
            "schema_modified": col_row["scm"],
            "version": col_row["ver"],
            "dirty": col_row["dty"],
            "update_sequence_number": col_row["usn"],
            "last_sync": col_row["ls"],
            "config": conf,
            "models": models,
            "decks": decks,
            "deck_config": dconf,
            "tags": tags,
        }

        summary = {
            "source_apkg": str(apkg_path),
            "output_dir": str(output_dir),
            "notes": len(notes_export),
            "cards": len(cards_export),
            "models": len(model_map),
            "decks": len(deck_map),
            "media_files": len(extracted_media),
        }

        (output_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "collection.json").write_text(
            json.dumps(collection_export, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "notes.json").write_text(
            json.dumps(notes_export, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "cards.json").write_text(
            json.dumps(cards_export, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (output_dir / "media-map.json").write_text(
            json.dumps(extracted_media, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return output_dir


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    for apkg_path in args.apkg_paths:
        output_dir = export_collection(apkg_path, args.output_root)
        print(f"decompiled {apkg_path} -> {output_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
