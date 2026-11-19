"""Daten-/Rechenfunktionen für das Dashboard."""

import glob
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from dashboard_constants import BERLIN
from otterpi_store import BatchStore
from sensor_schemas import MEASUREMENT_DISPLAY_NAMES
from status import (
    _latest_batch_for_device,
    calculate_rate_of_change,
    check_limits,
    check_sensor_stale,
)


def _calculate_average_series(
    batches: list[dict],
    sensor_keys: list[tuple[str, str, str]],
    max_points: int = 500,
) -> list[dict]:
    """Berechnet eine Mittelwert-Reihe aus mehreren Sensoren pro Zeitpunkt.

    Bei mehr als ``max_points`` Punkten wird auf ``max_points``
    heruntergebrochen (Durchschnitt pro Bucket), analog zu ``_series``.
    """
    series = []

    for batch in batches:
        batch_time = batch.get("created_at", "")
        measurements = batch.get("measurements", {})

        values = []
        for _, _, measurement_key in sensor_keys:
            measurement = measurements.get(measurement_key, {})
            value = measurement.get("value")
            if value is not None:
                values.append(value)

        if not values:
            continue

        avg_value = sum(values) / len(values)

        dt = datetime.fromisoformat(batch_time)
        if dt.tzinfo is not None:
            offset = dt.utcoffset()
            if offset is not None and offset.total_seconds() == 0:
                dt = dt.astimezone(BERLIN)

        label = dt.strftime("%H:%M")
        date = dt.strftime("%Y-%m-%d")
        series.append({"label": label, "date": date, "value": avg_value})

    if len(series) > max_points:
        step = len(series) / max_points
        downsampled = []
        for i in range(max_points):
            start = int(i * step)
            end = int((i + 1) * step)
            chunk = series[start:end]
            if not chunk:
                continue
            avg = sum(p["value"] for p in chunk) / len(chunk)
            downsampled.append(
                {
                    "label": chunk[0]["label"],
                    "date": chunk[0]["date"],
                    "value": avg,
                }
            )
        series = downsampled

    return series


def _calculate_stats(
    temp_series: list[dict[str, Any]],
    hum_series: list[dict[str, Any]],
) -> dict[str, float]:
    """Berechnet Statistiken (Min/Max/Ø) für die Detailseiten."""
    stats = {
        "temp_min": 0.0,
        "temp_max": 0.0,
        "temp_avg": 0.0,
        "hum_min": 0.0,
        "hum_max": 0.0,
        "hum_avg": 0.0,
    }

    if temp_series:
        temp_values = [point["value"] for point in temp_series if point["value"] is not None]
        if temp_values:
            stats["temp_min"] = min(temp_values)
            stats["temp_max"] = max(temp_values)
            stats["temp_avg"] = sum(temp_values) / len(temp_values)

    if hum_series:
        hum_values = [point["value"] for point in hum_series if point["value"] is not None]
        if hum_values:
            stats["hum_min"] = min(hum_values)
            stats["hum_max"] = max(hum_values)
            stats["hum_avg"] = sum(hum_values) / len(hum_values)

    return stats


def _room_climate(batches: list[dict], room: dict) -> dict:
    """Berechnet Raumtemperatur und -feuchte aus den WeatherHub-Sensoren."""
    temps = []
    hums = []

    if not batches:
        return {"temp": None, "hum": None}

    for device in room["devices"]:
        if device.get("type") == "weatherhub_id01":
            key = device["key"]
            latest = _latest_batch_for_device(batches, key)
            measurements = latest.get("measurements", {})
            temp = measurements.get(f"{key}.temperature_1", {})
            if temp.get("value") is not None:
                temps.append(temp["value"])

    for sensor_key in room.get("weatherhub_climate", []):
        latest = _latest_batch_for_device(batches, sensor_key)
        measurements = latest.get("measurements", {})

        temp = measurements.get(f"{sensor_key}.temperature", {})
        if temp.get("value") is not None:
            temps.append(temp["value"])

        hum = measurements.get(f"{sensor_key}.humidity", {})
        if hum.get("value") is not None:
            hums.append(hum["value"])

    result = {"temp": None, "hum": None}

    if temps:
        result["temp"] = sum(temps) / len(temps)

    if hums:
        result["hum"] = sum(hums) / len(hums)

    return result


