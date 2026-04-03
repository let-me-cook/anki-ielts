#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from anki_helpers import (
    apkg_member_name,
    collect_media_refs,
    current_epoch_millis,
    current_epoch_seconds,
    extract_cloze_ords,
    field_checksum,
    html_to_text,
    load_yaml,
    merge_tags,
    plain_text_to_html,
    safe_join,
    serialize_tags,
    stable_int_id,
    write_json,
)

SUPPORTED_CARD_TYPES = {"contextual_cloze"}
SCHEMA_SQL = """
CREATE TABLE col (
    id              integer primary key,
    crt             integer not null,
    mod             integer not null,
    scm             integer not null,
    ver             integer not null,
    dty             integer not null,
    usn             integer not null,
    ls              integer not null,
    conf            text not null,
    models          text not null,
    decks           text not null,
    dconf           text not null,
    tags            text not null
);
CREATE TABLE notes (
    id              integer primary key,
    guid            text not null,
    mid             integer not null,
    mod             integer not null,
    usn             integer not null,
    tags            text not null,
    flds            text not null,
    sfld            integer not null,
    csum            integer not null,
    flags           integer not null,
    data            text not null
);
CREATE TABLE cards (
    id              integer primary key,
    nid             integer not null,
    did             integer not null,
    ord             integer not null,
    mod             integer not null,
    usn             integer not null,
    type            integer not null,
    queue           integer not null,
    due             integer not null,
    ivl             integer not null,
    factor          integer not null,
    reps            integer not null,
    lapses          integer not null,
    left            integer not null,
    odue            integer not null,
    odid            integer not null,
    flags           integer not null,
    data            text not null
);
CREATE TABLE revlog (
    id              integer primary key,
    cid             integer not null,
    usn             integer not null,
    ease            integer not null,
    ivl             integer not null,
    lastIvl         integer not null,
    factor          integer not null,
    time            integer not null,
    type            integer not null
);
CREATE TABLE graves (
    usn             integer not null,
    oid             integer not null,
    type            integer not null
);
CREATE INDEX ix_notes_usn on notes (usn);
CREATE INDEX ix_cards_usn on cards (usn);
CREATE INDEX ix_revlog_usn on revlog (usn);
CREATE INDEX ix_cards_nid on cards (nid);
CREATE INDEX ix_cards_sched on cards (did, queue, due);
CREATE INDEX ix_revlog_cid on revlog (cid);
CREATE INDEX ix_notes_csum on notes (csum);
"""


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile an authored module deck into an .apkg and stage a local release bundle."
    )
    parser.add_argument("authored_dir", type=Path, help="Authored deck directory produced by init_authored_deck.py.")
    parser.add_argument("--version", required=True, help="Release version/tag, for example v0.1.0.")
    parser.add_argument("--build-root", type=Path, default=Path("build"), help="Root directory for compiled .apkg output.")
    parser.add_argument(
        "--release-root",
        type=Path,
        default=Path("release"),
        help="Root directory for the local release bundle.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def require_string(value: Any, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value.strip()


def require_string_list(value: Any, context: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{context} must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def load_module_files(modules_dir: Path) -> List[Dict[str, Any]]:
    modules = []
    for module_path in sorted(modules_dir.glob("*.yaml")):
        payload = load_yaml(module_path) or {}
        payload["_path"] = module_path
        modules.append(payload)
    if not modules:
        raise FileNotFoundError(f"No module YAML files found in {modules_dir}")
    return modules


def validate_source_refs(value: Any, context: str) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")

    normalized = []
    for index, item in enumerate(value):
        item_context = f"{context}[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{item_context} must be a mapping")
        normalized.append(
            {
                "deck": require_string(item.get("deck"), f"{item_context}.deck"),
                "note_id": int(item.get("note_id")),
            }
        )
    return normalized


def render_text_field(prompt: str, sentence: str) -> str:
    parts = []
    if prompt:
        parts.append(f'<div class="prompt">{plain_text_to_html(prompt)}</div>')
    parts.append(f'<div class="sentence">{sentence}</div>')
    return "".join(parts)


def render_extra_field(extra: str) -> str:
    if not extra:
        return ""
    return f'<div class="extra">{plain_text_to_html(extra)}</div>'


def build_guid(deck_slug: str, authored_id: str) -> str:
    return hashlib.sha1(f"{deck_slug}:{authored_id}".encode("utf-8")).hexdigest()[:12]


def load_authored_cards(authored_dir: Path, manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    modules_dir = authored_dir / Path(manifest.get("paths", {}).get("modules_dir", "modules"))
    module_files = load_module_files(modules_dir)
    default_tags = require_string_list(manifest.get("default_tags"), "manifest.default_tags")
    deck_slug = require_string(manifest.get("deck", {}).get("slug"), "manifest.deck.slug")

    authored_cards: List[Dict[str, Any]] = []
    seen_authored_ids = set()
    seen_note_ids = set()
    seen_card_ids = set()

    for module_payload in module_files:
        module_path = module_payload["_path"]
        module_name = module_payload.get("module") or module_path.stem
        module_name = require_string(module_name, f"{module_path}.module")
        module_tags = require_string_list(module_payload.get("tags"), f"{module_path}.tags")
        raw_cards = module_payload.get("cards", [])
        if not isinstance(raw_cards, list):
            raise ValueError(f"{module_path}.cards must be a list")

        for index, raw_card in enumerate(raw_cards):
            card_context = f"{module_path}.cards[{index}]"
            if not isinstance(raw_card, dict):
                raise ValueError(f"{card_context} must be a mapping")

            authored_id = require_string(raw_card.get("id"), f"{card_context}.id")
            if authored_id in seen_authored_ids:
                raise ValueError(f"Duplicate authored card id: {authored_id}")
            seen_authored_ids.add(authored_id)

            card_type = raw_card.get("type", "contextual_cloze")
            card_type = require_string(card_type, f"{card_context}.type")
            if card_type not in SUPPORTED_CARD_TYPES:
                raise ValueError(f"Unsupported card type for {authored_id}: {card_type}")

            prompt = require_string(raw_card.get("prompt"), f"{card_context}.prompt")
            sentence = require_string(raw_card.get("sentence"), f"{card_context}.sentence")
            extra = raw_card.get("extra", "")
            if extra is None:
                extra = ""
            if not isinstance(extra, str):
                raise ValueError(f"{card_context}.extra must be a string")

            card_tags = require_string_list(raw_card.get("tags"), f"{card_context}.tags")
            source_refs = validate_source_refs(raw_card.get("source_refs"), f"{card_context}.source_refs")
            card_ords = extract_cloze_ords([sentence])
            if not card_ords:
                raise ValueError(f"{card_context}.sentence must contain at least one cloze marker")

            note_id = stable_int_id(f"{deck_slug}:note:{authored_id}")
            if note_id in seen_note_ids:
                raise ValueError(f"Generated note id collision for {authored_id}")
            seen_note_ids.add(note_id)

            card_ids = []
            for card_ord in card_ords:
                card_id = stable_int_id(f"{deck_slug}:card:{authored_id}:{card_ord}")
                if card_id in seen_card_ids:
                    raise ValueError(f"Generated card id collision for {authored_id}:{card_ord}")
                seen_card_ids.add(card_id)
                card_ids.append(card_id)

            text_field = render_text_field(prompt, sentence)
            extra_field = render_extra_field(extra)
            media_refs = collect_media_refs([text_field, extra_field])
            sort_field = html_to_text(text_field)
            checksum = field_checksum(sort_field)

            authored_cards.append(
                {
                    "authored_id": authored_id,
                    "module": module_name,
                    "type": card_type,
                    "prompt": prompt,
                    "sentence": sentence,
                    "extra": extra,
                    "source_refs": source_refs,
                    "tags": merge_tags(default_tags, [f"module::{module_name}"], module_tags, card_tags),
                    "note_id": note_id,
                    "guid": build_guid(deck_slug, authored_id),
                    "card_ords": card_ords,
                    "card_ids": card_ids,
                    "fields": [text_field, extra_field],
                    "sort_field": sort_field,
                    "checksum": checksum,
                    "media_refs": media_refs,
                }
            )

    if not authored_cards:
        raise ValueError(f"No authored cards found in {modules_dir}")

    return authored_cards


def validate_media_files(media_dir: Path, authored_cards: List[Dict[str, Any]]) -> List[Path]:
    referenced = sorted({ref for card in authored_cards for ref in card["media_refs"]})
    for relative_ref in referenced:
        media_path = safe_join(media_dir, relative_ref)
        if not media_path.exists():
            raise FileNotFoundError(f"Referenced media file is missing: {media_path}")

    if not media_dir.exists():
        return []
    return sorted(path for path in media_dir.rglob("*") if path.is_file())


def build_model_payload(model_id: int, model_name: str, deck_id: int, now_seconds: int) -> Dict[str, Any]:
    return {
        str(model_id): {
            "tmpls": [
                {
                    "afmt": "{{cloze:Text}}<hr id=answer>\n{{Extra}}",
                    "name": "Cloze",
                    "qfmt": "{{cloze:Text}}",
                    "did": None,
                    "ord": 0,
                    "bafmt": "",
                    "bqfmt": "",
                }
            ],
            "css": (
                ".card {\n"
                " font-family: Arial;\n"
                " font-size: 20px;\n"
                " text-align: left;\n"
                " color: #1f2937;\n"
                " background-color: #fffdf8;\n"
                "}\n\n"
                ".prompt {\n"
                " font-size: 14px;\n"
                " font-weight: bold;\n"
                " letter-spacing: 0.04em;\n"
                " text-transform: uppercase;\n"
                " color: #6b7280;\n"
                " margin-bottom: 12px;\n"
                "}\n\n"
                ".sentence {\n"
                " line-height: 1.5;\n"
                "}\n\n"
                ".extra {\n"
                " margin-top: 16px;\n"
                " font-size: 16px;\n"
                " color: #374151;\n"
                "}\n\n"
                ".cloze {\n"
                " font-weight: bold;\n"
                " color: #0f62fe;\n"
                "}"
            ),
            "latexPre": (
                "\\documentclass[12pt]{article}\n"
                "\\special{papersize=3in,5in}\n"
                "\\usepackage[utf8]{inputenc}\n"
                "\\usepackage{amssymb,amsmath}\n"
                "\\pagestyle{empty}\n"
                "\\setlength{\\parindent}{0in}\n"
                "\\begin{document}\n"
            ),
            "did": deck_id,
            "tags": [],
            "flds": [
                {"font": "Arial", "media": [], "name": "Text", "rtl": False, "ord": 0, "sticky": False, "size": 20},
                {"font": "Arial", "media": [], "name": "Extra", "rtl": False, "ord": 1, "sticky": False, "size": 20},
            ],
            "id": str(model_id),
            "name": model_name,
            "type": 1,
            "latexPost": "\\end{document}",
            "sortf": 0,
            "vers": [],
            "usn": -1,
            "mod": now_seconds,
        }
    }


def build_decks_payload(deck_id: int, deck_title: str, deck_description: str, model_id: int, now_seconds: int) -> Dict[str, Any]:
    return {
        "1": {
            "newToday": [0, 0],
            "revToday": [0, 0],
            "lrnToday": [0, 0],
            "timeToday": [0, 0],
            "conf": 1,
            "usn": 0,
            "desc": "",
            "dyn": 0,
            "collapsed": False,
            "extendNew": 10,
            "extendRev": 50,
            "id": 1,
            "name": "Default",
            "mod": now_seconds,
        },
        str(deck_id): {
            "desc": deck_description,
            "name": deck_title,
            "extendRev": 50,
            "usn": -1,
            "collapsed": False,
            "browserCollapsed": False,
            "newToday": [0, 0],
            "mid": str(model_id),
            "dyn": 0,
            "extendNew": 10,
            "lrnToday": [0, 0],
            "conf": 1,
            "revToday": [0, 0],
            "timeToday": [0, 0],
            "id": deck_id,
            "mod": now_seconds,
        },
    }


def build_conf_payload(deck_id: int, model_id: int, next_pos: int) -> Dict[str, Any]:
    return {
        "activeDecks": [deck_id],
        "curDeck": deck_id,
        "newSpread": 0,
        "collapseTime": 1200,
        "timeLim": 0,
        "estTimes": True,
        "dueCounts": True,
        "curModel": str(model_id),
        "nextPos": next_pos,
        "sortType": "noteFld",
        "sortBackwards": False,
        "addToCur": True,
        "dayLearnFirst": False,
        "newBury": True,
    }


def build_dconf_payload(now_seconds: int) -> Dict[str, Any]:
    return {
        "1": {
            "name": "Default",
            "new": {
                "delays": [1, 10],
                "ints": [1, 4, 7],
                "initialFactor": 2500,
                "separate": True,
                "order": 1,
                "perDay": 20,
                "bury": False,
            },
            "lapse": {
                "delays": [10],
                "mult": 0,
                "minInt": 1,
                "leechFails": 8,
                "leechAction": 0,
            },
            "rev": {
                "perDay": 200,
                "ease4": 1.3,
                "fuzz": 0.05,
                "minSpace": 1,
                "ivlFct": 1,
                "maxIvl": 36500,
                "bury": False,
                "hardFactor": 1.2,
            },
            "maxTaken": 60,
            "timer": 0,
            "autoplay": True,
            "replayq": True,
            "mod": now_seconds,
            "usn": 0,
            "id": 1,
        }
    }


def initialize_collection_db(
    db_path: Path,
    manifest: Dict[str, Any],
    authored_cards: List[Dict[str, Any]],
) -> None:
    now_seconds = current_epoch_seconds()
    now_millis = current_epoch_millis()
    deck = manifest["deck"]
    model = manifest["model"]
    deck_id = int(deck["deck_id"])
    model_id = int(model["id"])

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.executescript(SCHEMA_SQL)
        cursor.execute(
            """
            INSERT INTO col (
                id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                now_seconds,
                now_millis,
                now_millis,
                11,
                0,
                -1,
                0,
                json.dumps(build_conf_payload(deck_id, model_id, len(authored_cards) + 1), ensure_ascii=False),
                json.dumps(
                    build_model_payload(model_id, model["name"], deck_id, now_seconds),
                    ensure_ascii=False,
                ),
                json.dumps(
                    build_decks_payload(
                        deck_id,
                        deck["title"],
                        deck.get("description", ""),
                        model_id,
                        now_seconds,
                    ),
                    ensure_ascii=False,
                ),
                json.dumps(build_dconf_payload(now_seconds), ensure_ascii=False),
                json.dumps({}, ensure_ascii=False),
            ),
        )

        due = 1
        for authored_card in authored_cards:
            cursor.execute(
                """
                INSERT INTO notes (
                    id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    authored_card["note_id"],
                    authored_card["guid"],
                    model_id,
                    now_seconds,
                    -1,
                    serialize_tags(authored_card["tags"]),
                    "\x1f".join(authored_card["fields"]),
                    authored_card["sort_field"],
                    authored_card["checksum"],
                    0,
                    "",
                ),
            )

            for card_id, card_ord in zip(authored_card["card_ids"], authored_card["card_ords"]):
                cursor.execute(
                    """
                    INSERT INTO cards (
                        id, nid, did, ord, mod, usn, type, queue, due, ivl, factor,
                        reps, lapses, left, odue, odid, flags, data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        card_id,
                        authored_card["note_id"],
                        deck_id,
                        card_ord,
                        now_seconds,
                        -1,
                        0,
                        0,
                        due,
                        0,
                        2500,
                        0,
                        0,
                        1001,
                        0,
                        0,
                        0,
                        "",
                    ),
                )
                due += 1

        connection.commit()
    finally:
        connection.close()


def build_apkg(authored_dir: Path, output_path: Path, authored_cards: List[Dict[str, Any]], manifest: Dict[str, Any]) -> None:
    media_dir = authored_dir / Path(manifest.get("paths", {}).get("media_dir", "media"))
    media_files = validate_media_files(media_dir, authored_cards)

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        db_path = temp_dir / "collection.anki2"
        initialize_collection_db(db_path, manifest, authored_cards)

        media_manifest = {}
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(db_path, arcname="collection.anki2")
            for index, media_file in enumerate(media_files):
                relative_name = media_file.relative_to(media_dir).as_posix()
                media_manifest[apkg_member_name(index)] = relative_name
                archive.write(media_file, arcname=apkg_member_name(index))
            archive.writestr("media", json.dumps(media_manifest, ensure_ascii=False))


def write_build_exports(
    build_dir: Path,
    manifest: Dict[str, Any],
    version: str,
    authored_cards: List[Dict[str, Any]],
) -> None:
    build_dir.mkdir(parents=True, exist_ok=True)
    summary_payload = {
        "deck_slug": manifest["deck"]["slug"],
        "deck_title": manifest["deck"]["title"],
        "version": version,
        "modules": sorted({card["module"] for card in authored_cards}),
        "notes": len(authored_cards),
        "cards": sum(len(card["card_ords"]) for card in authored_cards),
        "source_decks": manifest.get("source_decks", []),
    }
    cards_payload = [
        {
            "id": card["authored_id"],
            "module": card["module"],
            "type": card["type"],
            "prompt": card["prompt"],
            "sentence": card["sentence"],
            "extra": card["extra"],
            "tags": card["tags"],
            "source_refs": card["source_refs"],
            "note_id": card["note_id"],
            "card_ords": card["card_ords"],
        }
        for card in authored_cards
    ]
    write_json(build_dir / "summary.json", summary_payload)
    write_json(build_dir / "cards.json", cards_payload)


def stage_release_bundle(
    authored_dir: Path,
    manifest: Dict[str, Any],
    version: str,
    compiled_apkg: Path,
    authored_cards: List[Dict[str, Any]],
    build_root: Path,
    release_root: Path,
) -> Path:
    deck_slug = manifest["deck"]["slug"]
    release_dir = release_root / deck_slug / version
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
            f"- Source deck count: {len(manifest.get('source_decks', []))}",
            f"- Module count: {len({card['module'] for card in authored_cards})}",
            f"- Notes: {len(authored_cards)}",
            f"- Cards: {sum(len(card['card_ords']) for card in authored_cards)}",
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
        "assets": [release_asset_path.name],
        "source_authored_dir": str(authored_dir),
        "build_dir": str(build_root / deck_slug / version),
    }
    write_json(release_dir / "release.json", release_payload)
    return release_dir


def build_release_from_authored(
    authored_dir: Path,
    version: str,
    build_root: Path,
    release_root: Path,
) -> Dict[str, Path]:
    manifest = load_yaml(authored_dir / "manifest.yaml")
    if manifest.get("authored_format_version") != 1:
        raise ValueError(f"Unsupported authored format version: {manifest.get('authored_format_version')}")

    require_string(manifest.get("deck", {}).get("slug"), "manifest.deck.slug")
    require_string(manifest.get("deck", {}).get("title"), "manifest.deck.title")
    require_string(manifest.get("model", {}).get("name"), "manifest.model.name")
    int(manifest.get("deck", {}).get("deck_id"))
    int(manifest.get("model", {}).get("id"))

    authored_cards = load_authored_cards(authored_dir, manifest)
    deck_slug = manifest["deck"]["slug"]
    asset_name = manifest["release"]["asset_name_template"].replace("{version}", version)
    build_dir = build_root / deck_slug / version
    compiled_apkg = build_dir / asset_name

    build_apkg(authored_dir, compiled_apkg, authored_cards, manifest)
    write_build_exports(build_dir, manifest, version, authored_cards)
    release_dir = stage_release_bundle(
        authored_dir,
        manifest,
        version,
        compiled_apkg,
        authored_cards,
        build_root,
        release_root,
    )
    return {
        "compiled_apkg": compiled_apkg,
        "release_dir": release_dir,
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    outputs = build_release_from_authored(
        args.authored_dir,
        version=args.version,
        build_root=args.build_root,
        release_root=args.release_root,
    )
    print(f"built {outputs['compiled_apkg']}")
    print(f"release bundle {outputs['release_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
