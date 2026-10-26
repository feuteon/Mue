"""Intégration au clic droit de l'Explorateur Windows (registre, HKCU uniquement :
pas besoin d'être administrateur, et rien n'est touché pour les autres comptes).

Pour chaque extension connue on crée :
  HKCU\\Software\\Classes\\SystemFileAssociations\\.jpg\\shell\\Mue.ConvertTo
      MUIVerb = "Convertir vers"     SubCommands = ""     Icon = Mue.exe
      shell\\01_png  -> MUIVerb "PNG",  command = "Mue.exe" --to png "%1"
      shell\\02_webp -> …
SystemFileAssociations ajoute l'entrée sans toucher au programme qui ouvre le fichier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .formats import EXT_TO_CATEGORY, SEP
from .settings import Settings

try:
    import winreg  # type: ignore
except ImportError:  # hors Windows (tests) : on peut injecter un faux winreg
    winreg = None  # type: ignore

KEY_NAME = "Mue.ConvertTo"
BASE = r"Software\Classes\SystemFileAssociations"
MENU_TITLE = "Convertir vers"
ECF_SEPARATORBEFORE = 0x20
CLASSIC_MENU_KEY = r"Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"


def _reg():
    if winreg is None:
        raise RuntimeError("Le registre Windows n'est pas disponible sur ce système.")
    return winreg


# --- Commande lancée par l'Explorateur -------------------------------------------------

def exe_path() -> Path:
    return Path(sys.executable).resolve()


def command_prefix() -> str:
    if getattr(sys, "frozen", False):
        return f'"{exe_path()}"'
    # mode développement : python(w).exe main.py
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    main = Path(__file__).resolve().parents[1] / "main.py"
    return f'"{pyw if pyw.exists() else py}" "{main}"'


def icon_value() -> str:
    if getattr(sys, "frozen", False):
        return f'"{exe_path()}",0'
    ico = Path(__file__).resolve().parents[1] / "assets" / "mue.ico"
    return f'"{ico}"'


# --- Utilitaires registre --------------------------------------------------------------

def _set(path: str, values: dict) -> None:
    r = _reg()
    with r.CreateKeyEx(r.HKEY_CURRENT_USER, path, 0, r.KEY_WRITE) as k:
        for name, val in values.items():
            if isinstance(val, int):
                r.SetValueEx(k, name, 0, r.REG_DWORD, val)
            else:
                r.SetValueEx(k, name, 0, r.REG_SZ, val)


def _delete_tree(path: str) -> bool:
    r = _reg()
    try:
        with r.OpenKey(r.HKEY_CURRENT_USER, path, 0, r.KEY_READ | r.KEY_WRITE) as k:
            while True:
                try:
                    child = r.EnumKey(k, 0)
                except OSError:
                    break
                _delete_tree(f"{path}\\{child}")
        r.DeleteKey(r.HKEY_CURRENT_USER, path)
        return True
    except FileNotFoundError:
        return False


def _exists(path: str) -> bool:
    r = _reg()
    try:
        with r.OpenKey(r.HKEY_CURRENT_USER, path):
            return True
    except OSError:
        return False


def _read(path: str, name: str = "") -> str | None:
    r = _reg()
    try:
        with r.OpenKey(r.HKEY_CURRENT_USER, path) as k:
            return r.QueryValueEx(k, name)[0]
    except OSError:
        return None


def _notify_shell() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)  # SHCNE_ASSOCCHANGED
        except Exception:
            pass


# --- API ---------------------------------------------------------------------------------

def install(settings: Settings) -> int:
    """(Ré)installe le menu pour toutes les extensions. Retourne le nombre d'extensions."""
    from .converter import menu_for_ext
    uninstall(notify=False)
    prefix = command_prefix()
    count = 0
    for ext in sorted(EXT_TO_CATEGORY):
        items = menu_for_ext(ext, settings)
        if not items:
            continue
        root = f"{BASE}\\.{ext}\\shell\\{KEY_NAME}"
        _set(root, {"MUIVerb": MENU_TITLE, "SubCommands": "", "Icon": icon_value(),
                    "MultiSelectModel": "Player"})
        n, sep_next = 0, False
        for it in items:
            if it is SEP:
                sep_next = True
                continue
            target, label = it
            n += 1
            sub = f"{root}\\shell\\{n:02d}_{target}"
            vals = {"MUIVerb": label, "MultiSelectModel": "Player"}
            if sep_next:
                vals["CommandFlags"] = ECF_SEPARATORBEFORE
                sep_next = False
            _set(sub, vals)
            _set(sub + "\\command", {"": f'{prefix} --to {target} "%1"'})
        sub = f"{root}\\shell\\99_settings"
        _set(sub, {"MUIVerb": "Réglages de Mue…", "CommandFlags": ECF_SEPARATORBEFORE})
        _set(sub + "\\command", {"": f"{prefix} --settings"})
        count += 1
    _notify_shell()
    return count


def uninstall(notify: bool = True) -> int:
    r = _reg()
    removed = 0
    try:
        with r.OpenKey(r.HKEY_CURRENT_USER, BASE) as k:
            names, i = [], 0
            while True:
                try:
                    names.append(r.EnumKey(k, i))
                    i += 1
                except OSError:
                    break
    except OSError:
        names = []
    for name in names:
        if _delete_tree(f"{BASE}\\{name}\\shell\\{KEY_NAME}"):
            removed += 1
    if notify:
        _notify_shell()
    return removed


def status() -> str:
    """'ok' | 'absent' | 'stale' (installé mais pointe vers un autre emplacement de Mue)"""
    cmd = _read(f"{BASE}\\.png\\shell\\{KEY_NAME}\\shell\\01_jpg\\command") or \
        _read(f"{BASE}\\.jpg\\shell\\{KEY_NAME}\\shell\\01_png\\command")
    if cmd is None:
        return "absent"
    return "ok" if cmd.startswith(command_prefix()) else "stale"


# --- Windows 11 : menu contextuel classique ----------------------------------------------

def is_windows_11() -> bool:
    return sys.platform == "win32" and sys.getwindowsversion().build >= 22000


def classic_menu_enabled() -> bool:
    return _exists(CLASSIC_MENU_KEY + r"\InprocServer32")


def set_classic_menu(enabled: bool) -> None:
    if enabled:
        _set(CLASSIC_MENU_KEY + r"\InprocServer32", {"": ""})
    else:
        _delete_tree(CLASSIC_MENU_KEY)


def restart_explorer() -> None:
    from .engines import NO_WINDOW
    subprocess.run(["taskkill", "/f", "/im", "explorer.exe"], creationflags=NO_WINDOW,
                   capture_output=True)
    subprocess.Popen(["explorer.exe"], creationflags=0)
