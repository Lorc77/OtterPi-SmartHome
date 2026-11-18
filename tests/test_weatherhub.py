"""Tests für den WeatherHubReader (measurements_from_packet)."""

from datetime import datetime, timedelta, timezone

from weatherhub import WeatherHubReader
from weatherhub_gateway_decoder import BootPacket, GatewayPacket


def _make_packet(sensor_id, sensor_type, decoded_values):
    return GatewayPacket(
        gateway_timestamp=1000,
        sensor_id=sensor_id,
        sensor_type=sensor_type,
        decoded_values=decoded_values,
        raw_data=bytes(64),
    )


def test_measurements_from_packet_id01():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet(
        "017A5CD3FC1C",
        0x01,
        {
            "temperature_1": {"value": 23.4, "error": False, "overflow": False},
            "temperature_2": {"value": -25.1, "error": False, "overflow": False},
        },
    )

    measurements = reader.measurements_from_packet(packet)

    assert "weatherhub_017a5cd3fc1c.temperature_1" in measurements
    assert "weatherhub_017a5cd3fc1c.temperature_2" in measurements
    assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].value == 23.4
    assert measurements["weatherhub_017a5cd3fc1c.temperature_2"].value == -25.1
    assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].unit == "celsius"
    assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].validity == "valid"


def test_measurements_from_packet_id03():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet(
        "03469858AF14",
        0x03,
        {
            "temperature": {"value": 21.3, "error": False, "overflow": False},
            "humidity": {"value": 48.0, "error": False, "overflow": False},
        },
    )

    measurements = reader.measurements_from_packet(packet)

    assert "weatherhub_03469858af14.temperature" in measurements
    assert "weatherhub_03469858af14.humidity" in measurements
    assert measurements["weatherhub_03469858af14.temperature"].value == 21.3
    assert measurements["weatherhub_03469858af14.humidity"].value == 48.0
    assert measurements["weatherhub_03469858af14.humidity"].unit == "percent"


def test_measurements_from_packet_id0e():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet(
        "0E74A4597B54",
        0x0E,
        {
            "temperature": {"value": 16.4, "error": False, "overflow": False},
            "humidity": {"value": 70.0, "error": False, "overflow": False},
        },
    )

    measurements = reader.measurements_from_packet(packet)

    assert "weatherhub_0e74a4597b54.temperature" in measurements
    assert "weatherhub_0e74a4597b54.humidity" in measurements
    assert measurements["weatherhub_0e74a4597b54.temperature"].value == 16.4
    assert measurements["weatherhub_0e74a4597b54.humidity"].value == 70.0


def test_measurements_from_packet_id10():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet(
        "010203040506",
        0x10,
        {
            "contact": {"open": True, "time_unit": 0, "elapsed_value": 0},
        },
    )

    measurements = reader.measurements_from_packet(packet)

    # ID10 hat keine Measurements (nur contact_open als State)
    assert measurements == {}


def test_measurements_from_packet_skips_boot():
    reader = WeatherHubReader(stale_after_seconds=1800)
    boot = BootPacket(raw_data=bytes(15))

    measurements = reader.measurements_from_packet(boot)

    assert measurements == {}


def test_measurements_from_packet_skips_empty():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet("017A5CD3FC1C", 0x01, {})

    measurements = reader.measurements_from_packet(packet)

    assert measurements == {}


def test_measurements_from_packet_invalid():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet(
        "017A5CD3FC1C",
        0x01,
        {
            "temperature_1": {"value": None, "error": True, "overflow": False},
            "temperature_2": {"value": -25.1, "error": False, "overflow": False},
        },
    )

    measurements = reader.measurements_from_packet(packet)

    m = measurements["weatherhub_017a5cd3fc1c.temperature_1"]
    assert m.validity == "invalid"
    assert m.validity_reason == "sensor_error"
    assert m.value is None


def test_measurements_from_packet_overflow():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet(
        "017A5CD3FC1C",
        0x01,
        {
            "temperature_1": {"value": 23.4, "error": False, "overflow": True},
            "temperature_2": {"value": -25.1, "error": False, "overflow": False},
        },
    )

    measurements = reader.measurements_from_packet(packet)

    m = measurements["weatherhub_017a5cd3fc1c.temperature_1"]
    assert m.validity == "invalid"
    assert m.validity_reason == "overflow"


def test_measurements_from_packet_stale():
    reader = WeatherHubReader(stale_after_seconds=1800)
    packet = _make_packet(
        "017A5CD3FC1C",
        0x01,
        {
            "temperature_1": {"value": 23.4, "error": False, "overflow": False},
            "temperature_2": {"value": -25.1, "error": False, "overflow": False},
        },
    )

    # Erstes Paket → valid
    reader.update_from_packets([packet])
    measurements = reader.measurements_from_packet(packet)
    assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].validity == "valid"

    # Empfangszeit künstlich altern lassen
    old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    reader._reception_times["017A5CD3FC1C"] = old_time

    measurements = reader.measurements_from_packet(packet)
    assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].validity == "stale"
    assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].value == 23.4
