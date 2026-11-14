"""Real mouse / keyboard automation and app launching.

pyautogui is imported lazily because on Linux it needs an X display at import time.
Moving the physical mouse into a screen corner aborts automation (pyautogui FAILSAFE).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from urllib.parse import quote_plus

log = logging.getLogger(__name__)

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"


class AutomationDisabled(Exception):
    pass


class AutomationUnavailable(RuntimeError):
    """Mouse/keyboard control can't start (no desktop session, missing OS permission, ...)."""


@dataclass
class ActionOutcome:
    ok: bool
    detail: str


# ---------------------------------------------------------------------------
# Key names
# ---------------------------------------------------------------------------
_KEY_ALIASES = {
    "control": "ctrl",
    "ctl": "ctrl",
    "cmd": "command",
    "meta": "command" if IS_MAC else "win",
    "super": "command" if IS_MAC else "win",
    "windows": "win",
    "option": "alt",
    "opt": "alt",
    "return": "enter",
    "escape": "esc",
    "del": "delete",
    "page up": "pageup",
    "page down": "pagedown",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "arrowup": "up",
    "arrowdown": "down",
    "arrowleft": "left",
    "arrowright": "right",
    "spacebar": "space",
    " ": "space",
}


def normalize_keys(keys: list[str] | str) -> list[str]:
    """['Mod', 'S'] -> ['ctrl', 's'] on Windows/Linux, ['command', 's'] on macOS."""
    if isinstance(keys, str):
        parts = [p for p in keys.replace("+", " ").split() if p]
    else:
        parts = [str(k) for k in keys]
    out: list[str] = []
    for k in parts:
        k = k.strip().lower()
        if not k:
            continue
        if k in ("mod", "primary"):
            k = "command" if IS_MAC else "ctrl"
        if IS_MAC and k == "win":
            k = "command"
        out.append(_KEY_ALIASES.get(k, k))
    return out


# ---------------------------------------------------------------------------
# App catalogue
# ---------------------------------------------------------------------------
WEB_APPS = {
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "netflix": "https://www.netflix.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "reddit": "https://www.reddit.com",
    "wikipedia": "https://www.wikipedia.org",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "calendar": "https://calendar.google.com",
    "google calendar": "https://calendar.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "docs": "https://docs.google.com",
    "whatsapp web": "https://web.whatsapp.com",
    "spotify web": "https://open.spotify.com",
    "amazon": "https://www.amazon.com",
}

_WIN_APPS = {
    "notepad": ["notepad"],
    "text editor": ["notepad"],
    "calculator": ["calc"],
    "calc": ["calc"],
    "paint": ["mspaint"],
    "file explorer": ["explorer"],
    "explorer": ["explorer"],
    "files": ["explorer"],
    "terminal": ["wt", "powershell"],
    "command prompt": ["cmd"],
    "cmd": ["cmd"],
    "powershell": ["powershell"],
    "task manager": ["taskmgr"],
    "settings": ["ms-settings:"],
    "browser": ["https://www.google.com"],
    "chrome": ["chrome"],
    "google chrome": ["chrome"],
    "edge": ["msedge"],
    "firefox": ["firefox"],
    "spotify": ["spotify:", "spotify"],
    "vscode": ["code"],
    "vs code": ["code"],
    "visual studio code": ["code"],
    "word": ["winword"],
    "excel": ["excel"],
    "powerpoint": ["powerpnt"],
    "outlook": ["outlook"],
    "discord": ["discord:", "discord"],
    "steam": ["steam:", "steam"],
    "camera": ["microsoft.windows.camera:"],
    "photos": ["ms-photos:"],
    "mail": ["outlookmail:", "mailto:"],
    "store": ["ms-windows-store:"],
    "snipping tool": ["ms-screenclip:", "snippingtool"],
}

_MAC_APPS = {
    "notepad": "TextEdit",
    "text editor": "TextEdit",
    "textedit": "TextEdit",
    "calculator": "Calculator",
    "calc": "Calculator",
    "file explorer": "Finder",
    "explorer": "Finder",
    "files": "Finder",
    "finder": "Finder",
    "terminal": "Terminal",
    "settings": "System Settings",
    "system settings": "System Settings",
    "browser": "Safari",
    "safari": "Safari",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "firefox": "Firefox",
    "spotify": "Spotify",
    "music": "Music",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "outlook": "Microsoft Outlook",
    "mail": "Mail",
    "notes": "Notes",
    "messages": "Messages",
    "photos": "Photos",
    "discord": "Discord",
    "slack": "Slack",
    "steam": "Steam",
    "task manager": "Activity Monitor",
    "activity monitor": "Activity Monitor",
    "camera": "Photo Booth",
    "calendar": "Calendar",
}

