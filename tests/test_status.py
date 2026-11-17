"""Tests für die gemeinsame Status-/Violation-Logik."""

from status import (
    calculate_rate_of_change,
    check_limits,
    check_stale_invalid,
    check_states,
)


class TestCalculateRateOfChange:
    def test_empty(self):
        assert calculate_rate_of_change([]) is None

    def test_single_value(self):
        assert calculate_rate_of_change([("2026-11-16T10:00:00+00:00", 20.0)]) is None

    def test_two_values(self):
        values = [
            ("2026-11-16T10:00:00+00:00", 20.0),
            ("2026-11-16T11:00:00+00:00", 22.0),
        ]
        assert calculate_rate_of_change(values) == 2.0

    def test_negative_rate(self):
        values = [
            ("2026-11-16T10:00:00+00:00", 22.0),
            ("2026-11-16T11:00:00+00:00", 20.0),
        ]
        assert calculate_rate_of_change(values) == -2.0

    def test_zero_hours(self):
        values = [
            ("2026-11-16T10:00:00+00:00", 20.0),
            ("2026-11-16T10:00:00+00:00", 22.0),
        ]
        assert calculate_rate_of_change(values) is None

    def test_multiple_values_uses_first_and_last(self):
        values = [
            ("2026-11-16T10:00:00+00:00", 20.0),
            ("2026-11-16T10:30:00+00:00", 21.0),
            ("2026-11-16T11:00:00+00:00", 22.0),
        ]
        assert calculate_rate_of_change(values) == 2.0


def _measurement(value, unit="celsius", validity="valid", validity_reason=None):
    result = {
        "value": value,
        "unit": unit,
        "validity": validity,
    }
    if validity_reason is not None:
        result["validity_reason"] = validity_reason
    return result


class TestCheckLimits:
    def test_empty_limits(self):
        assert check_limits({}, {}) == []

    def test_disabled_limit(self):
        measurements = {"sensor.temperature": _measurement(30.0)}
        limits = {"sensor.temperature": {"critical_max": 28.0, "enabled": False}}
        assert check_limits(measurements, limits) == []

    def test_missing_measurement(self):
        limits = {"sensor.temperature": {"critical_max": 28.0}}
        assert check_limits({}, limits) == []

    def test_value_none(self):
        measurements = {"sensor.temperature": _measurement(None, validity="unavailable")}
        limits = {"sensor.temperature": {"critical_max": 28.0}}
        assert check_limits(measurements, limits) == []

    def test_invalid_skipped(self):
        measurements = {"sensor.temperature": _measurement(None, validity="invalid")}
        limits = {"sensor.temperature": {"critical_max": 28.0}}
        assert check_limits(measurements, limits) == []

    def test_stale_skipped_by_default(self):
        measurements = {"sensor.temperature": _measurement(30.0, validity="stale")}
        limits = {"sensor.temperature": {"critical_max": 28.0}}
        assert check_limits(measurements, limits) == []

    def test_stale_checked_when_skip_stale_false(self):
        measurements = {"sensor.temperature": _measurement(30.0, validity="stale")}
        limits = {"sensor.temperature": {"critical_max": 28.0}}
        violations = check_limits(measurements, limits, skip_stale=False)
        assert len(violations) == 1
        assert violations[0].rule == "critical_max"

    def test_critical_max(self):
        measurements = {"sensor.temperature": _measurement(30.0)}
        limits = {"sensor.temperature": {"critical_max": 28.0}}
        violations = check_limits(measurements, limits)
        assert len(violations) == 1
        assert violations[0].rule == "critical_max"
        assert violations[0].severity == "critical"
        assert violations[0].value == 30.0
        assert violations[0].threshold == 28.0
        assert violations[0].unit == "celsius"

    def test_critical_min(self):
        measurements = {"sensor.temperature": _measurement(15.0)}
        limits = {"sensor.temperature": {"critical_min": 18.0}}
        violations = check_limits(measurements, limits)
        assert len(violations) == 1
        assert violations[0].rule == "critical_min"
        assert violations[0].severity == "critical"

    def test_warning_max(self):
        measurements = {"sensor.temperature": _measurement(24.0)}
        limits = {"sensor.temperature": {"warning_max": 23.0}}
        violations = check_limits(measurements, limits)
        assert len(violations) == 1
        assert violations[0].rule == "warning_max"
        assert violations[0].severity == "warning"

    def test_warning_min(self):
        measurements = {"sensor.temperature": _measurement(19.0)}
        limits = {"sensor.temperature": {"warning_min": 20.0}}
        violations = check_limits(measurements, limits)
        assert len(violations) == 1
        assert violations[0].rule == "warning_min"
        assert violations[0].severity == "warning"

    def test_no_violation(self):
        measurements = {"sensor.temperature": _measurement(22.0)}
        limits = {"sensor.temperature": {"critical_max": 28.0, "warning_max": 23.0}}
        assert check_limits(measurements, limits) == []

    def test_rate_of_change(self):
        measurements = {"sensor.temperature": _measurement(22.0)}
        limits = {"sensor.temperature": {"rate_of_change_max_per_hour": 2.0}}
        rate_values = {"sensor.temperature": 3.0}
        violations = check_limits(measurements, limits, rate_values)
        assert len(violations) == 1
        assert violations[0].rule == "rate_of_change"
        assert violations[0].severity == "warning"
        assert violations[0].value == 3.0
        assert violations[0].threshold == 2.0

    def test_rate_of_change_no_violation(self):
        measurements = {"sensor.temperature": _measurement(22.0)}
        limits = {"sensor.temperature": {"rate_of_change_max_per_hour": 2.0}}
        rate_values = {"sensor.temperature": 1.0}
        assert check_limits(measurements, limits, rate_values) == []

    def test_rate_of_change_missing_rate(self):
        measurements = {"sensor.temperature": _measurement(22.0)}
        limits = {"sensor.temperature": {"rate_of_change_max_per_hour": 2.0}}
        assert check_limits(measurements, limits) == []

    def test_multiple_violations(self):
        measurements = {"sensor.temperature": _measurement(30.0)}
        limits = {"sensor.temperature": {"critical_max": 28.0, "warning_max": 23.0}}
        violations = check_limits(measurements, limits)
        assert len(violations) == 2
        rules = {v.rule for v in violations}
        assert rules == {"critical_max", "warning_max"}


