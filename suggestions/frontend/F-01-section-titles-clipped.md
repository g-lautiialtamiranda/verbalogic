# F-01 · Section titles lose part of their first letter

**Status:** done (2026-09-25)  
**Effort:** S

## What
Headings like "OTHER WAYS TO SAY IT" and "SYNONYMS" render with the first letter slightly cut off on the left (visible in your first screenshot and in the test screenshots). Probably the letter-spacing/padding on `#sectionTitle` in `ui/theme.qss`. Fix it so titles line up with the text under them.

## Why
Small, but it shows on every lookup and makes the popup look unfinished.

## What changed
The letters weren't clipped. Font kerning pushed "T" into "O" at this small bold size, and the fractional letter-spacing (0.8px) made the gaps uneven. The small all-caps labels (titles, language names, VERBALOGIC) are now made with `caps_label()` in `ui/widgets.py`, which turns kerning off, and use 1px letter-spacing.
