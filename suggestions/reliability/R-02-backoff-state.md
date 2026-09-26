# R-02 · Smarter waiting after a Google limit

**Status:** proposed  
**Effort:** S

## What
Today the wait doubles on every hit (60s, 120s, 240s, 480s…) and is forgotten when the app restarts. Save it to disk and cap it lower. Before showing "resting", try one cheap test request, so a limit that has already lifted doesn't cost you minutes.

## Why
The 480s message you saw came from this doubling.
