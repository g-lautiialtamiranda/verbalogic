# Contributing to VerbaLogic

Thanks for helping. There are three ways to contribute. In all of them, the maintainer reviews what you send and has the final say. Not every idea or change gets accepted, but every one gets read.

## Report a bug
[Open a bug report](https://github.com/g-lautiialtamiranda/verbalogic/issues/new?template=bug_report.yml). Say what you did, what you expected and what happened. The log (`%APPDATA%\VerbaLogic\verbalogic.log`) helps a lot. It can contain text you looked up, so check it and remove anything private before you paste it.

## Suggest an idea
[Open a suggestion](https://github.com/g-lautiialtamiranda/verbalogic/issues/new?template=suggestion.yml). Explain what you'd like and why it would help. Check [`suggestions/`](suggestions/README.md) first, since it might already be planned or might have been decided against.

## Propose a code change
1. For anything bigger than a small fix, open an issue first so we can agree on the idea before you spend time on it.
2. Fork the repo and create a branch.
3. Set up: run `scripts\install.cmd`, then `.venv\Scripts\python -m pip install -e ".[dev]"`.
4. Make the change and keep it focused on one thing. Match the style of the surrounding code.
5. Run the tests: `.venv\Scripts\python -m pytest`.
6. Open a pull request that explains what it changes and why, and links the issue. For visual changes, add a screenshot.

The maintainer will review it, may ask for changes, and decides whether to merge it.

## Ground rules
- Be kind and assume good intent.
- Never commit API keys, personal data or paths from your own PC.
- VerbaLogic should stay free to run: prefer free services that don't need a key.