_LINUX_APPS = {
    "notepad": ["gnome-text-editor", "gedit", "kate", "xed", "mousepad", "pluma", "featherpad"],
    "text editor": ["gnome-text-editor", "gedit", "kate", "xed", "mousepad", "pluma"],
    "calculator": ["gnome-calculator", "kcalc", "galculator", "mate-calc", "qalculate-gtk"],
    "calc": ["gnome-calculator", "kcalc", "galculator", "mate-calc"],
    "file explorer": ["nautilus", "dolphin", "nemo", "thunar", "pcmanfm", "caja"],
    "explorer": ["nautilus", "dolphin", "nemo", "thunar", "pcmanfm"],
    "files": ["nautilus", "dolphin", "nemo", "thunar", "pcmanfm"],
    "terminal": ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "kitty", "alacritty", "xterm"],
    "settings": ["gnome-control-center", "systemsettings", "xfce4-settings-manager"],
    "browser": ["xdg-open https://www.google.com"],
    "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    "google chrome": ["google-chrome", "google-chrome-stable", "chromium"],
    "firefox": ["firefox"],
    "edge": ["microsoft-edge"],
    "spotify": ["spotify"],
    "vscode": ["code"],
    "vs code": ["code"],
    "visual studio code": ["code"],
    "discord": ["discord"],
    "slack": ["slack"],
    "steam": ["steam"],
    "task manager": ["gnome-system-monitor", "plasma-systemmonitor", "ksysguard", "xfce4-taskmanager"],
    "word": ["libreoffice --writer"],
    "excel": ["libreoffice --calc"],
    "powerpoint": ["libreoffice --impress"],
}


def _stub_mouseinfo_if_needed() -> None:
    """pyautogui imports `mouseinfo`, which calls sys.exit() on Linux when tkinter is missing
    (python3-tk is not installed by default on Ubuntu). We never use MouseInfo, so stub it out."""
    if "mouseinfo" in sys.modules:
        return
    try:
        import tkinter  # noqa: F401
    except ImportError:
        import types

        stub = types.ModuleType("mouseinfo")
        stub.MouseInfoWindow = lambda *a, **k: None  # type: ignore[attr-defined]
        sys.modules["mouseinfo"] = stub


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url
    if "://" not in url and not url.startswith(("mailto:", "about:")):
        url = "https://" + url
    return url


def looks_like_url(text: str) -> bool:
    t = text.strip().lower()
    if " " in t:
        return False
    return t.startswith(("http://", "https://", "www.")) or (
        "." in t and t.rsplit(".", 1)[-1].isalpha() and 2 <= len(t.rsplit(".", 1)[-1]) <= 6
    )


def _popen(cmd: list[str] | str, shell: bool = False) -> None:
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if IS_WIN:
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(cmd, shell=shell, **kwargs)  # noqa: S603 - fixed catalogue / user-requested app names