def _recent_batches(
    store: BatchStore,
    hours: int = 48,
    limit: Optional[int] = None,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """Liest die letzten Batches aus SQLite.

    Wenn ``start_date`` und ``end_date`` gesetzt sind (Custom-Range),
    wird nach diesem Bereich gefiltert. Sonst nach ``now - hours``.
    Filterung erfolgt per SQL nach ``created_at``.
    """
    if start_date and end_date:
        cutoff = start_date + "T00:00:00"
        until = (datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%dT00:00:00"
        )
        with sqlite3.connect(store.path) as conn:
            rows = conn.execute(
                "SELECT payload, received_at FROM batches "
                "WHERE created_at >= ? AND created_at < ? "
                "ORDER BY rowid ASC",
                (cutoff, until),
            ).fetchall()
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        if limit is None:
            limit = 5000
        with sqlite3.connect(store.path) as conn:
            rows = conn.execute(
                "SELECT payload, received_at FROM batches "
                "WHERE created_at >= ? "
                "ORDER BY rowid DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
        rows.reverse()

    batches = []
    for payload, received_at in rows:
        data = json.loads(payload)
        data["_received_at"] = received_at or data.get("created_at", "")
        batches.append(data)

    return batches


def _count_recent_batches(store: BatchStore, hours: int = 48) -> int:
    """Zählt die Batches der letzten ``hours`` Stunden (SQL COUNT)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(store.path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM batches WHERE created_at >= ?",
            (cutoff,),
        ).fetchone()
    return row[0] if row else 0


def _system_metrics() -> dict:
    """Liest CPU-Temperatur und Memory-Auslastung vom Host.

    Gibt None zurück, wenn die Werte nicht verfügbar sind
    (z. B. unter Windows bei Tests).
    """
    result = {"cpu_temp": None, "memory_used": None}

    # CPU-Temperatur (Raspberry Pi: thermal_zone0)
    for path in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        try:
            with open(path) as f:
                result["cpu_temp"] = int(f.read().strip()) / 1000.0
            break
        except (OSError, ValueError):
            continue

    # Memory
    try:
        meminfo = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, value = line.partition(":")
                meminfo[key.strip()] = int(value.strip().split()[0])
        total = meminfo.get("MemTotal")
        available = meminfo.get("MemAvailable")
        if total and available:
            result["memory_used"] = (total - available) / total * 100
    except (OSError, ValueError):
        pass

    return result


def _current_values(batches: list[dict]) -> dict:
    """Ermittelt die aktuellen Werte aus dem letzten Batch."""
    current = {
        "temp_101": 0.0,
        "hum_101": 0.0,
        "temp_102": 0.0,
        "hum_102": 0.0,
        "temp_freezer": 0.0,
        "temp_memmert_links": 0.0,
        "temp_memmert_rechts": 0.0,
        "last_batch": "–",
    }

    if not batches:
        return current

    latest = batches[-1]

    current["last_batch"] = (
        datetime.fromisoformat(latest["created_at"])
        .astimezone(BERLIN)
        .strftime("%d.%m.%Y %H:%M Uhr")
    )

    measurements = latest.get("measurements", {})

    temp_101 = measurements.get("atmoweb_101.temperature_1", {})
    hum_101 = measurements.get("atmoweb_101.humidity", {})
    temp_102 = measurements.get("atmoweb_102.temperature_1", {})
    hum_102 = measurements.get("atmoweb_102.humidity", {})
    temp_freezer = measurements.get("freezer.temperature", {})
    temp_memmert_links = measurements.get("memmert_ipp300_links.temperature", {})
    temp_memmert_rechts = measurements.get("memmert_ipp300_rechts.temperature", {})

    if temp_101.get("value") is not None:
        current["temp_101"] = temp_101["value"]
    if hum_101.get("value") is not None:
        current["hum_101"] = hum_101["value"]
    if temp_102.get("value") is not None:
        current["temp_102"] = temp_102["value"]
    if hum_102.get("value") is not None:
        current["hum_102"] = hum_102["value"]
    if temp_freezer.get("value") is not None:
        current["temp_freezer"] = temp_freezer["value"]
    if temp_memmert_links.get("value") is not None:
        current["temp_memmert_links"] = temp_memmert_links["value"]
    if temp_memmert_rechts.get("value") is not None:
        current["temp_memmert_rechts"] = temp_memmert_rechts["value"]

    return current


def _device_current(batches: list[dict], key: str, device_type: str = "atmoweb") -> dict:
    """Ermittelt aktuelle Werte + Status für ein Gerät."""
    result = {
        "temp": 0.0,
        "hum": 0.0,
        "value": "–",
        "status": "lamp-off",
    }

    if not batches:
        return result

    latest = _latest_batch_for_device(batches, key)
    measurements = latest.get("measurements", {})

    if device_type == "placeholder":
        return result

    if device_type in ("freezer", "memmert"):
        temp = measurements.get(f"{key}.temperature", {})
        if temp.get("value") is not None:
            result["temp"] = temp["value"]
            result["value"] = f"{temp['value']:.1f} °C"

        if result["temp"] != 0.0:
            result["status"] = "lamp-ok"

        return result

    if device_type == "weatherhub_id01":
        temp = measurements.get(f"{key}.temperature_2", {})
        if temp.get("value") is not None:
            result["temp"] = temp["value"]
            result["value"] = f"{temp['value']:.1f} °C"

        if result["temp"] != 0.0:
            result["status"] = "lamp-ok"

        return result

    if device_type == "weatherhub_id02":
        temp = measurements.get(f"{key}.temperature", {})
        if temp.get("value") is not None:
            result["temp"] = temp["value"]
            result["value"] = f"{temp['value']:.1f} °C"
        if result["temp"] != 0.0:
            result["status"] = "lamp-ok"
        return result

    if device_type in ("weatherhub_id0e", "weatherhub_id03", "weatherhub_id04"):
        temp = measurements.get(f"{key}.temperature", {})
        hum = measurements.get(f"{key}.humidity", {})

        if temp.get("value") is not None:
            result["temp"] = temp["value"]
            result["value"] = f"{temp['value']:.1f} °C"

        if hum.get("value") is not None:
            result["hum"] = hum["value"]

        if result["temp"] > 0 or result["hum"] > 0:
            result["status"] = "lamp-ok"

        return result

    if device_type == "weatherhub_id10":
        return result

    temp = measurements.get(f"{key}.temperature_1", {})
    hum = measurements.get(f"{key}.humidity", {})

    if temp.get("value") is not None:
        result["temp"] = temp["value"]
        result["value"] = f"{temp['value']:.1f} °C"

    if hum.get("value") is not None:
        result["hum"] = hum["value"]

    if result["temp"] > 0 or result["hum"] > 0:
        result["status"] = "lamp-ok"

    return result


def _device_status(batches: list[dict], key: str, device_type: str = "atmoweb") -> str:
    """Ermittelt den erweiterten Status für die Gerätekachel."""
    if not batches:
        return "status-off"

    if device_type == "placeholder":
        return "status-off"

    latest = _latest_batch_for_device(batches, key)
    measurements = latest.get("measurements", {})
    states = latest.get("states", {}).get(key, {})

    if states.get("alarms"):
        return "status-critical"

    limits = _device_limits(key)
    limit_status = _limit_status(measurements, limits, batches)
    if limit_status == "status-critical":
        return "status-critical"

    if device_type != "weatherhub_id10":
        system = _load_alarm_limits_cached().get("system", {})
        stale_after = system.get("stale_after_seconds", 1800)
        offline_after = system.get("offline_after_seconds", 43200)
        sensor_state = check_sensor_stale(batches, key, stale_after, offline_after)
        if sensor_state == "offline":
            return "status-off"
        if sensor_state == "stale":
            return "status-warn"

    if device_type == "weatherhub_id10":
        if not states:
            return "status-off"
        if states.get("battery_low"):
            return "status-warn"
        contact_rule = _load_alarm_limits_cached().get("states", {}).get(f"{key}.contact_open", {})
        if contact_rule.get("enabled") and states.get("contact_open"):
            return "status-warn"
        return "status-ok"

    if device_type in ("freezer", "memmert", "weatherhub_id01", "weatherhub_id02"):
        if device_type in ("freezer", "memmert", "weatherhub_id02"):
            measurement_key = f"{key}.temperature"
        elif device_type == "weatherhub_id01":
            measurement_key = f"{key}.temperature_2"
        else:
            measurement_key = f"{key}.temperature"

        temp = measurements.get(measurement_key, {})
        validity = temp.get("validity")

        if validity == "invalid":
            return "status-critical"
        if validity == "stale":
            return "status-warn"
        if validity == "valid":
            if states.get("battery_low"):
                return "status-warn"
            if limit_status == "status-warn":
                return "status-warn"
            return "status-ok"
        return "status-off"

    if device_type in ("weatherhub_id0e", "weatherhub_id03", "weatherhub_id04"):
        temp = measurements.get(f"{key}.temperature", {})
    else:
        temp = measurements.get(f"{key}.temperature_1", {})
    hum = measurements.get(f"{key}.humidity", {})
    validities = {temp.get("validity"), hum.get("validity")}

    if "invalid" in validities:
        return "status-critical"
    if validities <= {"valid", "stale"} and len(validities) == 1:
        if "stale" in validities:
            return "status-warn"
        if states.get("battery_low"):
            return "status-warn"
        if limit_status == "status-warn":
            return "status-warn"
        return "status-ok"
    if temp.get("value") is not None or hum.get("value") is not None:
        return "status-warn"
    return "status-off"


def _series(batches: list[dict], key: str, max_points: int = 500) -> list[dict]:
    """Extrahiert eine Messwert-Reihe aus den Batches.

    Bei mehr als ``max_points`` Punkten wird auf ``max_points``
    heruntergebrochen (Durchschnitt pro Bucket).
    """
    series = []
    for batch in batches:
        measurement = batch.get("measurements", {}).get(key, {})
        value = measurement.get("value")
        measured_at = measurement.get("measured_at")

        if value is not None and measured_at:
            dt = datetime.fromisoformat(measured_at)

            if dt.tzinfo is not None:
                offset = dt.utcoffset()
                if offset is not None and offset.total_seconds() == 0:
                    dt = dt.astimezone(BERLIN)

            label = dt.strftime("%H:%M")
            date = dt.strftime("%Y-%m-%d")
            series.append({"label": label, "date": date, "value": value})

    if len(series) > max_points:
        step = len(series) / max_points
        downsampled = []
        for i in range(max_points):
            start = int(i * step)
            end = int((i + 1) * step)
            chunk = series[start:end]
            if not chunk:
                continue
            avg = sum(p["value"] for p in chunk) / len(chunk)
            downsampled.append(
                {
                    "label": chunk[0]["label"],
                    "date": chunk[0]["date"],
                    "value": avg,
                }
            )
        series = downsampled

    return series


def _latest_batch(batches: list[dict]) -> dict:
    return batches[-1] if batches else {}


def _latest_device(batches: list[dict], device_key: str) -> dict:
    latest = _latest_batch(batches)
    return latest.get("device", {}).get(device_key, {})


_alarm_limits_cache = {"mtime": None, "data": None}


def _load_alarm_limits_cached() -> dict:
    """Lädt alarm_limits.json mit mtime-Cache."""
    config_dir = os.environ.get(
        "SMARTHOME_CONFIG_DIR",
        "/var/lib/otterpi-smarthome/config",
    )
    path = Path(config_dir) / "alarm_limits.json"
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _alarm_limits_cache["mtime"] == mtime and _alarm_limits_cache["data"] is not None:
        return _alarm_limits_cache["data"]
    try:
        from config_store import load_alarm_limits

        data = load_alarm_limits()
    except Exception:
        return {}
    _alarm_limits_cache["mtime"] = mtime
    _alarm_limits_cache["data"] = data
    return data


def _device_limits(device_key: str) -> dict:
    """Liest die Limits für ein Gerät aus alarm_limits.json.

    Gibt ein Dict ``{full_key: limits}`` zurück (z.B.
    ``{"atmoweb_101.temperature_1": {"warning_min": 22, ...}}``).
    Leeres Dict, wenn keine Limits gesetzt sind.
    """
    data = _load_alarm_limits_cached()
    sensors = data.get("sensors", {})
    result = {}
    for key, limits in sensors.items():
        if key.startswith(device_key + "."):
            result[key] = limits
    return result


def _limit_status(measurements: dict, limits: dict, batches: Optional[list[dict]] = None) -> str:
    """Prüft Limit-Verletzungen.

    Gibt ``"status-critical"``, ``"status-warn"`` oder ``""`` zurück.
    """
    rate_values = {}
    if batches is not None:
        for key, limit in limits.items():
            rate_limit = limit.get("rate_of_change_max_per_hour")
            if rate_limit is None:
                continue
            rate = calculate_rate_of_change(_rate_values(batches, key))
            if rate is not None:
                rate_values[key] = rate
    violations = check_limits(measurements, limits, rate_values, skip_stale=False)
    if any(v.severity == "critical" for v in violations):
        return "status-critical"
    if any(v.severity == "warning" for v in violations):
        return "status-warn"
    return ""


def _rate_values(batches: list[dict], measurement_key: str) -> list[tuple[str, float]]:
    """Extrahiert (created_at, value)-Tupel für ein Measurement."""
    values = []
    for batch in batches:
        measurement = batch.get("measurements", {}).get(measurement_key, {})
        value = measurement.get("value")
        created_at = batch.get("created_at")
        if value is not None and created_at:
            values.append((created_at, value))
    return values


_ALARM_LABELS = {
    "temperature_below_low_alarm": "Undertemperature",
    "temperature_above_high_alarm": "Overtemperature",
    "ac_power_failure": "Power failure",
    "control_probe_fault": "Control probe fault",
    "microprocessor_fault": "Microprocessor fault",
    "heat_exchanger_fault": "Heat exchanger fault",
    "hot_condenser": "Hot condenser",
}


def _primary_measurement(measurements: dict, key: str, device_type: str) -> dict:
    if device_type in (
        "freezer",
        "memmert",
        "weatherhub_id0e",
        "weatherhub_id02",
        "weatherhub_id03",
        "weatherhub_id04",
    ):
        return measurements.get(f"{key}.temperature", {})
    if device_type == "weatherhub_id01":
        return measurements.get(f"{key}.temperature_2", {})
    if device_type == "weatherhub_id10":
        return {}
    return measurements.get(f"{key}.temperature_1", {})


def _invalid_reason(measurements: dict, key: str, device_type: str) -> Optional[str]:
    return _primary_measurement(measurements, key, device_type).get("validity_reason")


def _stale_measurement(measurements: dict, key: str) -> Optional[dict]:
    """Liefert das erste stale Measurement für ein Gerät."""
    for k, m in measurements.items():
        if k.startswith(f"{key}.") and m.get("validity") == "stale":
            return m
    return None


def _stale_age(measurement: dict) -> Optional[str]:
    """Liefert das Alter eines stale Measurements."""
    measured_at = measurement.get("measured_at")
    if not measured_at:
        return None
    dt = datetime.fromisoformat(measured_at)
    age_seconds = (datetime.now(timezone.utc) - dt).total_seconds()
    minutes = int(age_seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h"


def _contact_events(states: dict) -> list[dict]:
    """Extrahiert die Kontakt-Ereignisse aus den States."""
    events = []
    for suffix, label in (
        ("", "Current"),
        ("_previous", "Previous"),
        ("_previous_1", "Previous 1"),
        ("_previous_2", "Previous 2"),
    ):
        open_key = f"contact{suffix}_open"
        since_key = f"contact{suffix}_since"
        if open_key in states:
            events.append(
                {
                    "label": label,
                    "open": states[open_key],
                    "since": states.get(since_key),
                }
            )
    events.sort(key=lambda e: e["since"] or 0, reverse=True)
    return events


def _device_chips(
    batches: list[dict], key: str, device_type: str = "atmoweb"
) -> list[tuple[str, str]]:
    """Liefert die Chips (Text, CSS-Klasse) für ein Gerät."""
    if not batches or device_type == "placeholder":
        return []

    latest = _latest_batch_for_device(batches, key)
    measurements = latest.get("measurements", {})
    states = latest.get("states", {}).get(key, {})
    operation = latest.get("operation", {}).get(key, {})
    chips: list[tuple[str, str]] = []

    # 1) Limit-Chips: pro Measurement nur der höchste (crit > warning)
    limits = _device_limits(key)
    rate_values = {}
    for limit_key, limit in limits.items():
        rate_limit = limit.get("rate_of_change_max_per_hour")
        if rate_limit is None:
            continue
        rate = calculate_rate_of_change(_rate_values(batches, limit_key))
        if rate is not None:
            rate_values[limit_key] = rate

    violations = check_limits(measurements, limits, rate_values, skip_stale=False)
    violations_by_key = {}
    for v in violations:
        violations_by_key.setdefault(v.key, []).append(v)

    limit_critical_added = False
    for limit_key in limits:
        key_violations = violations_by_key.get(limit_key, [])
        if not key_violations:
            continue
        measurement_name = limit_key.split(".", 1)[1]
        display_name = MEASUREMENT_DISPLAY_NAMES.get(measurement_name, measurement_name)
        minmax = [v for v in key_violations if v.rule != "rate_of_change"]
        if minmax:
            v = minmax[0]
            direction = "below" if v.rule.endswith("_min") else "above"
            if v.severity == "critical":
                chips.append((f"⛔ {display_name} {direction} limit", "chip-critical"))
                limit_critical_added = True
            else:
                chips.append((f"⚠ {display_name} {direction} limit", "chip-warn"))
        for v in key_violations:
            if v.rule == "rate_of_change":
                chips.append((f"⚠ {display_name} rate of change above limit", "chip-warn"))

    # 2) Alarm-Chips
    alarms = states.get("alarms") or []
    for alarm in alarms:
        label = _ALARM_LABELS.get(alarm, alarm)
        chips.append((f"🚨 Alarm: {label}", "chip-critical"))

    # 3) Status-Chips (invalid, OK, Offline)
    status = _device_status(batches, key, device_type)
    if status == "status-critical" and not alarms and not limit_critical_added:
        reason = _invalid_reason(measurements, key, device_type)
        if reason == "overflow":
            chips.append(("⛔ Sensor overflow", "chip-critical"))
        elif reason == "sensor_error":
            chips.append(("⛔ Sensor error", "chip-critical"))
        else:
            chips.append(("⛔ Invalid", "chip-critical"))
    elif status == "status-ok":
        chips.append(("OK", "chip-ok"))
    elif status == "status-off":
        chips.append(("Offline", "chip-off"))

    # 4) Immer sichtbare Warnungen (stale, battery low)
    if states.get("battery_low"):
        chips.append(("⚠ Battery low", "chip-warn"))
    stale = _stale_measurement(measurements, key)
    if stale is not None:
        age = _stale_age(stale)
        if age is not None:
            chips.append((f"⚠ No data for {age}", "chip-warn"))
        else:
            chips.append(("⚠ Stale", "chip-warn"))

    # 5) State-Chips
    if states.get("water_contact"):
        chips.append(("Water contact", "chip-warn"))
    if device_type == "weatherhub_id10" and "contact_open" in states:
        contact_rule = _load_alarm_limits_cached().get("states", {}).get(f"{key}.contact_open", {})
        if states["contact_open"]:
            since = states.get("contact_since")
            if since:
                minutes = int((datetime.now(timezone.utc).timestamp() - since) / 60)
                label = f"Contact open (since {minutes} min)"
            else:
                label = "Contact open"
            if contact_rule.get("enabled"):
                chips.append((f"⚠ {label}", "chip-warn"))
            else:
                chips.append((label, "chip-info"))
        else:
            chips.append(("Contact closed", "chip-info"))

    if states.get("door_open"):
        chips.append(("Door open", "chip-info"))
    if states.get("door_locked"):
        chips.append(("Door locked", "chip-info"))
    if states.get("defrost"):
        chips.append(("Defrost", "chip-info"))
    if "flap" in states:
        chips.append((f"Flap {states['flap']:.0f}%", "chip-info"))
    if "mode" in operation:
        chips.append((f"Mode: {operation['mode']}", "chip-info"))
    if "operation_mode" in states:
        mode = "local" if states["operation_mode"] == 0 else "remote"
        chips.append((f"Mode: {mode}", "chip-info"))

    return chips


def _led_value(batches: list[dict], key: str) -> Optional[float]:
    if not batches:
        return None
    latest = _latest_batch_for_device(batches, key)
    states = latest.get("states", {}).get(key, {})
    lights = states.get("lights", {})
    if isinstance(lights, dict) and "led" in lights:
        return lights["led"]
    return None
