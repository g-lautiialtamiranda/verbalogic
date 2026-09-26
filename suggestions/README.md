# Suggestions

The VerbaLogic roadmap: ideas for improving the app, one file each, grouped by type:

- `frontend/`: Visuals and layout: how the popup looks and reads.
- `functional/`: Features and behaviour: what the app does.
- `reliability/`: Data sources, errors, privacy, speed and tests.
- `ideas/`: Bigger or later ideas, to talk through before building.

## Have an idea or found a problem?
Please don't add files here. [Open an issue](https://github.com/g-lautiialtamiranda/verbalogic/issues/new/choose) instead. The maintainer reviews every issue and decides what gets built. Accepted ideas may get a file and an ID here.

## How it works
- Each suggestion has an ID (`F-` frontend, `U-` functional, `R-` reliability, `I-` ideas) and its own file with the what, the why and the outcome.
- **Status:** `proposed` → `approved` → `done` (or `rejected`), with the date. The status is kept both in the file and in the table below.
- **Effort:** S = under an hour, M = a few hours, L = a day or more.

## Index
| ID | Suggestion | Type | Effort | Status |
|---|---|---|---|---|
| [F-01](frontend/F-01-section-titles-clipped.md) | Section titles lose part of their first letter | frontend | S | done (2026-09-25) |
| [F-02](frontend/F-02-openrouter-hint-once.md) | Show the OpenRouter hint once, as a button | frontend | S | done (2026-09-25) |
| [F-03](frontend/F-03-meaning-list-jump.md) | Click "Meaning 2 of 8" to see all meanings | frontend | S | done (2026-09-25) |
| [F-04](frontend/F-04-empty-synonyms-state.md) | Quieter empty states | frontend | S | done (2026-09-25) |
| [U-01](functional/U-01-strip-punctuation.md) | Clean stray punctuation before dictionary lookups | functional | S | rejected (2026-09-25) |
| [U-02](functional/U-02-spanish-synonyms-fallback.md) | Spanish synonyms when Google has none | functional | S | proposed |
| [U-03](functional/U-03-pronunciation.md) | Pronunciation button | functional | S | proposed |
| [U-04](functional/U-04-history-favourites.md) | Lookup history and favourites | functional | M | proposed |
| [U-05](functional/U-05-anki-export.md) | Export saved words to Anki / CSV | functional | S | proposed |
| [U-06](functional/U-06-ai-meaning-match.md) | Use AI to match translations to meanings (with an OpenRouter key) | functional | M | proposed |
| [U-07](functional/U-07-language-detection.md) | Better language detection for ambiguous words | functional | S | proposed |
| [R-01](reliability/R-01-endpoint-fallback.md) | Second dictionary endpoint as a fallback | reliability | S | proposed |
| [R-02](reliability/R-02-backoff-state.md) | Smarter waiting after a Google limit | reliability | S | proposed |
| [R-03](reliability/R-03-private-log.md) | Stop writing looked-up text to the log | reliability | S | proposed |
| [R-04](reliability/R-04-start-with-windows.md) | Start with Windows on by default | reliability | S | proposed |
| [R-05](reliability/R-05-popup-smoke-test.md) | Automated popup screenshot test | reliability | S | proposed |
| [I-01](ideas/I-01-context-meaning.md) | Pick the meaning from the sentence | ideas | L | proposed |
| [I-02](ideas/I-02-language-pairs.md) | Per-app language pairs and more languages | ideas | M | proposed |
| [I-03](ideas/I-03-review-mode.md) | Review mode for saved words | ideas | M | proposed |
