"""Instance unique.

Quand on sélectionne 30 fichiers puis « Convertir vers > PNG », Windows lance Mue 30 fois
(une fois par fichier). Le premier processus devient « serveur » (un named pipe), affiche
la fenêtre et convertit ; les 29 autres lui envoient leur fichier puis quittent aussitôt
(sans même charger Qt). Résultat : une seule fenêtre, une seule file d'attente."""

from __future__ import annotations

import getpass
import json
import os
import sys
import threading
import time
from multiprocessing.connection import Client, Listener
from typing import Callable

from .settings import cache_dir

IS_WIN = sys.platform == "win32"


def _address() -> tuple[str, str]:
    user = "".join(c for c in (getpass.getuser() or "user") if c.isalnum()) or "user"
    if IS_WIN:
        return rf"\\.\pipe\Mue-{user}", "AF_PIPE"
    return str(cache_dir() / f"mue-{user}.sock"), "AF_UNIX"


ADDRESS, FAMILY = _address()


def send(msg: dict) -> bool:
    """Envoie un message à l'instance principale. False s'il n'y en a pas."""
    try:
        conn = Client(ADDRESS, family=FAMILY)
    except (FileNotFoundError, ConnectionRefusedError):
        if not IS_WIN and os.path.exists(ADDRESS):  # socket orpheline (dev sous Linux)
            try:
                os.unlink(ADDRESS)
            except OSError:
                pass
        return False
    except OSError:
        return False
    try:
        conn.send_bytes(json.dumps(msg).encode("utf-8"))
        return True
    except OSError:
        return False
    finally:
        conn.close()


class Server:
    def __init__(self) -> None:
        # Échoue (PermissionError / OSError) si une autre instance a déjà créé le pipe.
        self._listener = Listener(ADDRESS, family=FAMILY)
        self._handler: Callable[[dict], None] | None = None

    def start(self, handler: Callable[[dict], None]) -> None:
        self._handler = handler
        threading.Thread(target=self._loop, name="mue-ipc", daemon=True).start()

    def _loop(self) -> None:
        while True:
            try:
                conn = self._listener.accept()
            except OSError:
                return
            try:
                data = conn.recv_bytes(1 << 20)
                msg = json.loads(data.decode("utf-8"))
                if isinstance(msg, dict) and self._handler:
                    self._handler(msg)
            except (OSError, EOFError, ValueError):
                pass
            finally:
                conn.close()

    def close(self) -> None:
        try:
            self._listener.close()
        except OSError:
            pass


def deliver_or_serve(msg: dict, wait: float = 6.0) -> Server | None:
    """Renvoie None si le message a été remis à une instance existante,
    sinon un Server : on est l'instance principale (et le message reste à traiter)."""
    deadline = time.monotonic() + wait
    while True:
        if send(msg):
            return None
        try:
            return Server()
        except OSError:
            # Une autre instance vient de naître à l'instant : on réessaie de lui parler.
            if time.monotonic() > deadline:
                raise
            time.sleep(0.03)
