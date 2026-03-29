# anki-ielts

This repo uses `uv` with a local `.venv` and a config-driven fetch script for AnkiWeb shared decks.

## Setup

Create the environment:

```bash
uv venv .venv
```

Activate it if you want a shell-local Python environment:

```bash
source .venv/bin/activate
```

## Fetch decks

Edit `configs/shared_decks.json`, then run:

```bash
uv run python scripts/fetch_apkgs.py
```

Downloaded `.apkg` files are written to `raw/`.

## Decompile decks

Turn an `.apkg` into a readable folder with extracted media and JSON exports:

```bash
uv run python scripts/decompile_apkg.py raw/2090856176-IELTS-Writing-Part-1.apkg
```

This writes output to `decompiled/<apkg-stem>/`.

## Simplify decompiled output

Turn a decompiled deck into an editable YAML workspace:

```bash
uv run python scripts/simplify_decompiled.py decompiled/2090856176-IELTS-Writing-Part-1
```

This writes output to `editable/<apkg-stem>/`.

## Patch card text

For line-based edits, keep the base note YAML unchanged and add a unified diff patch at:

```bash
editable/<apkg-stem>/changes/cards/<note-id>.patch
```

Patch rules:

- target field is `fields.Text`
- patches are applied only during build
- if a patch changes cloze markers like `{{cN::...}}`, the edited note's cards are regenerated and its scheduling is reset
- if a patch does not apply cleanly, the build fails

Example:

```diff
--- a/text
+++ b/text
@@ -1 +1 @@
-old line
+new line
```

## Build a local release bundle

Compile the editable YAML back into an `.apkg` and stage a release bundle:

```bash
uv run python scripts/build_release.py editable/2090856176-IELTS-Writing-Part-1 --version v0.1.0
```

This writes:

- the compiled deck to `build/<apkg-stem>/<version>/`
- the local GitHub release bundle to `release/<apkg-stem>/<version>/`
