# Decision Log

## Primary Product

The repo started as a pipeline for patching one inherited IELTS deck, but that is no longer the main direction.

Current decision:

- source decks are inputs
- authored decks are the publishable product

Reason:

- the original source deck structure was weak
- rewriting content inside a weak note design has diminishing returns
- the tooling remains useful even when the inherited content is not

## Source Deck Policy

Use shared `.apkg` files as reference material only unless the user explicitly wants a patched inherited release.

What source decks are good for:

- mining example sentences
- mining useful phrasing
- spotting bad patterns worth correcting
- extracting topic coverage

What source decks are not good for by default:

- defining the final note model
- defining the final release structure

## Editable Source-Deck Policy

The inherited-deck patch pipeline stays in the repo because it is still useful for:

- quick fixes to bad source decks
- inspection/debugging
- line-based experimental edits

Key rule:

- base note YAML stays unchanged
- `changes/cards/<note-id>.patch` is the source of change

If a patch changes cloze markers, rebuild the cards for that note and reset scheduling for that note.

## Authored Deck Source Format

Authored decks use module YAML files under:

- `editable/authored/<deck-slug>/modules/*.yaml`

This was chosen over one-note-per-file because it is easier to:

- review by topic
- author in batches
- curate content from multiple source decks
- reason about deck balance and coverage

## Supported Authored Card Model

Current authored deck compiler supports:

- `contextual_cloze`

This is the default because it is the best balance of:

- practical recall
- sentence-level context
- simple compilation logic
- low ambiguity

Potential future extension:

- `sentence_transform`

That should be additive, not a replacement for the current model.

## Grammar Deck Philosophy

The deck `ielts-writing-1-grammar-structure` is meant to teach practical grammar decisions for IELTS Writing Task 1.

It should optimize for:

- one grammar decision per card
- realistic Task 1 sentence contexts
- short rule notes in `extra`
- contrast pairs where misuse is common

It should avoid:

- giant synonym bundles
- vague prompts
- prompts that reveal the answer
- cards that test multiple unrelated decisions at once

## Release Tag Convention

GitHub release tags are repo-global.

That means:

- deck asset names can be deck-specific
- git tags still move forward across the whole repo

Current published tags before the grammar-deck publish step:

- `v0.3.0`
- `v0.4.0`

Planned next release at the time of this note:

- `v0.5.0`

## Validation Expectations

Before publishing an authored deck:

1. Build the exact release version.
2. Decompile the built `.apkg`.
3. Confirm notes/cards/models/decks look correct.
4. Run a prompt-leak sanity check against cloze targets.
5. Check `git status` so only intended source/docs changes are published.

## Current Known State

As of `2026-04-03`:

- `ielts-writing-task-1-core` exists as a curated authored deck
- `ielts-writing-1-grammar-structure` exists as a larger grammar-focused authored deck
- the grammar deck was expanded to `103` notes/cards across `9` modules before publish

## Likely Next Improvements

- order grammar modules by difficulty more explicitly
- add more negative-pair cards for common learner mistakes
- add more map/process grammar if those become a larger product focus
- only revisit compiler changes if authoring pain becomes real
