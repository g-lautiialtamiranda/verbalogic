# Suggestions

The VerbaLogic roadmap: **open** ideas for improving the app, one file each, grouped by type:

- `frontend/`: Visuals and layout: how the popup looks and reads (none open right now).
- `functional/`: Features and behaviour: what the app does.
- `reliability/`: Data sources, errors, privacy, speed and tests.
- `ideas/`: Bigger or later ideas, to talk through before building.

Only open suggestions live here. What has been built, and what was decided against, is in [`record/`](../record/README.md), one short log per work session.

## Have an idea or found a problem?
Please don't add files here. [Open an issue](https://github.com/g-lautiialtamiranda/verbalogic/issues/new/choose) instead. The maintainer reviews every issue and decides what gets built. Accepted ideas may get a file and an ID here.

## How it works
- Each suggestion has an ID (`F-` frontend, `U-` functional, `R-` reliability, `I-` ideas) and its own file with the what and the why. IDs are never reused.
- **Status:** `proposed` → `approved`. Then:
  - **built:** the file is removed from here, and one line about what changed goes into that session's log in `record/`.
  - **rejected:** the file is deleted, and the session log notes the decision in one line.
- **Effort:** S = under an hour, M = a few hours, L = a day or more.

## Index
| ID | Suggestion | Type | Effort | Status |
|---|---|---|---|---|
| [U-07](functional/U-07-language-detection.md) | Better language detection for ambiguous words | functional | S | proposed |
| [U-08](functional/U-08-phonetics.md) | Phonetic transcription for English words | functional | S | proposed |
| [U-09](functional/U-09-register-labels.md) | Formal / informal labels on synonyms | functional | S | proposed |
| [U-10](functional/U-10-compact-bubble.md) | Compact bubble for single words | functional | M | proposed |
| [U-11](functional/U-11-everyday-expressions.md) | Everyday expressions, idioms and metaphors | functional | M | proposed |
| [U-12](functional/U-12-softer-euphemisms.md) | Softer ways to say it (euphemisms and tactful phrasing) | functional | S | proposed |
| [U-13](functional/U-13-everyday-sentences.md) | Real everyday sentences (free, no key) | functional | S | proposed |
| [R-01](reliability/R-01-endpoint-fallback.md) | Second dictionary endpoint as a fallback | reliability | S | proposed |
| [R-02](reliability/R-02-backoff-state.md) | Smarter waiting after a Google limit | reliability | S | proposed |
| [R-03](reliability/R-03-private-log.md) | Stop writing looked-up text to the log | reliability | S | proposed |
| [R-04](reliability/R-04-start-with-windows.md) | Start with Windows on by default | reliability | S | proposed |
| [R-05](reliability/R-05-popup-smoke-test.md) | Automated popup screenshot test | reliability | S | proposed |
| [R-06](reliability/R-06-windows-installer.md) | A real Windows installer | reliability | L | proposed |
| [I-01](ideas/I-01-context-meaning.md) | Pick the meaning from the sentence | ideas | L | proposed |
| [I-02](ideas/I-02-language-pairs.md) | Per-app language pairs and more languages | ideas | M | proposed |
| [I-03](ideas/I-03-review-mode.md) | Review mode for saved words | ideas | M | proposed |
| [I-04](ideas/I-04-conjugations.md) | Verb conjugations | ideas | M | proposed |
