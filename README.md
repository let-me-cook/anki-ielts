# anki-ielts

This repo uses `uv` with a local `.venv` to:

- fetch one or more shared `.apkg` source decks from AnkiWeb
- decompile those source decks into reviewable JSON
- optionally patch inherited source decks in place
- extract candidate material from source decks
- author one new curated deck in module-based YAML
- compile that authored deck into a releaseable `.apkg`

## Setup

Create the environment:

```bash
uv venv .venv
```

Activate it if you want a shell-local Python environment:

```bash
source .venv/bin/activate
```

## Fetch source decks

Edit `configs/shared_decks.json`, then run:

```bash
uv run python scripts/fetch_apkgs.py
```

Downloaded `.apkg` files are written to `raw/`. You can list multiple source decks in the config.

## Decompile source decks

Turn an `.apkg` into a readable folder with extracted media and JSON exports:

```bash
uv run python scripts/decompile_apkg.py raw/2090856176-IELTS-Writing-Part-1.apkg
```

This writes output to `decompiled/<apkg-stem>/`.

## Extract candidate material

Export decompiled notes into a reviewable YAML file for curation:

```bash
uv run python scripts/extract_candidates.py decompiled/2090856176-IELTS-Writing-Part-1 --output /tmp/candidates.yaml
```

This does not create publishable notes. It gives you raw source material to mine for examples.

## Initialize an authored deck

Create a new module-based authored deck workspace:

```bash
uv run python scripts/init_authored_deck.py ielts-writing-task-1-core \
  --title "IELTS Writing Task 1 Core" \
  --source-deck 2090856176-IELTS-Writing-Part-1 \
  --default-tag ielts \
  --default-tag writing-task-1 \
  --default-tag authored
```

This writes a new deck under `editable/authored/<deck-slug>/`.

The repo already includes one example authored deck at:

```text
editable/authored/ielts-writing-task-1-core/
```

## Author module YAML

Authored cards live in topic files under `editable/authored/<deck-slug>/modules/`.

Example:

```yaml
module: comparisons
tags:
  - comparison
cards:
  - id: compare_car_spending
    type: contextual_cloze
    prompt: Compare UK and France car spending in one sentence.
    sentence: The UK spent around £450k on cars, {{c1::compared with}} exactly £400k in France.
    extra: Use this when two figures are close enough to compare directly.
    tags:
      - data-comparison
    source_refs:
      - deck: 2090856176-IELTS-Writing-Part-1
        note_id: 1466416397068
```

Current authored deck rules:

- one YAML file per module
- supported card type is `contextual_cloze`
- `sentence` must contain at least one cloze marker like `{{c1::...}}`
- `prompt` is required and should not reveal the answer
- `source_refs` are optional provenance links back to source decks

## Build an authored deck

Compile the authored module deck into a fresh `.apkg` and local release bundle:

```bash
uv run python scripts/build_authored_deck.py editable/authored/ielts-writing-task-1-core --version v0.1.0
```

This writes:

- the compiled deck to `build/<deck-slug>/<version>/`
- build metadata such as `summary.json` and `cards.json` to the same build directory
- the local GitHub release bundle to `release/<deck-slug>/<version>/`

## Simplify decompiled output

Turn a decompiled source deck into a note-by-note editable YAML workspace:

```bash
uv run python scripts/simplify_decompiled.py decompiled/2090856176-IELTS-Writing-Part-1
```

This writes output to `editable/<apkg-stem>/`.

## Patch inherited source-deck notes

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

## Build a patched source deck

Compile the editable YAML back into an `.apkg` and stage a release bundle:

```bash
uv run python scripts/build_release.py editable/2090856176-IELTS-Writing-Part-1 --version v0.1.0
```

This writes:

- the compiled deck to `build/<apkg-stem>/<version>/`
- the local GitHub release bundle to `release/<apkg-stem>/<version>/`
