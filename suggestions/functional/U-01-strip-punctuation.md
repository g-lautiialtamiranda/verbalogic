# U-01 · Clean stray punctuation before dictionary lookups

**Status:** rejected (2026-09-25)  
**Effort:** S

## What
The log shows lookups like `terminal)` and `what follows?` sent as-is to the dictionary and to Datamuse, which then return nothing useful. Strip the punctuation, quotes and brackets around the text before the dictionary step. The translation can keep the original text.

## Why
Double-clicking to select a word often grabs a bracket, comma or question mark with it.

## Outcome
Maintainer decision: punctuation can change what you mean, and the translator should know that. Text is sent exactly as selected, which is how it already worked.