class Automation:
    def __init__(self, config):
        self.config = config
        self._gui = None

    # -- pyautogui ------------------------------------------------------
    @property
    def gui(self):
        if self._gui is None:
            _stub_mouseinfo_if_needed()
            try:
                import pyautogui  # needs a display; imported lazily
            except SystemExit as exc:  # some pyautogui deps call sys.exit() instead of raising
                raise AutomationUnavailable(f"Mouse/keyboard control could not start: {exc}") from None
            except Exception as exc:
                hint = (
                    " Run the agent inside your desktop session (on Linux: an X11/Xorg session with DISPLAY set)."
                    if sys.platform.startswith("linux")
                    else ""
                )
                raise AutomationUnavailable(f"I can't reach the desktop to move the mouse ({type(exc).__name__}: {exc}).{hint}") from None

            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.02
            self._gui = pyautogui
        return self._gui

    def _require(self) -> None:
        if not self.config.allow_automation:
            raise AutomationDisabled("Mouse and keyboard control is turned off (DF_ALLOW_AUTOMATION=false).")

    def to_pixels(self, xn: float, yn: float) -> tuple[int, int]:
        w, h = self.gui.size()
        return min(max(int(round(xn * w)), 0), w - 1), min(max(int(round(yn * h)), 0), h - 1)

    def screen_size(self) -> tuple[int, int]:
        try:
            w, h = self.gui.size()
            return int(w), int(h)
        except Exception:  # no display
            return 0, 0

    def click(self, xn: float, yn: float, button: str = "left", clicks: int = 1) -> ActionOutcome:
        self._require()
        g = self.gui
        x, y = self.to_pixels(xn, yn)
        original = g.position()
        g.moveTo(x, y, duration=0.12)
        g.click(x=x, y=y, clicks=clicks, interval=0.08, button=button)
        if self.config.restore_mouse:
            time.sleep(0.05)
            g.moveTo(original[0], original[1])
        kind = "double-clicked" if clicks == 2 else ("right-clicked" if button == "right" else "clicked")
        return ActionOutcome(True, f"{kind} at ({x}, {y})")

    def scroll(self, direction: str, amount: int = 5, at: tuple[float, float] | None = None) -> ActionOutcome:
        self._require()
        g = self.gui
        amount = max(1, min(int(amount or 5), 50))
        original = g.position()
        if at is not None:
            g.moveTo(*self.to_pixels(*at))
        step = 120 if IS_WIN else 1  # Windows counts in wheel deltas
        if direction in ("up", "down"):
            g.scroll(step * amount * (1 if direction == "up" else -1))
        elif direction in ("left", "right"):
            if hasattr(g, "hscroll") and not IS_WIN:
                g.hscroll(amount * (-1 if direction == "left" else 1))
            else:
                g.keyDown("shift")
                try:
                    g.scroll(step * amount * (1 if direction == "left" else -1))
                finally:
                    g.keyUp("shift")
        else:
            return ActionOutcome(False, f"unknown scroll direction {direction!r}")
        if at is not None and self.config.restore_mouse:
            g.moveTo(original[0], original[1])
        return ActionOutcome(True, f"scrolled {direction} {amount}")

    def type_text(self, text: str, enter: bool = False) -> ActionOutcome:
        self._require()
        g = self.gui
        if text:
            if text.isascii():
                g.write(text, interval=0.012)
            else:
                self._paste(text)
        if enter:
            g.press("enter")
        return ActionOutcome(True, f"typed {len(text)} characters" + (" and pressed Enter" if enter else ""))

    def _paste(self, text: str) -> None:
        import pyperclip

        try:
            previous = pyperclip.paste()
        except Exception:
            previous = None
        pyperclip.copy(text)
        self.gui.hotkey("command" if IS_MAC else "ctrl", "v")
        time.sleep(0.15)
        if previous is not None:
            try:
                pyperclip.copy(previous)
            except Exception:
                pass

    def press_keys(self, keys: list[str] | str) -> ActionOutcome:
        self._require()
        names = normalize_keys(keys)
        if not names:
            return ActionOutcome(False, "no keys given")
        valid = set(self.gui.KEYBOARD_KEYS)
        bad = [k for k in names if k not in valid]
        if bad:
            return ActionOutcome(False, f"unknown key(s): {', '.join(bad)}")
        if len(names) == 1:
            self.gui.press(names[0])
        else:
            self.gui.hotkey(*names)
        return ActionOutcome(True, "pressed " + "+".join(names))

    # -- launching ------------------------------------------------------
    def open_url(self, url: str) -> ActionOutcome:
        url = normalize_url(url)
        if not url:
            return ActionOutcome(False, "empty URL")
        webbrowser.open(url, new=2)
        return ActionOutcome(True, f"opened {url}")

    def web_search_in_browser(self, query: str) -> ActionOutcome:
        template = self.config.search_url or "https://www.google.com/search?q={query}"
        url = template.replace("{query}", quote_plus(query))
        webbrowser.open(url, new=2)
        return ActionOutcome(True, f"searched the web for {query!r}")

    def open_app(self, name: str) -> ActionOutcome:
        raw = name.strip()
        key = raw.lower().removesuffix(" app").strip()
        if not key:
            return ActionOutcome(False, "no app name")
        if looks_like_url(key):
            return self.open_url(raw)
        try:
            if IS_WIN:
                ok = self._open_windows(key, raw)
            elif IS_MAC:
                ok = self._open_mac(key, raw)
            else:
                ok = self._open_linux(key, raw)
        except Exception as exc:  # launching is best-effort
            log.info("open_app %r failed: %s", raw, exc)
            ok = False
        if ok:
            return ActionOutcome(True, f"opened {raw}")
        if key in WEB_APPS:
            return self.open_url(WEB_APPS[key])
        return ActionOutcome(False, f"couldn't find an app called {raw!r} on this PC")

    def _open_windows(self, key: str, raw: str) -> bool:
        if key in WEB_APPS and key not in _WIN_APPS:
            return False
        for target in _WIN_APPS.get(key, [raw]):
            if target.startswith("http"):
                webbrowser.open(target, new=2)
                return True
            if target.endswith(":"):
                os.startfile(target)  # type: ignore[attr-defined]  # protocol handler, e.g. ms-settings:
                return True
            exe = shutil.which(target) or _win_app_path(target)
            if exe:
                _popen([exe])
                return True
        shortcut = _find_start_menu_shortcut(key)
        if shortcut:
            os.startfile(shortcut)  # type: ignore[attr-defined]
            return True
        return False

    def _open_mac(self, key: str, raw: str) -> bool:
        if key in WEB_APPS and key not in _MAC_APPS:
            return False
        app = _MAC_APPS.get(key, raw)
        result = subprocess.run(["open", "-a", app], capture_output=True, text=True, timeout=8)
        if result.returncode == 0:
            return True
        bundle = _find_mac_app(key)
        if bundle:
            return subprocess.run(["open", bundle], capture_output=True, timeout=8).returncode == 0
        return False

    def _open_linux(self, key: str, raw: str) -> bool:
        if key in WEB_APPS and key not in _LINUX_APPS:
            return False
        candidates = _LINUX_APPS.get(key, [key.replace(" ", "-"), key.replace(" ", "")])
        for cmd in candidates:
            parts = cmd.split()
            if shutil.which(parts[0]):
                _popen(parts)
                return True
        desktop = _find_desktop_file(key)
        if desktop:
            if shutil.which("gtk-launch"):
                _popen(["gtk-launch", os.path.basename(desktop)])
                return True
            if shutil.which("gio"):
                _popen(["gio", "launch", desktop])
                return True
        return False


