# R-01 · Second dictionary endpoint as a fallback

**Status:** proposed  
**Effort:** S

## What
Google blocked the `gtx` endpoint for your connection, which is why the dictionary kept "resting", so VerbaLogic now uses `dict-chrome-ex`. If that one also gets limited some day, try the other one automatically, each with its own wait timer, instead of showing "Dictionary resting".

## Why
Keeps synonyms and meanings working when Google tightens one endpoint.
