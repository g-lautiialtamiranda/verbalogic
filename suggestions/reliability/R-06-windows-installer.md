# R-06 · A real Windows installer

**Status:** proposed  
**Effort:** L

## What
Package VerbaLogic as a normal Windows program: one `.exe` built with PyInstaller or Nuitka, wrapped in an installer (for example Inno Setup) with a Start-menu entry, an uninstaller and "Start with Windows". Ideally signed, with a check for new versions on GitHub Releases. The script install stays for developers.

## Why
Today installing needs Python and a script. An installer is what lets you hand it to anyone, and it's the biggest step toward the app feeling like a finished product.
