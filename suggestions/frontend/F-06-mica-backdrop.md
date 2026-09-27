# F-06 · Windows 11 Mica / Acrylic backdrop

**Status:** proposed  
**Effort:** M

## What
Let the card use Windows 11's own translucent material (Acrylic, meant for short-lived popups like this one) through `DwmSetWindowAttribute(DWMWA_SYSTEMBACKDROP_TYPE)`, so the desktop shows through softly behind it, like the Start menu. On Windows 10, or if it fails, keep today's solid card. The rounded corners and the hand-drawn shadow need to be made to work with it. A setting would turn it off.

## Why
It makes VerbaLogic look like part of Windows 11 instead of a window drawn on top of it.

## References
- [DWM_SYSTEMBACKDROP_TYPE (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type)
- [PySide6-Frameless-Window](https://github.com/rayzchen/PySide6-Frameless-Window): an existing Python example of Mica/Acrylic on frameless windows
- [Qt Forum: rounded corners with acrylic on a frameless QWidget](https://forum.qt.io/topic/162168/how-to-round-the-corners-of-a-frameless-qwidget-when-also-applying-acrylic-effects)
