"""Gemeinsame Status-/Violation-Logik für Alert-Engine und Dashboard."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


def calculate_rate_of_change(
    values: list[tuple[str, float]],
) -> Optional[float]:
    """Berechnet die Rate of Change (pro Stunde) aus (created_at, value)-Tupeln.

    Gibt ``None`` zurück, wenn weniger als zwei Werte vorliegen oder der
    Zeitabstand null ist.
    """
    if len(values) < 2:
        return None
    first_time, first_value = values[0]
    last_time, last_value = values[-1]
    dt = datetime.fromisoformat(last_time) - datetime.fromisoformat(first_time)
    hours = dt.total_seconds() / 3600
    if hours <= 0:
        return None
    return (last_value - first_value) / hours


@dataclass(frozen=True)
class LimitViolation:
    key: str
    rule: str  # "critical_max", "warning_min", "rate_of_change", ...
    severity: str  # "critical", "warning"
    value: float
    threshold: float
    unit: str


def check_limits(
    measurements: dict,
    limits: dict,
    rate_values: Optional[dict] = None,
    *,
    skip_stale: bool = True,
) -> list:
    """Prüft Grenzwerte und Rate-of-Change. Gibt alle Violations zurück.

    ``rate_values`` ist ein optionales Dict ``{sensor_key: rate}``. Wird es
    nicht übergeben, wird Rate-of-Change nicht geprüft.

    ``skip_stale``: Wenn ``True`` (Default), werden ``stale``-Measurements
    übersprungen (Alert-Engine-Verhalten). Wenn ``False``, werden sie geprüft
    (Dashboard-Verhalten).
    """
    rate_values = rate_values or {}
    violations = []
    for key, limit in limits.items():
        if not limit.get("enabled", True):
            continue
        measurement = measurements.get(key)
        if measurement is None:
            continue
        value = measurement.get("value")
        validity = measurement.get("validity")
        if validity == "invalid":
            continue
        if skip_stale and validity == "stale":
            continue
        if value is None:
            continue
        unit = measurement.get("unit", "")
        for rule, threshold, severity in (
            ("critical_min", limit.get("critical_min"), "critical"),
            ("critical_max", limit.get("critical_max"), "critical"),
            ("warning_min", limit.get("warning_min"), "warning"),
            ("warning_max", limit.get("warning_max"), "warning"),
        ):
            if threshold is None:
                continue
            if rule.endswith("_min") and value < threshold:
                violations.append(
                    LimitViolation(
                        key=key,
                        rule=rule,
                        severity=severity,
                        value=value,
                        threshold=threshold,
                        unit=unit,
                    )
                )
            elif rule.endswith("_max") and value > threshold:
                violations.append(
                    LimitViolation(
                        key=key,
                        rule=rule,
                        severity=severity,
                        value=value,
                        threshold=threshold,
                        unit=unit,
                    )
                )
        rate_limit = limit.get("rate_of_change_max_per_hour")
        if rate_limit is not None:
            rate = rate_values.get(key)
            if rate is not None and abs(rate) > rate_limit:
                violations.append(
                    LimitViolation(
                        key=key,
                        rule="rate_of_change",
                        severity="warning",
                        value=rate,
                        threshold=rate_limit,
                        unit=unit,
                    )
                )
    return violations


@dataclass(frozen=True)
class DeviceViolation:
    device_key: str
    rule: str  # "stale", "invalid"
    severity: str
    reason: Optional[str]


def check_stale_invalid(
    measurements: dict,
    limits: dict,
    device_config: Optional[dict] = None,
) -> list:
    """Prüft stale/invalid pro Gerät. Gibt alle Violations zurück.

    Ein Gerät wird über den Teil vor dem ersten ``.`` im ``sensor_key``
    identifiziert. Pro Gerät wird maximal eine Violation zurückgegeben
    (invalid vor stale).
    """
    device_config = device_config or {}
    device_states = {}
    for sensor_key, limit in limits.items():
        if not limit.get("enabled", True):
            continue
        measurement = measurements.get(sensor_key)
        if measurement is None:
            continue
        validity = measurement.get("validity")
        validity_reason = measurement.get("validity_reason")
        device_key = sensor_key.split(".")[0]
        if device_key not in device_states:
            device_states[device_key] = {
                "stale": False,
                "invalid": False,
                "reason": None,
            }
        if validity == "invalid":
            device_states[device_key]["invalid"] = True
            device_states[device_key]["reason"] = validity_reason
        elif validity == "stale":
            device_states[device_key]["stale"] = True

    violations = []
    for device_key, state in device_states.items():
        device_rule = device_config.get(device_key, {})
        if state["invalid"] and device_rule.get("invalid_enabled", True):
            violations.append(
                DeviceViolation(
                    device_key=device_key,
                    rule="invalid",
                    severity="critical",
                    reason=state["reason"],
                )
            )
        elif state["stale"] and device_rule.get("stale_enabled", True):
            violations.append(
                DeviceViolation(
                    device_key=device_key,
                    rule="stale",
                    severity="warning",
                    reason=None,
                )
            )
    return violations


@dataclass(frozen=True)
class StateViolation:
    key: str
    rule: str  # "alarm", "battery_low", "door_open", "contact_open"
    severity: str
    value: object


def check_states(
    batch_states: dict,
    rules: dict,
) -> list:
    """Prüft States. Gibt alle Violations zurück.

    ``batch_states`` ist das ``states``-Dict aus dem Batch
    (``{device_key: {state_name: value}}``).
    ``rules`` ist die ``states``-Sektion aus ``alarm_limits.json``
    (``{state_key: {enabled: bool}}``).

    Behandelt nur die vier Alert-Trigger-States: ``alarms``, ``battery_low``,
    ``door_open``, ``contact_open``. Info-States (``door_locked``, ``defrost``,
    ``flap``, ``mode``, ``operation_mode``) sind keine Violations.
    """
    violations = []
    for state_key, rule in rules.items():
        if not rule.get("enabled", True):
            continue
        device_key, _, state_name = state_key.partition(".")
        device_states = batch_states.get(device_key, {})
        value = device_states.get(state_name)

        if state_name == "alarms" and isinstance(value, list):
            for alarm in value:
                violations.append(
                    StateViolation(
                        key=state_key,
                        rule="alarm",
                        severity="critical",
                        value=alarm,
                    )
                )
        elif state_name == "battery_low" and value is True:
            violations.append(
                StateViolation(
                    key=state_key,
                    rule="battery_low",
                    severity="warning",
                    value=True,
                )
            )
        elif state_name == "door_open" and value is True:
            violations.append(
                StateViolation(
                    key=state_key,
                    rule="door_open",
                    severity="warning",
                    value=True,
                )
            )
        elif state_name == "contact_open" and value is True:
            violations.append(
                StateViolation(
                    key=state_key,
                    rule="contact_open",
                    severity="warning",
                    value=True,
                )
            )
    return violations


def _latest_batch_for_device(batches: list[dict], key: str) -> dict:
    """Findet den letzten Batch, der Measurements oder States für ``key`` enthält."""
    for batch in reversed(batches):
        measurements = batch.get("measurements", {})
        states = batch.get("states", {})
        if any(k.startswith(f"{key}.") for k in measurements) or key in states:
            return batch
    return {}


def check_sensor_stale(
    batches: list[dict],
    key: str,
    stale_after: int,
    offline_after: int,
) -> str:
    """Liefert 'ok', 'stale' oder 'offline' für einen Sensor."""
    latest = _latest_batch_for_device(batches, key)
    created_at = latest.get("created_at")
    if not created_at:
        return "offline"
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(created_at)).total_seconds()
    if age > offline_after:
        return "offline"
    if age > stale_after:
        return "stale"
    return "ok"