class TestCheckStaleInvalid:
    def test_empty(self):
        assert check_stale_invalid({}, {}) == []

    def test_disabled_limit(self):
        measurements = {"sensor.temperature": _measurement(30.0, validity="invalid")}
        limits = {"sensor.temperature": {"enabled": False}}
        assert check_stale_invalid(measurements, limits) == []

    def test_missing_measurement(self):
        limits = {"sensor.temperature": {}}
        assert check_stale_invalid({}, limits) == []

    def test_valid_measurement(self):
        measurements = {"sensor.temperature": _measurement(22.0)}
        limits = {"sensor.temperature": {}}
        assert check_stale_invalid(measurements, limits) == []

    def test_invalid(self):
        measurements = {
            "sensor.temperature": _measurement(None, validity="invalid", validity_reason="overflow")
        }
        limits = {"sensor.temperature": {}}
        violations = check_stale_invalid(measurements, limits)
        assert len(violations) == 1
        assert violations[0].device_key == "sensor"
        assert violations[0].rule == "invalid"
        assert violations[0].severity == "critical"
        assert violations[0].reason == "overflow"

    def test_stale(self):
        measurements = {"sensor.temperature": _measurement(22.0, validity="stale")}
        limits = {"sensor.temperature": {}}
        violations = check_stale_invalid(measurements, limits)
        assert len(violations) == 1
        assert violations[0].device_key == "sensor"
        assert violations[0].rule == "stale"
        assert violations[0].severity == "warning"

    def test_invalid_takes_precedence_over_stale(self):
        measurements = {
            "sensor.temperature_1": _measurement(None, validity="invalid"),
            "sensor.temperature_2": _measurement(22.0, validity="stale"),
        }
        limits = {"sensor.temperature_1": {}, "sensor.temperature_2": {}}
        violations = check_stale_invalid(measurements, limits)
        assert len(violations) == 1
        assert violations[0].rule == "invalid"

    def test_invalid_disabled(self):
        measurements = {"sensor.temperature": _measurement(None, validity="invalid")}
        limits = {"sensor.temperature": {}}
        device_config = {"sensor": {"invalid_enabled": False}}
        assert check_stale_invalid(measurements, limits, device_config) == []

    def test_stale_disabled(self):
        measurements = {"sensor.temperature": _measurement(22.0, validity="stale")}
        limits = {"sensor.temperature": {}}
        device_config = {"sensor": {"stale_enabled": False}}
        assert check_stale_invalid(measurements, limits, device_config) == []

    def test_one_violation_per_device(self):
        measurements = {
            "sensor.temperature_1": _measurement(22.0, validity="stale"),
            "sensor.temperature_2": _measurement(23.0, validity="stale"),
        }
        limits = {"sensor.temperature_1": {}, "sensor.temperature_2": {}}
        violations = check_stale_invalid(measurements, limits)
        assert len(violations) == 1
        assert violations[0].device_key == "sensor"

    def test_multiple_devices(self):
        measurements = {
            "sensor_a.temperature": _measurement(22.0, validity="stale"),
            "sensor_b.temperature": _measurement(None, validity="invalid"),
        }
        limits = {"sensor_a.temperature": {}, "sensor_b.temperature": {}}
        violations = check_stale_invalid(measurements, limits)
        assert len(violations) == 2
        rules = {v.rule for v in violations}
        assert rules == {"stale", "invalid"}


