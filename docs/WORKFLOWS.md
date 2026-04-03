# Workflows

## Setup

Create the local environment:

```bash
uv venv .venv
source .venv/bin/activate
```

## Fetch Source Decks

```bash
uv run python scripts/fetch_apkgs.py
```

Config file:

- `configs/shared_decks.json`

## Decompile A Source Deck

```bash
uv run python scripts/decompile_apkg.py raw/<deck>.apkg
```

Output:

- `decompiled/<deck>/`

## Extract Candidate Material

```bash
uv run python scripts/extract_candidates.py decompiled/<deck> --output /tmp/candidates.yaml
```

Use this for raw curation, not direct publishing.

## Patch An Inherited Source Deck

Simplify it first:

```bash
uv run python scripts/simplify_decompiled.py decompiled/<deck>
```

Then write unified diffs at:

- `editable/<deck>/changes/cards/<note-id>.patch`

Build it:

```bash
uv run python scripts/build_release.py editable/<deck> --version vX.Y.Z
```

## Create A New Authored Deck

```bash
uv run python scripts/init_authored_deck.py <deck-slug> --title "<Deck Title>"
```

Authored deck root:

- `editable/authored/<deck-slug>/`

Important files:

- `manifest.yaml`
- `modules/*.yaml`

## Build An Authored Deck

```bash
uv run python scripts/build_authored_deck.py editable/authored/<deck-slug> --version vX.Y.Z
```

Outputs:

- `build/<deck-slug>/<version>/`
- `release/<deck-slug>/<version>/`

## Validate An Authored Deck

Decompile the built asset:

```bash
uv run python scripts/decompile_apkg.py build/<deck-slug>/<version>/<deck-slug>-<version>.apkg --output-root /tmp/<deck-slug>-validate
```

Check:

- note/card counts
- model/deck counts
- obvious content issues

## Prompt-Leak Sanity Check

Use a quick check that compares cloze targets against prompts. The repo does not yet have a dedicated script, so a short one-off Python check is acceptable before publishing.

Goal:

- prompt should describe the writing situation
- prompt should not contain the exact cloze answer

## Publish

Preferred sequence:

1. build the exact release version
2. validate the built `.apkg`
3. `git add` only source/docs changes
4. `git commit`
5. `git tag <version>`
6. `git push origin main`
7. `git push origin <version>`
8. `gh release create <version> build/<deck-slug>/<version>/<deck-slug>-<version>.apkg --repo let-me-cook/anki-ielts --title "<Deck Title> <version>" --notes-file release/<deck-slug>/<version>/release-notes.md`
