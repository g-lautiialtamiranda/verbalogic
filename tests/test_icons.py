import subprocess

import pytest
from PySide6.QtGui import QGuiApplication, QIcon

from verbalogic import startup
from verbalogic.ui.icon import ICO_SIZES, write_ico


@pytest.fixture(scope="module", autouse=True)
def qt():
    return QGuiApplication.instance() or QGuiApplication([])


def test_ico_has_every_size(tmp_path):
    path = tmp_path / "mark.ico"
    write_ico("#2F4A7A", path)
    assert sorted(s.width() for s in QIcon(str(path)).availableSizes()) == sorted(ICO_SIZES)


def _icon_location(link):
    ps = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{link}').IconLocation"
    return subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()


def test_update_icons_repoints_our_shortcuts_only(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    icons = tmp_path / "VerbaLogic"
    icons.mkdir()
    old, new = icons / "verbalogic-v1-111111.ico", icons / "verbalogic-v2-2f4a7a.ico"
    write_ico("#111111", old)
    write_ico("#2F4A7A", new)
    ours, pinned = startup.menu_shortcut_path(), startup.pinned_shortcut_path()
    ours.parent.mkdir(parents=True)
    pinned.parent.mkdir(parents=True)
    assert startup._create(ours, "-m verbalogic --open", "test", old)
    assert startup._create(pinned, "-m somethingelse", "not ours", old)

    assert startup.update_icons(new)
    assert _icon_location(ours).lower() == f"{new},0".lower()
    assert _icon_location(pinned).lower() == f"{old},0".lower()  # a shortcut to another app is left alone
    assert not old.exists() and new.exists()