# ---------------------------------------------------------------------------
# Installed-app discovery (so "open spotify" works without a hard-coded list)
# ---------------------------------------------------------------------------
def _win_app_path(name: str) -> str | None:
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:
        return None
    exe = name if name.lower().endswith(".exe") else f"{name}.exe"
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(root, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}") as k:
                value = winreg.QueryValue(k, None)
                if value:
                    return value.strip('"')
        except OSError:
            continue
    return None


def _best_match(key: str, names: dict[str, str]) -> str | None:
    """Pick the path whose display name equals, starts with, or contains the key."""
    key = key.lower()
    exact = [p for n, p in names.items() if n == key]
    if exact:
        return exact[0]
    starts = sorted((n, p) for n, p in names.items() if n.startswith(key))
    if starts:
        return min(starts, key=lambda np: len(np[0]))[1]
    contains = sorted((n, p) for n, p in names.items() if key in n)
    if contains:
        return min(contains, key=lambda np: len(np[0]))[1]
    return None


def _find_start_menu_shortcut(key: str) -> str | None:
    roots = [
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
    ]
    names: dict[str, str] = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.lower().endswith((".lnk", ".url")) and "uninstall" not in f.lower():
                    names.setdefault(os.path.splitext(f)[0].lower(), os.path.join(dirpath, f))
    return _best_match(key, names)


def _find_mac_app(key: str) -> str | None:
    names: dict[str, str] = {}
    for root in ("/Applications", "/System/Applications", "/System/Applications/Utilities", os.path.expanduser("~/Applications")):
        if os.path.isdir(root):
            for entry in os.listdir(root):
                if entry.endswith(".app"):
                    names.setdefault(entry[:-4].lower(), os.path.join(root, entry))
    return _best_match(key, names)


def _find_desktop_file(key: str) -> str | None:
    dirs = [
        os.path.expanduser("~/.local/share/applications"),
        "/usr/share/applications",
        "/usr/local/share/applications",
        "/var/lib/flatpak/exports/share/applications",
        os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
        "/var/lib/snapd/desktop/applications",
    ]
    names: dict[str, str] = {}
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".desktop"):
                continue
            path = os.path.join(d, f)
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    text = fh.read(4096)
            except OSError:
                continue
            if "NoDisplay=true" in text:
                continue
            for line in text.splitlines():
                if line.startswith("Name="):
                    names.setdefault(line[5:].strip().lower(), path)
                    break
            names.setdefault(f[:-8].lower(), path)
    return _best_match(key, names)
