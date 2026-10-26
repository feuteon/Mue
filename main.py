"""Point d'entrée de Mue.

    Mue.exe                       -> fenêtre de réglages
    Mue.exe --to png "C:\\a.jpg"   -> conversion (appelé par le menu clic droit)
    Mue.exe --install             -> ajoute le menu clic droit (utilisé par l'installeur)
    Mue.exe --uninstall           -> retire le menu
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _fix_std_streams() -> None:
    # En mode fenêtré (PyInstaller --noconsole), stdout/stderr valent None.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def _log_crash(exc: BaseException) -> None:
    import traceback
    from mue.settings import data_dir
    try:
        with open(data_dir() / "crash.log", "a", encoding="utf-8") as f:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=f)
    except OSError:
        pass


def make_app():
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Erweb.Mue")
        except Exception:
            pass
    app = QApplication(sys.argv)
    from mue import APP_NAME
    from mue.ui import theme
    from mue.ui.widgets import app_icon
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setFont(theme.font(9.5))
    app.setStyleSheet(theme.stylesheet())
    return app


def run_convert(target: str, paths: list[str]) -> int:
    from mue import ipc
    msg = {"target": target, "paths": [str(Path(p).resolve()) for p in paths]}
    try:
        server = ipc.deliver_or_serve(msg)
        if server is None:
            return 0  # une instance déjà ouverte s'en charge
    except OSError:
        server = None  # canal indisponible : on convertit quand même, en solo

    from mue import settings as settings_mod
    from mue.jobs import JobManager
    from mue.ui.progress_window import ProgressWindow
    app = make_app()
    s = settings_mod.get()
    manager = JobManager(s)
    win = ProgressWindow(manager)
    if server is not None:
        server.start(lambda m: manager.incoming.emit(m))
    manager.submit_message(msg)
    win.show()
    code = app.exec_()
    if server is not None:
        server.close()
    manager.shutdown()
    return code


def run_settings() -> int:
    from mue import settings as settings_mod
    from mue.ui.settings_window import SettingsWindow
    app = make_app()
    w = SettingsWindow(settings_mod.get())
    w.show()
    return app.exec_()


def main(argv: list[str]) -> int:
    _fix_std_streams()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    args = argv[1:]
    if args[:1] == ["--to"] and len(args) >= 3:
        return run_convert(args[1], args[2:])
    if args[:1] == ["--install"]:
        from mue import settings as settings_mod, shell_menu
        shell_menu.install(settings_mod.get())
        return 0
    if args[:1] == ["--uninstall"]:
        from mue import shell_menu
        shell_menu.uninstall()
        return 0
    return run_settings()


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except SystemExit:
        raise
    except BaseException as e:  # pragma: no cover
        _log_crash(e)
        raise
