#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://ankiweb.net"
INFO_PATH = "/svc/shared/item-info"
DOWNLOAD_PATH = "/svc/shared/download-deck/{shared_id}?t={token}"
CONFIG_PATH = Path("configs/shared_decks.json")
USER_AGENT = "anki-ielts/0.1"
SHARED_INFO_RE = re.compile(r"/shared/info/(\d+)")


class FetchError(RuntimeError):
    pass


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch AnkiWeb shared decks into raw/ from configs/shared_decks.json."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="Path to the JSON config file.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if the target path already exists.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def http_get_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read()


def read_varint(data: bytes, offset: int) -> Tuple[int, int]:
    value = 0
    shift = 0

    while True:
        if offset >= len(data):
            raise FetchError("Unexpected end of protobuf data while reading varint")

        current = data[offset]
        offset += 1
        value |= (current & 0x7F) << shift

        if not current & 0x80:
            return value, offset

        shift += 7
        if shift > 63:
            raise FetchError("Invalid protobuf varint")


def read_length_delimited(data: bytes, offset: int) -> Tuple[bytes, int]:
    length, offset = read_varint(data, offset)
    end = offset + length
    if end > len(data):
        raise FetchError("Unexpected end of protobuf data while reading bytes")
    return data[offset:end], end


def skip_field(data: bytes, offset: int, wire_type: int) -> int:
    if wire_type == 0:
        _, offset = read_varint(data, offset)
        return offset
    if wire_type == 1:
        end = offset + 8
        if end > len(data):
            raise FetchError("Unexpected end of protobuf data while skipping 64-bit field")
        return end
    if wire_type == 2:
        _, end = read_length_delimited(data, offset)
        return end
    if wire_type == 5:
        end = offset + 4
        if end > len(data):
            raise FetchError("Unexpected end of protobuf data while skipping 32-bit field")
        return end

    raise FetchError(f"Unsupported protobuf wire type: {wire_type}")


def parse_string(data: bytes, offset: int) -> Tuple[str, int]:
    raw, offset = read_length_delimited(data, offset)
    return raw.decode("utf-8", errors="replace"), offset


def parse_deck_payload(data: bytes) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    offset = 0

    while offset < len(data):
        tag, offset = read_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if field_number == 5 and wire_type == 2:
            payload["download_key"], offset = parse_string(data, offset)
        elif field_number in {1, 2, 3} and wire_type == 0:
            value, offset = read_varint(data, offset)
            if field_number == 1:
                payload["notes"] = value
            elif field_number == 2:
                payload["audio"] = value
            elif field_number == 3:
                payload["images"] = value
        else:
            offset = skip_field(data, offset, wire_type)

    return payload


def parse_available_payload(data: bytes) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    offset = 0

    while offset < len(data):
        tag, offset = read_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if field_number == 5 and wire_type == 2:
            payload["title"], offset = parse_string(data, offset)
        elif field_number == 10 and wire_type == 2:
            nested, offset = read_length_delimited(data, offset)
            payload["item_kind"] = "deck"
            payload["deck"] = parse_deck_payload(nested)
        elif field_number == 11 and wire_type == 2:
            _, offset = read_length_delimited(data, offset)
            payload["item_kind"] = "addon"
        else:
            offset = skip_field(data, offset, wire_type)

    return payload


def parse_item_info(data: bytes) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"status": "unknown"}
    offset = 0

    while offset < len(data):
        tag, offset = read_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 0x07

        if field_number == 1 and wire_type == 2:
            nested, offset = read_length_delimited(data, offset)
            payload["status"] = "available"
            payload.update(parse_available_payload(nested))
        elif field_number == 2 and wire_type == 0:
            value, offset = read_varint(data, offset)
            if value:
                payload["status"] = "missing"
        elif field_number == 3 and wire_type == 0:
            value, offset = read_varint(data, offset)
            if value:
                payload["status"] = "access_denied"
        else:
            offset = skip_field(data, offset, wire_type)

    return payload


def extract_shared_id(entry: Dict[str, Any]) -> int:
    if "shared_id" in entry:
        return int(entry["shared_id"])

    url = entry.get("url")
    if isinstance(url, str):
        match = SHARED_INFO_RE.search(url)
        if match:
            return int(match.group(1))

    raise FetchError("Each deck entry must include either shared_id or a valid shared/info URL")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "deck"


def resolve_filename(entry: Dict[str, Any], shared_id: int, title: str) -> str:
    filename = entry.get("filename")
    if isinstance(filename, str) and filename.strip():
        return filename
    return f"{shared_id}-{slugify(title)}.apkg"


def fetch_metadata(shared_id: int) -> Dict[str, Any]:
    info_url = f"{BASE_URL}{INFO_PATH}?{urlencode({'sharedId': shared_id})}"
    response = parse_item_info(http_get_bytes(info_url))

    status = response.get("status")
    if status == "missing":
        raise FetchError(f"Shared item {shared_id} is missing")
    if status == "access_denied":
        raise FetchError(f"Shared item {shared_id} is access denied")
    if status != "available":
        raise FetchError(f"Shared item {shared_id} returned unexpected status: {status}")

    if response.get("item_kind") != "deck":
        raise FetchError(f"Shared item {shared_id} is not a deck")

    title = str(response.get("title") or shared_id)
    deck = response.get("deck") or {}
    download_key = deck.get("download_key")
    if not download_key:
        raise FetchError(f"Shared item {shared_id} did not include a download key")

    return {
        "title": title,
        "download_key": download_key,
        "notes": deck.get("notes"),
        "audio": deck.get("audio"),
        "images": deck.get("images"),
    }


def download_apkg(shared_id: int, download_key: str) -> bytes:
    deck_url = BASE_URL + DOWNLOAD_PATH.format(
        shared_id=shared_id,
        token=quote(download_key, safe=""),
    )
    return http_get_bytes(deck_url)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FetchError(f"Config file does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    if not isinstance(config, dict):
        raise FetchError("Config file must contain a JSON object")

    decks = config.get("decks")
    if not isinstance(decks, list) or not decks:
        raise FetchError("Config file must contain a non-empty decks array")

    return config


def fetch_from_entry(entry: Dict[str, Any], output_root: Path, force: bool) -> Path:
    shared_id = extract_shared_id(entry)
    metadata = fetch_metadata(shared_id)
    filename = resolve_filename(entry, shared_id, metadata["title"])
    target = output_root / filename

    if target.exists() and not force:
        print(f"skip {shared_id}: {target} already exists")
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    deck_bytes = download_apkg(shared_id, metadata["download_key"])
    target.write_bytes(deck_bytes)

    print(
        f"saved {shared_id}: {target} "
        f"({len(deck_bytes)} bytes, title={metadata['title']!r})"
    )
    return target


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    try:
        config = load_config(args.config)
        output_root = Path(config.get("output_dir", "raw"))

        for raw_entry in config["decks"]:
            if not isinstance(raw_entry, dict):
                raise FetchError("Each deck entry must be a JSON object")
            fetch_from_entry(raw_entry, output_root, args.force)
    except FetchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
