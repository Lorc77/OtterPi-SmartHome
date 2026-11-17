"""Konfiguration für das Dashboard – Sensor-Zuordnung und Raumnamen.

Lädt die Raum-/Gerätekonfiguration aus rooms.json (OTTERPI_CONFIG_DIR).
Fällt auf _DEFAULT_ROOMS zurück, wenn die Datei fehlt oder ungültig ist.

Deployment-Hinweis:
    Nach Änderungen an rooms.json ist kein Neustart nötig –
    get_rooms() liest die Datei bei Änderung (mtime) neu.
"""

import json
import os
import threading
from pathlib import Path

_DEFAULT_ROOMS = {}

_lock = threading.Lock()
_cache = {"path": None, "mtime": None, "rooms": None}


def _rooms_path() -> Path:
    config_dir = os.environ.get("OTTERPI_CONFIG_DIR", "/var/lib/loggerpi-otterpi/config")
    return Path(config_dir) / "rooms.json"


def get_rooms() -> dict:
    """Liefert die aktuelle Raum-/Gerätekonfiguration.

    Liest rooms.json bei Änderung (mtime) neu. Fällt auf _DEFAULT_ROOMS
    zurück, wenn die Datei fehlt oder ungültig ist.
    """
    path = _rooms_path()

    with _lock:
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            return _DEFAULT_ROOMS

        if _cache["path"] == path and _cache["mtime"] == mtime and _cache["rooms"] is not None:
            return _cache["rooms"]

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rooms = data["rooms"]
            if not isinstance(rooms, dict):
                raise ValueError("rooms must be an object")
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            if _cache["path"] == path and _cache["rooms"] is not None:
                return _cache["rooms"]
            return _DEFAULT_ROOMS

        _cache["path"] = path
        _cache["mtime"] = mtime
        _cache["rooms"] = rooms
        return rooms
