"""Tests fÃ¼r die WeatherHub-Stale-Logik."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from weatherhub import WeatherHubReader
from weatherhub_gateway_decoder import GatewayPacket


class TestWeatherHubStaleLogic:
    """Testet die Stale-Logik des WeatherHubReaders."""

    def _make_gateway_packet(
        self,
        sensor_id: str,
        sensor_type: int,
        decoded_values: Dict[str, Any],
        gateway_timestamp: int = 1000,
    ) -> GatewayPacket:
        """Erzeugt ein GatewayPacket mit den gegebenen Werten."""
        return GatewayPacket(
            gateway_timestamp=gateway_timestamp,
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            decoded_values=decoded_values,
            raw_data=bytes(64),
        )

    def _make_id01_packet(self, sensor_id: str, temp1: float, temp2: float) -> GatewayPacket:
        """Erzeugt ein ID01-Paket mit zwei Temperaturen."""
        return self._make_gateway_packet(
            sensor_id=sensor_id,
            sensor_type=0x01,
            decoded_values={
                "temperature_1": {"value": temp1, "error": False, "overflow": False},
                "temperature_2": {"value": temp2, "error": False, "overflow": False},
            },
        )

    def test_fresh_sensor_is_valid(self) -> None:
        """Ein Sensor, der gerade gesendet hat, ist valid."""
        reader = WeatherHubReader()
        packet = self._make_id01_packet("017A5CD3FC1C", 23.4, -25.1)

        reader.update_from_packets([packet])
        measurements = reader.read_measurements()

        assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].validity == "valid"
        assert measurements["weatherhub_017a5cd3fc1c.temperature_2"].validity == "valid"
        assert measurements["weatherhub_017a5cd3fc1c.temperature_2"].value == -25.1

    def test_sensor_never_received_is_unavailable(self) -> None:
        """Ein Sensor, der nie empfangen wurde, hat keine Measurements."""
        reader = WeatherHubReader()

        # Kein Packet empfangen
        measurements = reader.read_measurements()

        assert measurements == {}

    def test_stale_within_threshold_is_valid(self) -> None:
        """Ein Sensor innerhalb des Schwellenwerts bleibt valid."""
        reader = WeatherHubReader()
        packet = self._make_id01_packet("017A5CD3FC1C", 23.4, -25.1)

        reader.update_from_packets([packet])

        # Simuliere, dass nur 10 Minuten vergangen sind (< 1800 Sekunden)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        reader._reception_times["017A5CD3FC1C"] = recent_time.isoformat()

        measurements = reader.read_measurements()
        assert measurements["weatherhub_017a5cd3fc1c.temperature_1"].validity == "valid"
        assert measurements["weatherhub_017a5cd3fc1c.temperature_2"].validity == "valid"

    def test_read_state_battery_low(self) -> None:
        reader = WeatherHubReader()
        packet = self._make_id01_packet("017A5CD3FC1C", 23.4, -25.1)
        packet = GatewayPacket(
            gateway_timestamp=packet.gateway_timestamp,
            sensor_id=packet.sensor_id,
            sensor_type=packet.sensor_type,
            decoded_values={
                **packet.decoded_values,
                "status": {"battery_low": True, "event_transmission": False, "counter": 1},
            },
            raw_data=packet.raw_data,
        )

        reader.update_from_packets([packet], client_ip="141.51.190.121")
        states = reader.read_state()

        assert states["weatherhub_017a5cd3fc1c"]["battery_low"] is True

    def test_read_device_info(self) -> None:
        reader = WeatherHubReader()
        packet = self._make_id01_packet("017A5CD3FC1C", 23.4, -25.1)

        reader.update_from_packets([packet], client_ip="141.51.190.121")
        info = reader.read_device_info()

        assert info["weatherhub_017a5cd3fc1c"]["sensor_id"] == "017A5CD3FC1C"
        assert info["weatherhub_017a5cd3fc1c"]["sensor_type"] == 1
        assert info["weatherhub_017a5cd3fc1c"]["gateway_ip"] == "141.51.190.121"
        assert info["weatherhub_017a5cd3fc1c"]["gateway_timestamp"] == 1000

    def test_overflow_sets_validity_reason(self) -> None:
        reader = WeatherHubReader()
        packet = self._make_gateway_packet(
            sensor_id="017A5CD3FC1C",
            sensor_type=0x01,
            decoded_values={
                "temperature_1": {"value": 23.4, "error": False, "overflow": True},
                "temperature_2": {"value": -25.1, "error": False, "overflow": False},
            },
        )

        reader.update_from_packets([packet])
        measurements = reader.read_measurements()

        m = measurements["weatherhub_017a5cd3fc1c.temperature_1"]
        assert m.validity == "invalid"
        assert m.validity_reason == "overflow"

    def test_read_state_id04_water_contact(self) -> None:
        """ID04: water_contact wird als State zurÃ¼ckgegeben."""
        reader = WeatherHubReader()
        packet = self._make_gateway_packet(
            sensor_id="041234567890",
            sensor_type=0x04,
            decoded_values={
                "temperature": {"value": 21.3, "error": False, "overflow": False},
                "humidity": {"value": 48.0, "error": False, "overflow": False},
                "water_contact_raw": 1,
                "status": {"battery_low": False, "event_transmission": False, "counter": 1},
            },
        )

        reader.update_from_packets([packet])
        states = reader.read_state()

        assert states["weatherhub_041234567890"]["battery_low"] is False
        assert states["weatherhub_041234567890"]["water_contact"] is True

    def test_read_state_id10_contact_open(self) -> None:
        """ID10: contact_open wird als State zurÃ¼ckgegeben."""
        reader = WeatherHubReader()
        packet = self._make_gateway_packet(
            sensor_id="101234567890",
            sensor_type=0x10,
            decoded_values={
                "contact": {"open": True, "time_unit": 0, "elapsed_value": 0},
                "status": {"battery_low": False, "event_transmission": False, "counter": 1},
            },
        )

        reader.update_from_packets([packet])
        states = reader.read_state()

        assert states["weatherhub_101234567890"]["battery_low"] is False
        assert states["weatherhub_101234567890"]["contact_open"] is True

    def test_read_state_id10_previous_events(self) -> None:
        """ID10: previous-Ereignisse werden als States zurÃ¼ckgegeben."""
        reader = WeatherHubReader()
        packet = self._make_gateway_packet(
            sensor_id="101234567890",
            sensor_type=0x10,
            decoded_values={
                "contact": {"open": True, "time_unit": 2, "elapsed_value": 5},
                "contact_previous": {"open": False, "time_unit": 2, "elapsed_value": 10},
                "contact_previous_1": {"open": True, "time_unit": 2, "elapsed_value": 15},
                "contact_previous_2": {"open": False, "time_unit": 2, "elapsed_value": 20},
                "status": {"battery_low": False},
            },
        )

        reader.update_from_packets([packet])
        states = reader.read_state()

        s = states["weatherhub_101234567890"]
        assert s["contact_open"] is True
        assert s["contact_previous_open"] is False
        assert s["contact_previous_1_open"] is True
        assert s["contact_previous_2_open"] is False
