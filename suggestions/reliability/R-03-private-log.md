# R-03 · Stop writing looked-up text to the log

**Status:** proposed  
**Effort:** S

## What
The log records every request URL, and the URL contains the full text you selected (whole paragraphs appear in `verbalogic.log`). Log only the length and language of each lookup, and turn down the HTTP library's logging.

## Why
Privacy: anything you select ends up in a plain-text file.
