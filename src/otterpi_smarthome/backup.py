#!/usr/bin/env python3
"""Backup der OtterPi-Datenbanken auf den NAS (SQL-Dump, CIFS-sicher).

Erstellt tägliche Backups von ``smarthome.sqlite3`` und ``alerts.sqlite3``
als SQL-Dump auf dem NAS (CIFS-Mount unter ``/mnt/otterbox``).

Warum SQL-Dump statt ``.sqlite3``-Kopie: SQLite kann auf CIFS nicht
zuverlässig schreiben (``disk I/O error`` durch fehlendes Locking).
Ein SQL-Dump ist reiner Text und damit CIFS-kompatibel – ohne lokales
Temp-File (kein SD-Verschleiß) und ohne RAM-Puffer.

Restore::

    python3 -c "import sqlite3; c=sqlite3.connect('restored.sqlite3'); \\
                c.executescript(open('batches_2026-11-15.sql').read())"

Vor dem Backup wird geprüft, ob der NAS gemountet und beschreibbar ist.
Wenn nicht, wird kein Backup geschrieben (kein Fallback auf die SD-Karte).

Rotation: Backups älter als ``RETENTION_DAYS`` Tage werden gelöscht.

Optional: IPv64.net-Push-Check (Erfolg/Fehler) über
``OTTERPI_BACKUP_HEALTHCHECK_URL``.
"""

import logging
import os
import sqlite3
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

LOGGER = logging.getLogger(__name__)

NAS_MOUNT = Path("/mnt/otterbox")
BACKUP_DIR = NAS_MOUNT / "OtterPi" / "backups_otterpi-smarthome"
DB_DIR = Path("/var/lib/otterpi-smarthome")
RETENTION_DAYS = 7

HEALTHCHECK_URL = os.environ.get("SMARTHOME_BACKUP_HEALTHCHECK_URL", "")


def _nas_ready() -> bool:
    """Prüft, ob der NAS gemountet und beschreibbar ist."""
    if not os.path.ismount(NAS_MOUNT):
        LOGGER.error("NAS not mounted at %s", NAS_MOUNT)
        return False
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        LOGGER.error("Cannot create backup dir %s: %s", BACKUP_DIR, exc)
        return False
    test_file = BACKUP_DIR / ".write_test"
    try:
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        return True
    except OSError as exc:
        LOGGER.error("NAS not writable at %s: %s", BACKUP_DIR, exc)
        return False


def _backup_database(src: Path, dst: Path) -> None:
    """Schreibt einen SQL-Dump der Datenbank direkt auf den NAS.

    ``iterdump()`` liefert Zeile für Zeile – kein lokales Temp-File,
    kein RAM-Puffer, reiner Text-Write auf CIFS.
    """
    src_conn = sqlite3.connect(src)
    try:
        user_version = src_conn.execute("PRAGMA user_version").fetchone()[0]
        with open(dst, "w", encoding="utf-8") as f:
            for line in src_conn.iterdump():
                f.write(line)
                f.write("\n")
            if user_version:
                f.write(f"PRAGMA user_version = {user_version};\n")
    finally:
        src_conn.close()


def _rotate(directory: Path, prefix: str, retention_days: int) -> None:
    """Löscht Backups älter als retention_days."""
    cutoff = datetime.now() - timedelta(days=retention_days)
    for path in directory.glob(f"{prefix}_*.sql"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                path.unlink()
                LOGGER.info("Deleted old backup: %s", path)
            except OSError as exc:
                LOGGER.warning("Failed to delete %s: %s", path, exc)


def _ping_healthcheck(status: str = "up", message: str = "") -> None:
    """Sendet einen Push an IPv64.net (optional)."""
    if not HEALTHCHECK_URL:
        return
    url = HEALTHCHECK_URL
    if status != "up":
        url += f"&status={status}"
        if message:
            url += f"&msg={urllib.parse.quote(message)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            if response.status != 200:
                LOGGER.warning("Healthcheck returned HTTP %s", response.status)
    except Exception as exc:
        LOGGER.warning("Healthcheck failed: %s", exc)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not _nas_ready():
        _ping_healthcheck("down", "NAS not ready")
        return 1

    date = datetime.now().strftime("%Y-%m-%d")

    for name in ("smarthome", "alerts"):
        src = DB_DIR / f"{name}.sqlite3"
        if not src.exists():
            LOGGER.warning("Database not found: %s", src)
            continue
        dst = BACKUP_DIR / f"{name}_{date}.sql"
        try:
            _backup_database(src, dst)
            LOGGER.info("Backed up %s to %s", src, dst)
        except Exception as exc:
            LOGGER.error("Failed to backup %s: %s", src, exc)
            _ping_healthcheck("down", f"Backup failed: {name}")
            return 1

    _rotate(BACKUP_DIR, "smarthome", RETENTION_DAYS)
    _rotate(BACKUP_DIR, "alerts", RETENTION_DAYS)

    LOGGER.info("Backup complete.")
    _ping_healthcheck("up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
