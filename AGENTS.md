# Agent Context

## Purpose

This repo is an Anki deck refinery for IELTS Writing Task 1.

There are two workflows:

1. Source-deck workflow: fetch shared `.apkg` files, decompile them, optionally patch inherited notes, and rebuild them.
2. Authored-deck workflow: write new module-based YAML decks from scratch, compile them into fresh `.apkg` files, and publish those as the main product.

The long-term direction is authored decks. Source decks are reference material unless the user explicitly asks to ship a patched inherited deck.

## Where To Start

Read these files in this order:

1. `README.md`
2. `AGENTS.md`
3. `docs/DECISIONS.md`
4. `docs/WORKFLOWS.md`

## Repo Map

- `configs/`: shared-deck fetch config
- `raw/`: downloaded `.apkg` source decks
- `decompiled/`: machine-readable extracts of source decks
- `editable/<apkg-stem>/`: editable patched source-deck workspaces
- `editable/authored/<deck-slug>/`: authored module-based source decks
- `build/`: compiled local `.apkg` outputs
- `release/`: local release bundles for GitHub Releases
- `scripts/`: fetch, decompile, patch, compile, and helper tooling

## Product Direction

- Prefer authored decks over incremental patching when the source deck design is weak.
- Use source decks to mine examples, structures, and raw ideas.
- Do not treat inherited source notes as the primary product unless the user explicitly wants that.
- Keep prompts non-spoilery. A prompt should describe the writing situation, not reveal the cloze target.
- Favor one grammar or writing decision per card.

## Current Authored Decks

- `editable/authored/ielts-writing-task-1-core/`
  A curated Task 1 phrasing deck.
- `editable/authored/ielts-writing-1-grammar-structure/`
  A grammar-focused Task 1 deck. As of `2026-04-03`, it was last validated at `103` notes/cards across `9` modules.

## Authoring Rules

- Authored cards currently use `contextual_cloze`.
- `sentence` must contain at least one cloze marker like `{{c1::...}}`.
- `prompt` is required and should not leak the answer.
- `extra` should stay short and explain the rule or warning.
- `source_refs` are optional provenance links back to source decks.

For the grammar deck in particular:

- teach practical IELTS Writing Task 1 grammar, not general-English trivia
- prefer realistic report sentences over isolated phrase lists
- include contrast pairs when confusion is common
- keep wording formal but natural

## Release Conventions

- Git tags/releases are repo-global, not per-deck.
- Asset filenames are deck-specific.
- Build and validate the exact version you plan to release.
- Do not commit `build/` or `release/` artifacts unless the user asks for that explicitly.

## Before Publishing

1. Build the authored deck with `scripts/build_authored_deck.py`.
2. Decompile the built `.apkg` with `scripts/decompile_apkg.py`.
3. Confirm note/card counts and look for obvious prompt leaks.
4. Stage only source files plus docs.
5. Commit, tag, push, and create the GitHub release with the built `.apkg`.
