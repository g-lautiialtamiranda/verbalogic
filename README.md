# VerbaLogic

Select text in any Windows app, press **Ctrl+Alt+D**, and a popup shows:

- the translation in your two languages (Spanish | English by default, + Portuguese on demand),
- **synonyms** grouped by noun/verb/adjective, in both languages (real dictionary data, not AI). Where Google has none in Spanish, **similar words** taken from its translations,
- **pronunciation** of each word with one click,
- **saved words and history**: star a word to keep it, and reopen any recent lookup,
- other translations and **real example sentences**,
- **every meaning of a word**, one at a time: step through them with the arrows, and the translation, definition, synonyms and example all follow the meaning you're on,
- **"Other ways to say it"**: short, natural rewrites (casual / neutral / formal), with Spanish in both *vos* (Argentina) and neutral versions. This part uses a free AI model through OpenRouter and is optional.

Free to run: translations and synonyms use Google's free endpoints and Datamuse (no key). Rewrites use OpenRouter's free models (free key, no card).

## Requirements
- Windows 10 or 11
- [Python 3.11 or newer](https://www.python.org/downloads/). In the installer, tick **"Add python.exe to PATH"**.

## Install
```powershell
git clone https://github.com/g-lautiialtamiranda/verbalogic.git
cd verbalogic
.\scripts\install.cmd
```
No git? On the repo page, click **Code → Download ZIP**, unzip it, and double-click `scripts\install.cmd`.

Put the folder somewhere with a short path, like `Documents\verbalogic`. Very deep folders can hit Windows' 260-character path limit during install.

The script creates a private Python environment (`.venv`) inside the folder and installs VerbaLogic there. Nothing is installed system-wide. If you'd rather do it by hand:
```powershell
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e .
```

## Run it
Double-click `scripts\start-verbalogic.cmd`, or run it from a terminal.

A purple **V** appears in the system tray. Right-click it for Settings, the config file, "Start with Windows" and Quit.

## Update
```powershell
git pull
.\scripts\install.cmd
```

## Use it

| Action | How |
|---|---|
| Look something up | Select text, press **Ctrl+Alt+D** |
| Look up something typed | Click the tray icon (or press the shortcut with nothing selected), type, **Enter** |
| Copy a translation | **Ctrl+1 / Ctrl+2 / Ctrl+3**, or the copy icon |
| Copy a synonym or rewrite | Click it |
| Look up a synonym | Double-click it |
| Hear the pronunciation | Speaker icon, or **Ctrl+Shift+1 / 2 / 3** |
| Save a word | Star icon, or **Ctrl+S** |
| Reopen a saved word or a recent lookup | History icon, **Ctrl+H**, or tray → *Saved and recent lookups* |
| Switch meaning (e.g. *bank*: river / money / tilt…) | **‹ ›** under the original word, or **Alt+← / Alt+→** |
| See all meanings and jump to one | Click **Meaning 2 of 8 ▾**, or **Alt+↓** |
| Add Portuguese | **+ PT** in the header |
| Keep the popup open | Pin icon |
| Close | **Esc**, or click anywhere else |

### In Warp and other terminals
In a terminal `Ctrl+C` means "stop", so VerbaLogic never sends it there. For Warp it sends `Ctrl+Shift+C` (Warp's copy). Warp also copies on select by default.
Inside full-screen terminal apps (like Claude Code), Warp's selection sometimes doesn't reach the clipboard. If the popup shows old text, fix it in the box at the top and press Enter.

## Rewrites (optional): free OpenRouter key
1. Create an account at [openrouter.ai](https://openrouter.ai) (no card needed).
2. Go to [openrouter.ai/keys](https://openrouter.ai/keys) → **Create key** → copy it.
3. Tray icon → **Settings → Rewrites** → paste it → **Save key** → **Test rewrites**.

The key is stored in Windows Credential Manager, never in a file. Free models have daily limits, and repeat lookups are cached so they don't count twice. Free providers may log what you send, so don't use rewrites on confidential text (translations go to Google either way).

## Configure
Everything lives in `%APPDATA%\VerbaLogic\config.toml` (tray → *Open config file*): shortcut, languages, theme, accent color, popup size, per-app copy keys, AI models, Spanish style and history (on/off, how many recent lookups to keep). Changes apply when you save. A bad value falls back to its default, and you get a notification.

## Develop
```powershell
.venv\Scripts\python -m pip install -e ".[dev]"   # adds pytest
.venv\Scripts\python -m pytest              # tests
.venv\Scripts\python -m verbalogic --show "improve"   # open the popup with text, no hotkey
```

Layout: `src/verbalogic/` — `hotkey.py` (Win32 RegisterHotKey), `capture.py` (copy + clipboard), `lookup.py` (orchestration + cache), `providers/` (Google, Datamuse, pronunciation, OpenAI-compatible LLM), `history.py` (saved words and recent lookups), `rewrites.py` + `prompts/rewrites.md` (prompt and anti-slop filter), `ui/` (popup, settings, theme).

Log file: `%APPDATA%\VerbaLogic\verbalogic.log`. Saved words and history are in `history.sqlite` in the same folder, and pronunciation clips are cached in `tts\`.

## Contributing
Found a bug or have an idea? [Open an issue](https://github.com/g-lautiialtamiranda/verbalogic/issues/new/choose). Want to write the code yourself? See [CONTRIBUTING.md](CONTRIBUTING.md). Open ideas live in [`suggestions/`](suggestions/README.md), and what has been built or decided, session by session, in [`record/`](record/README.md). The maintainer reviews every issue and pull request and decides what goes in.

## License
[MIT](LICENSE)