class TestCheckStates:
    def test_empty(self):
        assert check_states({}, {}) == []

    def test_disabled_rule(self):
        batch_states = {"freezer": {"alarms": ["ac_power_failure"]}}
        rules = {"freezer.alarms": {"enabled": False}}
        assert check_states(batch_states, rules) == []

    def test_missing_state(self):
        rules = {"freezer.alarms": {"enabled": True}}
        assert check_states({}, rules) == []

    def test_alarms_empty(self):
        batch_states = {"freezer": {"alarms": []}}
        rules = {"freezer.alarms": {"enabled": True}}
        assert check_states(batch_states, rules) == []

    def test_alarms_one(self):
        batch_states = {"freezer": {"alarms": ["ac_power_failure"]}}
        rules = {"freezer.alarms": {"enabled": True}}
        violations = check_states(batch_states, rules)
        assert len(violations) == 1
        assert violations[0].key == "freezer.alarms"
        assert violations[0].rule == "alarm"
        assert violations[0].severity == "critical"
        assert violations[0].value == "ac_power_failure"

    def test_alarms_multiple(self):
        batch_states = {"freezer": {"alarms": ["ac_power_failure", "control_probe_fault"]}}
        rules = {"freezer.alarms": {"enabled": True}}
        violations = check_states(batch_states, rules)
        assert len(violations) == 2
        values = {v.value for v in violations}
        assert values == {"ac_power_failure", "control_probe_fault"}

    def test_battery_low_true(self):
        batch_states = {"weatherhub_015f9410f3eb": {"battery_low": True}}
        rules = {"weatherhub_015f9410f3eb.battery_low": {"enabled": True}}
        violations = check_states(batch_states, rules)
        assert len(violations) == 1
        assert violations[0].rule == "battery_low"
        assert violations[0].severity == "warning"

    def test_battery_low_false(self):
        batch_states = {"weatherhub_015f9410f3eb": {"battery_low": False}}
        rules = {"weatherhub_015f9410f3eb.battery_low": {"enabled": True}}
        assert check_states(batch_states, rules) == []

    def test_door_open_true(self):
        batch_states = {"atmoweb_101": {"door_open": True}}
        rules = {"atmoweb_101.door_open": {"enabled": True}}
        violations = check_states(batch_states, rules)
        assert len(violations) == 1
        assert violations[0].rule == "door_open"
        assert violations[0].severity == "warning"

    def test_door_open_false(self):
        batch_states = {"atmoweb_101": {"door_open": False}}
        rules = {"atmoweb_101.door_open": {"enabled": True}}
        assert check_states(batch_states, rules) == []

    def test_contact_open_true(self):
        batch_states = {"weatherhub_010203040506": {"contact_open": True}}
        rules = {"weatherhub_010203040506.contact_open": {"enabled": True}}
        violations = check_states(batch_states, rules)
        assert len(violations) == 1
        assert violations[0].rule == "contact_open"
        assert violations[0].severity == "warning"

    def test_contact_open_false(self):
        batch_states = {"weatherhub_010203040506": {"contact_open": False}}
        rules = {"weatherhub_010203040506.contact_open": {"enabled": True}}
        assert check_states(batch_states, rules) == []

    def test_info_states_ignored(self):
        batch_states = {
            "atmoweb_101": {
                "door_locked": True,
                "defrost": True,
                "flap": 50,
            }
        }
        rules = {
            "atmoweb_101.door_locked": {"enabled": True},
            "atmoweb_101.defrost": {"enabled": True},
            "atmoweb_101.flap": {"enabled": True},
        }
        assert check_states(batch_states, rules) == []
