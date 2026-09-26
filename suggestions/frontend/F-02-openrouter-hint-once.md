# F-02 · Show the OpenRouter hint once, as a button

**Status:** done (2026-09-25)  
**Effort:** S

## What
Every single-word lookup shows "Add your free OpenRouter key in Settings…". Instead, show a small "Set up rewrites" button that opens Settings on the right tab for the first few lookups, then stop showing it. Another option: hide the section for single words, where rewrites add little.

## Why
It takes space on every lookup and repeats something you already know.

## What changed
Without a key, rewrites no longer run just to fail. Your first 3 lookups show "Natural rewrites need a free OpenRouter key" and a **Set up rewrites** button that opens Settings on the Rewrites tab. After that, nothing shows. The counter is `%APPDATA%\VerbaLogic\.rewrites_hint`; delete it to see the button again.
