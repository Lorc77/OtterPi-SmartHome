"""Tests für das Dashboard."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from dashboard import (
    _device_measurement_keys,
    _render_climate_detail,
    _render_device_detail,
    _render_overview,
    _render_room_detail,
)
from dashboard_config import get_rooms
from dashboard_data import _device_current, _device_status, _room_climate, _series
from otterpi_store import BatchStore


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Legt eine Test-rooms.json an und setzt SMARTHOME_CONFIG_DIR."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    rooms = {
        "rooms": {
            "test_room": {
                "name": "Test Room",
                "icon": "🧪",
                "devices": [
                    {
                        "name": "Test ID01",
                        "key": "weatherhub_test01",
                        "type": "weatherhub_id01",
                    },
                    {
                        "name": "Test ID0E",
                        "key": "weatherhub_test0e",
                        "type": "weatherhub_id0e",
                    },
                    {
                        "name": "Test ID10",
                        "key": "weatherhub_test10",
                        "type": "weatherhub_id10",
                    },
                ],
                "weatherhub_climate": ["weatherhub_test03"],
            },
            "test_room_odd": {
                "name": "Test Room Odd",
                "icon": "🧪",
                "devices": [
                    {
                        "name": "Test ID01",
                        "key": "weatherhub_test01",
                        "type": "weatherhub_id01",
                    },
                ],
                "weatherhub_climate": [],
            },
            "test_room_even": {
                "name": "Test Room Even",
                "icon": "🧪",
                "devices": [
                    {
                        "name": "Test ID01",
                        "key": "weatherhub_test01",
                        "type": "weatherhub_id01",
                    },
                    {
                        "name": "Test ID0E",
                        "key": "weatherhub_test0e",
                        "type": "weatherhub_id0e",
                    },
                ],
                "weatherhub_climate": [],
            },
        }
    }
    (config_dir / "rooms.json").write_text(json.dumps(rooms), encoding="utf-8")
    monkeypatch.setenv("SMARTHOME_CONFIG_DIR", str(config_dir))
    return config_dir


# ---------------------------------------------------------------------------
# Fixtures & Helper
# ---------------------------------------------------------------------------


def _make_measurement(value, unit="celsius", validity="valid", measured_at=None):
    """Erzeugt ein Measurement-Dict wie es im Batch vorkommt."""
    return {
        "value": value,
        "unit": unit,
        "measured_at": measured_at or "2026-10-27T12:00:00+00:00",
        "validity": validity,
        "source": "weatherhub",
    }


def _make_batch(measurements=None, created_at=None, states=None):
    """Erzeugt einen Batch-Dict für Tests."""
    result = {
        "batch_id": "test-batch",
        "logger_id": "smarthome",
        "sequence": 0,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "measurements": measurements or {},
        "system": {
            "cpu": {"temperature_celsius": 45.0},
        },
        "memory": {
            "total_bytes": 1000,
            "used_bytes": 500,
        },
    }
    if states is not None:
        result["states"] = states
    return result


def _store_batches(tmp_path, batches):
    """Speichert Batches in einer SQLite-Datenbank."""
    store = BatchStore(tmp_path / "otter.db")
    with sqlite3.connect(store.path) as conn:
        for batch in batches:
            conn.execute(
                (
                    "INSERT INTO batches "
                    "(batch_id, logger_id, sequence, payload, created_at) "
                    "VALUES (?, ?, ?, ?, ?)"
                ),
                (
                    batch["batch_id"],
                    batch["logger_id"],
                    batch["sequence"],
                    json.dumps(batch),
                    batch.get("created_at", ""),
                ),
            )
    return store


@pytest.fixture
def sample_batches():
    """Erzeugt Beispiel-Batches mit generischen Dummy-Sensoren."""
    measurements = {
        # ID01 (2 Kanäle)
        "weatherhub_test01.temperature_1": _make_measurement(21.8),
        "weatherhub_test01.temperature_2": _make_measurement(-21.5),
        # ID03 (Raumklima)
        "weatherhub_test03.temperature": _make_measurement(21.3),
        "weatherhub_test03.humidity": _make_measurement(48.0, unit="percent"),
        # ID0E (Temp + Feuchte)
        "weatherhub_test0e.temperature": _make_measurement(16.4),
        "weatherhub_test0e.humidity": _make_measurement(70.0, unit="percent"),
    }
    return [_make_batch(measurements)]


# ---------------------------------------------------------------------------
# _room_climate
# ---------------------------------------------------------------------------


class TestRoomClimate:
    """Testet die Raumklima-Berechnung."""

    def test_room_climate_with_id03(self, sample_batches):
        """ID03 liefert Raumtemperatur und -feuchte."""
        room = get_rooms()["test_room"]
        climate = _room_climate(sample_batches, room)

        assert climate["temp"] == pytest.approx(21.55, abs=0.01)
        assert climate["hum"] == pytest.approx(48.0, abs=0.01)

    def test_room_climate_with_id01(self, sample_batches):
        """ID01-Sensoren fließen in die Raumtemperatur ein."""
        room = get_rooms()["test_room_odd"]
        climate = _room_climate(sample_batches, room)

        assert climate["temp"] == pytest.approx(21.8, abs=0.01)
        assert climate["hum"] is None

    def test_room_climate_ignores_id0e(self, sample_batches):
        """ID0E (DryAger) darf nicht in die Raumtemperatur einfließen."""
        room = get_rooms()["test_room"]
        climate = _room_climate(sample_batches, room)

        assert climate["temp"] == pytest.approx(21.55, abs=0.01)

    def test_room_climate_empty_batches(self):
        """Ohne Batches gibt es kein Raumklima."""
        room = get_rooms()["test_room"]
        climate = _room_climate([], room)

        assert climate["temp"] is None
        assert climate["hum"] is None

    def test_room_climate_missing_values(self):
        """Fehlende Messwerte werden ignoriert."""
        measurements = {
            "weatherhub_test01.temperature_1": _make_measurement(21.5),
            "weatherhub_test01.temperature_2": _make_measurement(4.5),
        }
        batches = [_make_batch(measurements)]
        room = get_rooms()["test_room_odd"]

        climate = _room_climate(batches, room)

        assert climate["temp"] == pytest.approx(21.5, abs=0.01)


# ---------------------------------------------------------------------------
# _device_current
# ---------------------------------------------------------------------------


class TestDeviceCurrent:
    """Testet die aktuellen Gerätewerte."""

    def test_id01_shows_temperature_2(self, sample_batches):
        """ID01-Sensoren zeigen nur temperature_2 (Gerätetemperatur)."""
        result = _device_current(sample_batches, "weatherhub_test01", "weatherhub_id01")

        assert result["temp"] == -21.5
        assert result["value"] == "-21.5 °C"
        assert result["hum"] == 0.0

    def test_id0e_shows_temperature_and_humidity(self, sample_batches):
        """ID0E zeigt temperature + humidity."""
        result = _device_current(sample_batches, "weatherhub_test0e", "weatherhub_id0e")

        assert result["temp"] == 16.4
        assert result["hum"] == 70.0
        assert result["value"] == "16.4 °C"

    def test_id03_shows_temperature_and_humidity(self, sample_batches):
        """ID03 zeigt temperature + humidity (nicht temperature_1)."""
        result = _device_current(sample_batches, "weatherhub_test03", "weatherhub_id03")

        assert result["temp"] == 21.3
        assert result["hum"] == 48.0
        assert result["value"] == "21.3 °C"

    def test_placeholder_returns_empty(self, sample_batches):
        """Platzhalter liefert keine Werte."""
        result = _device_current(sample_batches, "dryager", "placeholder")

        assert result["temp"] == 0.0
        assert result["value"] == "–"

    def test_id04_shows_temperature_and_humidity(self):
        """ID04 zeigt temperature + humidity."""
        measurements = {
            "weatherhub_test04.temperature": _make_measurement(21.3),
            "weatherhub_test04.humidity": _make_measurement(48.0, unit="percent"),
        }
        batches = [_make_batch(measurements)]
        result = _device_current(batches, "weatherhub_test04", "weatherhub_id04")

        assert result["temp"] == 21.3
        assert result["hum"] == 48.0
        assert result["value"] == "21.3 °C"

    def test_id10_returns_empty(self):
        """ID10 hat keine Measurements → leeres Result."""
        measurements = {}
        batches = [_make_batch(measurements)]
        result = _device_current(batches, "weatherhub_test10", "weatherhub_id10")

        assert result["temp"] == 0.0
        assert result["value"] == "–"


# ---------------------------------------------------------------------------
# _device_status
# ---------------------------------------------------------------------------


class TestDeviceStatus:
    """Testet die Status-Berechnung."""

    def test_status_valid(self, sample_batches):
        """Gültige Werte → status-ok."""
        assert _device_status(sample_batches, "weatherhub_test01", "weatherhub_id01") == "status-ok"
        assert _device_status(sample_batches, "weatherhub_test0e", "weatherhub_id0e") == "status-ok"

    def test_status_id03(self, sample_batches):
        """ID03 mit gültigen Werten → status-ok."""
        assert _device_status(sample_batches, "weatherhub_test03", "weatherhub_id03") == "status-ok"

    def test_status_invalid(self):
        """Invalid → status-critical."""
        measurements = {
            "weatherhub_test01.temperature_2": _make_measurement(None, validity="invalid"),
        }
        batches = [_make_batch(measurements)]
        assert _device_status(batches, "weatherhub_test01", "weatherhub_id01") == "status-critical"

    def test_status_stale(self):
        """Stale → status-warn."""
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        measurements = {
            "weatherhub_test01.temperature_2": _make_measurement(
                4.5, validity="stale", measured_at=old_time
            ),
        }
        batches = [_make_batch(measurements)]
        assert _device_status(batches, "weatherhub_test01", "weatherhub_id01") == "status-warn"

    def test_status_no_batches(self):
        """Ohne Batches → status-off."""
        assert _device_status([], "weatherhub_test01", "weatherhub_id01") == "status-off"

    def test_status_placeholder(self, sample_batches):
        """Platzhalter → status-off."""
        assert _device_status(sample_batches, "dryager", "placeholder") == "status-off"

    def test_status_id04(self):
        """ID04 mit gültigen Werten → status-ok."""
        measurements = {
            "weatherhub_test04.temperature": _make_measurement(21.3),
            "weatherhub_test04.humidity": _make_measurement(48.0, unit="percent"),
        }
        batches = [_make_batch(measurements)]
        assert _device_status(batches, "weatherhub_test04", "weatherhub_id04") == "status-ok"

    def test_status_id10_contact_open_with_alert_enabled(self, tmp_path, monkeypatch):
        """ID10 mit contact_open=True und Alert aktiviert → status-warn."""
        monkeypatch.setenv("SMARTHOME_CONFIG_DIR", str(tmp_path))
        (tmp_path / "alarm_limits.json").write_text(
            json.dumps(
                {
                    "sensors": {},
                    "states": {"weatherhub_test10.contact_open": {"enabled": True}},
                }
            ),
            encoding="utf-8",
        )
        from dashboard_data import _alarm_limits_cache

        _alarm_limits_cache["mtime"] = None
        _alarm_limits_cache["data"] = None

        batches = [
            _make_batch(
                {},
                states={"weatherhub_test10": {"contact_open": True}},
            )
        ]
        assert _device_status(batches, "weatherhub_test10", "weatherhub_id10") == "status-warn"

    def test_status_id10_contact_open_without_alert(self):
        """ID10 mit contact_open=True und Alert nicht aktiviert → status-ok."""
        batches = [
            _make_batch(
                {},
                states={"weatherhub_test10": {"contact_open": True}},
            )
        ]
        assert _device_status(batches, "weatherhub_test10", "weatherhub_id10") == "status-ok"

    def test_status_id10_contact_closed(self):
        """ID10 mit contact_open=False → status-ok."""
        batches = [
            _make_batch(
                {},
                states={"weatherhub_test10": {"contact_open": False}},
            )
        ]
        assert _device_status(batches, "weatherhub_test10", "weatherhub_id10") == "status-ok"


# ---------------------------------------------------------------------------
# _series
# ---------------------------------------------------------------------------


class TestSeries:
    """Testet die Messwert-Reihen-Extraktion."""

    def test_series_extracts_values(self):
        """Serie extrahiert nur Werte mit measured_at."""
        measurements = {
            "weatherhub_test01.temperature_2": _make_measurement(
                4.5, measured_at="2026-10-27T12:00:00+00:00"
            ),
        }
        batches = [_make_batch(measurements)]

        series = _series(batches, "weatherhub_test01.temperature_2")

        assert len(series) == 1
        assert series[0]["value"] == 4.5
        assert series[0]["label"] == "13:00"
        assert series[0]["date"] == "2026-10-27"

    def test_series_skips_missing_values(self):
        """Serie überspringt Measurements ohne Wert."""
        measurements = {
            "weatherhub_test01.temperature_2": _make_measurement(None, validity="unavailable"),
        }
        batches = [_make_batch(measurements)]

        series = _series(batches, "weatherhub_test01.temperature_2")

        assert series == []

    def test_series_multiple_batches(self):
        """Serie aus mehreren Batches in chronologischer Reihenfolge."""
        measurements_1 = {
            "weatherhub_test01.temperature_2": _make_measurement(
                4.5, measured_at="2026-10-27T10:00:00+00:00"
            ),
        }
        measurements_2 = {
            "weatherhub_test01.temperature_2": _make_measurement(
                5.0, measured_at="2026-10-27T11:00:00+00:00"
            ),
        }
        batches = [
            _make_batch(measurements_1, created_at="2026-10-27T10:00:00+00:00"),
            _make_batch(measurements_2, created_at="2026-10-27T11:00:00+00:00"),
        ]

        series = _series(batches, "weatherhub_test01.temperature_2")

        assert len(series) == 2
        assert series[0]["value"] == 4.5
        assert series[1]["value"] == 5.0


# ---------------------------------------------------------------------------
# _render_overview
# ---------------------------------------------------------------------------


class TestRenderOverview:
    """Testet die Übersichtsseite."""

    def test_overview_contains_room_climate(self, sample_batches, tmp_path):
        """Übersicht enthält Raumklima in der Raum-Kopfzeile."""
        store = _store_batches(tmp_path, sample_batches)

        html = _render_overview(store)

        assert "🌡️ 21.6 °C" in html
        assert "💧 48 %" in html

    def test_overview_contains_english_texts(self, sample_batches, tmp_path):
        """Übersicht enthält englische Texte."""
        store = _store_batches(tmp_path, sample_batches)

        html = _render_overview(store)

        assert "Last measurement" in html


# ---------------------------------------------------------------------------
# _render_room_detail
# ---------------------------------------------------------------------------


class TestRenderRoomDetail:
    """Testet die Raum-Detailseite."""

    def test_room_detail_contains_climate(self, sample_batches, tmp_path):
        """Detailseite enthält Raumklima im Subtitle."""
        store = _store_batches(tmp_path, sample_batches)

        html = _render_room_detail(store, "test_room")

        assert "🌡️ Room temperature: 21.6 °C" in html
        assert "💧 Relative Humidity: 48.0 %" in html

    def test_room_detail_contains_english_back_button(self, sample_batches, tmp_path):
        """Detailseite enthält englischen Back-Button."""
        store = _store_batches(tmp_path, sample_batches)

        html = _render_room_detail(store, "test_room")

        assert "← Back to Overview" in html

    def test_room_detail_odd_number_cards_full_width(self, sample_batches, tmp_path):
        """Letzte Kachel bei ungerader Anzahl auf voller Breite."""
        store = _store_batches(tmp_path, sample_batches)

        html = _render_room_detail(store, "test_room_odd")

        assert "device-card device-card-full" in html

    def test_room_detail_even_number_cards_no_full_width(self, sample_batches, tmp_path):
        """Bei gerader Anzahl keine volle Breite."""
        store = _store_batches(tmp_path, sample_batches)

        html = _render_room_detail(store, "test_room_even")

        assert "device-card device-card-full" not in html


class TestRenderClimateDetail:
    """Smoke-Tests für die Raumklima-Detailseite."""

    def test_climate_detail_renders(self, sample_batches, tmp_path):
        store = _store_batches(tmp_path, sample_batches)
        html = _render_climate_detail(store, "test_room")
        assert "Room Climate" in html
        assert "Average Temperature" in html

    def test_climate_detail_not_found(self, sample_batches, tmp_path):
        store = _store_batches(tmp_path, sample_batches)
        html = _render_climate_detail(store, "unknown")
        assert "Not Found" in html


class TestRenderDeviceDetail:
    """Smoke-Tests für die Geräte-Detailseite."""

    def test_device_detail_renders(self, sample_batches, tmp_path):
        store = _store_batches(tmp_path, sample_batches)
        html = _render_device_detail(store, "weatherhub_test01")
        assert "Statistics" in html
        assert "weatherhub_test01" in html

    def test_device_detail_not_found(self, sample_batches, tmp_path):
        store = _store_batches(tmp_path, sample_batches)
        html = _render_device_detail(store, "unknown")
        assert "Not Found" in html


def test_render_led_svg_on():
    from dashboard import _render_led_svg

    html = _render_led_svg(2)
    assert "led-on" in html
    assert "2%" in html


def test_render_led_svg_off():
    from dashboard import _render_led_svg

    html = _render_led_svg(0)
    assert "led-off" in html
    assert "0%" in html


def test_render_led_svg_none():
    from dashboard import _render_led_svg

    assert _render_led_svg(None) == ""


def test_render_chips():
    from dashboard import _render_chips

    html = _render_chips([("OK", "chip-ok"), ("Door open", "chip-info")])
    assert 'class="chip chip-ok"' in html
    assert "OK" in html
    assert "Door open" in html


class TestRenderOverviewStatus:
    def test_overview_shows_status_lamp(self, sample_batches, tmp_path):
        store = _store_batches(tmp_path, sample_batches)
        html = _render_overview(store)
        assert 'class="lamp status-ok"' in html
        assert "Last packet" in html

    def test_overview_shows_offline_status(self, tmp_path):
        old = (datetime.now(timezone.utc) - timedelta(minutes=61)).isoformat()
        batches = [_make_batch(created_at=old)]
        store = _store_batches(tmp_path, batches)
        html = _render_overview(store)
        assert "Gateway offline" in html
        assert "status-critical" in html


def test_status_text_critical():
    from dashboard import _status_text

    assert _status_text("status-critical") == "CRITICAL"
    assert _status_text("status-ok") == "OK"
    assert _status_text("status-warn") == "STALE"
    assert _status_text("status-off") == "OFFLINE"


def test_device_measurement_keys_id03():
    """ID03 liefert temperature/humidity, nicht temperature_1."""
    device = {"key": "weatherhub_test03", "type": "weatherhub_id03"}
    temp_key, hum_key = _device_measurement_keys(device)

    assert temp_key == "weatherhub_test03.temperature"
    assert hum_key == "weatherhub_test03.humidity"


def test_device_measurement_keys_id0e():
    """ID0E liefert temperature/humidity."""
    device = {"key": "weatherhub_test0e", "type": "weatherhub_id0e"}
    temp_key, hum_key = _device_measurement_keys(device)

    assert temp_key == "weatherhub_test0e.temperature"
    assert hum_key == "weatherhub_test0e.humidity"


def test_device_measurement_keys_id01():
    """ID01 liefert temperature_2 (Gerätetemperatur), keine Feuchte."""
    device = {"key": "weatherhub_test01", "type": "weatherhub_id01"}
    temp_key, hum_key = _device_measurement_keys(device)

    assert temp_key == "weatherhub_test01.temperature_2"
    assert hum_key is None


def test_device_measurement_keys_id04():
    """ID04 liefert temperature/humidity (wie ID03/ID0E)."""
    device = {"key": "weatherhub_test04", "type": "weatherhub_id04"}
    temp_key, hum_key = _device_measurement_keys(device)

    assert temp_key == "weatherhub_test04.temperature"
    assert hum_key == "weatherhub_test04.humidity"


def test_device_measurement_keys_id10():
    """ID10 hat keine Measurements."""
    device = {"key": "weatherhub_test10", "type": "weatherhub_id10"}
    temp_key, hum_key = _device_measurement_keys(device)

    assert temp_key is None
    assert hum_key is None
