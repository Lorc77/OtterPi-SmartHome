"""Gemeinsame Heartbeat-/Offline-Status-Logik für Admin und Dashboard."""

from datetime import datetime, timezone
from typing import Optional


def load_offline_thresholds(system_config: Optional[dict] = None) -> tuple[int, int]:
    """Liefert (warning_seconds, critical_seconds) für die Offline-Erkennung.

    Wenn ``system_config`` übergeben wird, werden die Werte daraus gelesen.
    Sonst wird ``alarm_limits.json`` geladen.
    """
    if system_config is None:
        try:
            from config_store import load_alarm_limits

            data = load_alarm_limits()
        except Exception:
            return (1800, 3600)
        system_config = data.get("system", {}) or {}
    return (
        system_config.get("gateway_offline_warning_seconds", 1800),
        system_config.get("gateway_offline_critical_seconds", 3600),
    )


def offline_status(
    last_received_at: Optional[str],
    warning_seconds: int = 1800,
    critical_seconds: int = 3600,
) -> tuple[str, str]:
    """Liefert (CSS-Klasse, Text) für die Statusanzeige im Header.

    - ``status-off``: noch kein Paket empfangen oder ungültiger Zeitstempel
    - ``status-ok``: letztes Paket innerhalb der Warnschwelle
    - ``status-warn``: letztes Paket zwischen Warn- und Kritisch-Schwelle
    - ``status-critical``: letztes Paket älter als die Kritisch-Schwelle
    """
    if not last_received_at:
        return ("status-off", "No packet received yet")

    try:
        last_dt = datetime.fromisoformat(last_received_at)
    except ValueError:
        return ("status-off", "Invalid timestamp")

    age_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
    minutes = int(age_seconds // 60)

    if age_seconds >= critical_seconds:
        return ("status-critical", f"Gateway offline for {minutes} min")
    if age_seconds >= warning_seconds:
        return ("status-warn", f"Last packet {minutes} min ago")
    return ("status-ok", f"Last packet {minutes} min ago")
