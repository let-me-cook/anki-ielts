#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from anki_helpers import (
    PatchApplyError,
    apkg_member_name,
    apply_unified_diff,
    collect_media_refs,
    current_epoch_millis,
    current_epoch_seconds,
    extract_cloze_ords,
    field_checksum,
    html_to_text,
    load_json,
    load_yaml,
    safe_join,
    serialize_tags,
    write_json,
)


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile editable deck YAML back into an .apkg and stage a local release bundle."
    )
    parser.add_argument("editable_dir", type=Path, help="Editable deck directory produced by simplify_decompiled.py.")
    parser.add_argument("--version", required=True, help="Release version/tag, for example v0.1.0.")
    parser.add_argument("--build-root", type=Path, default=Path("build"), help="Root directory for compiled .apkg output.")
    parser.add_argument(
        "--release-root",
        type=Path,
        default=Path("release"),
        help="Root directory for the local release bundle.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_models_by_id(collection: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    output: Dict[int, Dict[str, Any]] = {}
    for model_id, model in collection["models"].items():
        output[int(model_id)] = model
    return output


def load_note_files(notes_dir: Path) -> List[Dict[str, Any]]:
    notes = []
    for note_path in sorted(notes_dir.glob("*.yaml")):
        note = load_yaml(note_path)
        note["_path"] = note_path
        notes.append(note)
    return notes


def resolve_changes_cards_dir(editable_dir: Path, manifest: Dict[str, Any]) -> Path:
    changes_dir = manifest.get("paths", {}).get("changes_cards_dir", "changes/cards")
    return editable_dir / Path(changes_dir)


def note_patch_path(changes_cards_dir: Path, note_id: int) -> Path:
    return changes_cards_dir / f"{note_id}.patch"


def validate_patch_files(changes_cards_dir: Path, expected_note_ids: set[int]) -> None:
    if not changes_cards_dir.exists():
        return

    unknown = []
    for patch_path in sorted(changes_cards_dir.glob("*.patch")):
        try:
            note_id = int(patch_path.stem)
        except ValueError:
            unknown.append(str(patch_path))
            continue
        if note_id not in expected_note_ids:
            unknown.append(str(patch_path))

    if unknown:
        raise ValueError(f"Unknown patch files found: {unknown}")


def apply_note_text_patch(note_id: int, base_text: str, patch_path: Path) -> str:
    patch_text = patch_path.read_text(encoding="utf-8")
    try:
        return apply_unified_diff(base_text, patch_text)
    except PatchApplyError as error:
        raise ValueError(f"Failed to apply patch for note {note_id}: {error}") from error


def validate_and_transform_notes(
    editable_dir: Path,
    manifest: Dict[str, Any],
    base_collection: Dict[str, Any],
    base_notes: List[Dict[str, Any]],
    base_cards: List[Dict[str, Any]],
    note_files: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    models_by_id = load_models_by_id(base_collection)
    base_notes_by_id = {note["id"]: note for note in base_notes}
    expected_note_ids = set(base_notes_by_id)
    seen_note_ids = set()
    changes_cards_dir = resolve_changes_cards_dir(editable_dir, manifest)
    validate_patch_files(changes_cards_dir, expected_note_ids)

    base_card_ords_by_note = defaultdict(list)
    for card in base_cards:
        base_card_ords_by_note[card["note_id"]].append(card["template_ord"])

    patch_target_field = manifest.get("patches", {}).get("target_field", "Text")
    transformed_notes = []
    for note in note_files:
        note_id = note["id"]
        if note_id in seen_note_ids:
            raise ValueError(f"Duplicate note id in editable source: {note_id}")
        seen_note_ids.add(note_id)

        if note_id not in base_notes_by_id:
            raise ValueError(f"Editable note {note_id} does not exist in the base deck")

        base_note = base_notes_by_id[note_id]
        if note["guid"] != base_note["guid"]:
            raise ValueError(f"Editable note {note_id} changed guid, which is not allowed")
        if note["model_id"] != base_note["model_id"]:
            raise ValueError(f"Editable note {note_id} changed model_id, which is not allowed")

        model = models_by_id[note["model_id"]]
        field_names = [field["name"] for field in model.get("flds", [])]
        fields = dict(note["fields"])
        if set(fields.keys()) != set(field_names):
            raise ValueError(
                f"Editable note {note_id} field set does not match model fields {field_names}"
            )

        base_text = base_note["fields_by_name"].get(patch_target_field, "")
        current_text = fields.get(patch_target_field, "")
        if current_text != base_text:
            raise ValueError(
                f"Editable note {note_id} changed {patch_target_field} directly; use "
                f"{note_patch_path(changes_cards_dir, note_id)} instead"
            )

        patch_path = note_patch_path(changes_cards_dir, note_id)
        if patch_path.exists():
            fields[patch_target_field] = apply_note_text_patch(note_id, base_text, patch_path)

        ordered_fields = [fields[field_name] for field_name in field_names]
        media_refs = collect_media_refs(ordered_fields)
        edited = fields[patch_target_field] != base_text

        if model.get("type") == 1:
            card_ords = extract_cloze_ords(ordered_fields)
        else:
            card_ords = sorted(base_card_ords_by_note.get(note_id, []))

        sort_field_index = int(model.get("sortf", 0))
        sort_field = html_to_text(ordered_fields[sort_field_index]) if ordered_fields else ""
        checksum = field_checksum(sort_field)

        transformed_notes.append(
            {
                "id": note_id,
                "guid": note["guid"],
                "model_id": note["model_id"],
                "tags": note.get("tags", []),
                "ordered_fields": ordered_fields,
                "sort_field": sort_field,
                "checksum": checksum,
                "media_refs": media_refs,
                "card_ords": card_ords,
                "edited": edited,
                "_path": note["_path"],
            }
        )

    if seen_note_ids != expected_note_ids:
        missing = sorted(expected_note_ids - seen_note_ids)
        extra = sorted(seen_note_ids - expected_note_ids)
        raise ValueError(f"Editable notes do not match base notes; missing={missing}, extra={extra}")

    return transformed_notes


def validate_media_files(editable_media_dir: Path, transformed_notes: List[Dict[str, Any]]) -> List[Path]:
    referenced = sorted({ref for note in transformed_notes for ref in note["media_refs"]})

    for relative_ref in referenced:
        media_path = safe_join(editable_media_dir, relative_ref)
        if not media_path.exists():
            raise FileNotFoundError(f"Referenced media file is missing: {media_path}")

    return sorted(path for path in editable_media_dir.rglob("*") if path.is_file())


def delete_rows_for_card_ids(cursor: sqlite3.Cursor, table: str, column: str, card_ids: List[int]) -> None:
    if not card_ids:
        return

    placeholders = ",".join("?" for _ in card_ids)
    cursor.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", card_ids)


def regenerate_cards_for_edited_notes(
    cursor: sqlite3.Cursor,
    transformed_notes: List[Dict[str, Any]],
    base_cards: List[Dict[str, Any]],
) -> None:
    base_cards_by_note = defaultdict(list)
    for card in base_cards:
        base_cards_by_note[card["note_id"]].append(card)

    next_card_id = max(
        cursor.execute("SELECT COALESCE(MAX(id), 0) FROM cards").fetchone()[0] + 1,
        current_epoch_millis(),
    )
    next_due = cursor.execute("SELECT COALESCE(MAX(due), 0) FROM cards").fetchone()[0] + 1
    now_seconds = current_epoch_seconds()

    for note in transformed_notes:
        if not note["edited"]:
            continue

        existing_cards = sorted(base_cards_by_note.get(note["id"], []), key=lambda card: card["template_ord"])
        existing_card_ids = [card["id"] for card in existing_cards]

        delete_rows_for_card_ids(cursor, "revlog", "cid", existing_card_ids)
        delete_rows_for_card_ids(cursor, "graves", "oid", existing_card_ids)
        cursor.execute("DELETE FROM cards WHERE nid = ?", (note["id"],))

        if not note["card_ords"]:
            continue

        deck_id = existing_cards[0]["deck_id"] if existing_cards else 1
        flags = existing_cards[0]["flags"] if existing_cards else 0
        data = existing_cards[0]["data"] if existing_cards else ""

        for card_ord in note["card_ords"]:
            cursor.execute(
                """
                INSERT INTO cards (
                    id, nid, did, ord, mod, usn, type, queue, due, ivl, factor,
                    reps, lapses, left, odue, odid, flags, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    next_card_id,
                    note["id"],
                    deck_id,
                    card_ord,
                    now_seconds,
                    -1,
                    0,
                    0,
                    next_due,
                    0,
                    2500,
                    0,
                    0,
                    1001,
                    0,
                    0,
                    flags,
                    data,
                ),
            )
            next_card_id += 1
            next_due += 1


def update_collection_db(
    db_path: Path,
    transformed_notes: List[Dict[str, Any]],
    base_cards: List[Dict[str, Any]],
) -> None:
    now_seconds = current_epoch_seconds()
    now_millis = current_epoch_millis()

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()

        for note in transformed_notes:
            cursor.execute(
                """
                UPDATE notes
                SET mod = ?, usn = ?, tags = ?, flds = ?, sfld = ?, csum = ?
                WHERE id = ?
                """,
                (
                    now_seconds,
                    -1,
                    serialize_tags(note["tags"]),
                    "\x1f".join(note["ordered_fields"]),
                    note["sort_field"],
                    note["checksum"],
                    note["id"],
                ),
            )

        regenerate_cards_for_edited_notes(cursor, transformed_notes, base_cards)
        cursor.execute(
            """
            UPDATE col
            SET mod = ?, usn = ?, ls = ?
            """,
            (now_millis, -1, 0),
        )
        connection.commit()
    finally:
        connection.close()


def build_apkg(
    editable_dir: Path,
    output_path: Path,
    transformed_notes: List[Dict[str, Any]],
    base_cards: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    editable_media_dir = editable_dir / "media"
    media_files = validate_media_files(editable_media_dir, transformed_notes)

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        db_path = temp_dir / "collection.anki2"
        shutil.copy2(editable_dir / "_base" / "collection.anki2", db_path)
        update_collection_db(db_path, transformed_notes, base_cards)

        media_manifest = {}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_path, arcname="collection.anki2")

            for index, media_file in enumerate(media_files):
                relative_name = media_file.relative_to(editable_media_dir).as_posix()
                media_manifest[apkg_member_name(index)] = relative_name
                archive.write(media_file, arcname=apkg_member_name(index))

            archive.writestr("media", json.dumps(media_manifest, ensure_ascii=False))

    return [
        {
            "zip_member": zip_name,
            "original_name": relative_name,
            "output_path": relative_name,
            "missing_from_archive": False,
        }
        for zip_name, relative_name in media_manifest.items()
    ]


def stage_release_bundle(
    editable_dir: Path,
    manifest: Dict[str, Any],
    version: str,
    compiled_apkg: Path,
    transformed_notes: List[Dict[str, Any]],
    build_root: Path,
    release_root: Path,
) -> Path:
    deck_stem = manifest["deck_stem"]
    release_dir = release_root / deck_stem / version
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)

    release_asset_path = release_dir / compiled_apkg.name
    shutil.copy2(compiled_apkg, release_asset_path)

    release_title = manifest["release"]["title_template"].replace("{version}", version)
    release_notes = "\n".join(
        [
            f"# {release_title}",
            "",
            f"- Source deck: {deck_stem}",
            f"- Version: {version}",
            f"- Notes: {len(transformed_notes)}",
            f"- Build asset: `{release_asset_path.name}`",
            "",
            "This release bundle was generated locally and is ready for manual upload to GitHub Releases.",
        ]
    )
    (release_dir / "release-notes.md").write_text(release_notes + "\n", encoding="utf-8")

    release_payload = {
        "repo": manifest["release"]["repo"],
        "tag": version,
        "title": release_title,
        "body_file": "release-notes.md",
        "assets": [
            release_asset_path.name,
        ],
        "source_editable_dir": str(editable_dir),
        "build_dir": str(build_root / deck_stem / version),
    }
    write_json(release_dir / "release.json", release_payload)
    return release_dir


def build_release_from_editable(
    editable_dir: Path,
    version: str,
    build_root: Path,
    release_root: Path,
) -> Dict[str, Path]:
    manifest = load_yaml(editable_dir / "manifest.yaml")
    if manifest.get("editable_format_version") != 1:
        raise ValueError(
            f"Unsupported editable format version: {manifest.get('editable_format_version')}"
        )
    base_dir = editable_dir / "_base"
    base_collection = load_json(base_dir / "collection.json")
    base_notes = load_json(base_dir / "notes.json")
    base_cards = load_json(base_dir / "cards.json")
    note_files = load_note_files(editable_dir / "notes")

    transformed_notes = validate_and_transform_notes(
        editable_dir,
        manifest,
        base_collection,
        base_notes,
        base_cards,
        note_files,
    )

    deck_stem = manifest["deck_stem"]
    asset_name = manifest["release"]["asset_name_template"].replace("{version}", version)
    build_dir = build_root / deck_stem / version
    compiled_apkg = build_dir / asset_name
    build_apkg(editable_dir, compiled_apkg, transformed_notes, base_cards)
    release_dir = stage_release_bundle(
        editable_dir,
        manifest,
        version,
        compiled_apkg,
        transformed_notes,
        build_root,
        release_root,
    )

    return {
        "compiled_apkg": compiled_apkg,
        "release_dir": release_dir,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    outputs = build_release_from_editable(
        args.editable_dir,
        version=args.version,
        build_root=args.build_root,
        release_root=args.release_root,
    )

    print(f"built {outputs['compiled_apkg']}")
    print(f"release bundle {outputs['release_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
