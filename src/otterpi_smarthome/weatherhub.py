"""WeatherHub measurement adapter.

Provides the WeatherHubReader to convert decoded Gateway packets
into Core Measurement objects.
"""

from datetime import datetime, timezone
from typing import Optional, Union

from model.measurement import Measurement
from weatherhub_gateway_decoder import BootPacket, GatewayPacket


def _contact_timestamp(contact: dict, gateway_timestamp: int) -> int:
    """Berechnet den Unix-Timestamp aus time_unit/elapsed_value."""
    unit = contact.get("time_unit", 3)
    elapsed = contact.get("elapsed_value", 0)
    if unit == 0:
        elapsed_seconds = 86400 * elapsed
    elif unit == 1:
        elapsed_seconds = 3600 * elapsed
    elif unit == 2:
        elapsed_seconds = 60 * elapsed
    else:
        elapsed_seconds = elapsed
    return gateway_timestamp - elapsed_seconds


class WeatherHubReader:
    """Adapter between WeatherHub Gateway packets and Core Measurements."""

    def __init__(self, stale_after_seconds: float = 1800.0) -> None:
        self.stale_after_seconds = stale_after_seconds
        self._latest_packets: dict[str, GatewayPacket] = {}
        self._reception_times: dict[str, str] = {}
        self._gateway_ips: dict[str, str] = {}

    def update_from_packets(
        self,
        packets: list[Union[BootPacket, GatewayPacket]],
        client_ip: Optional[str] = None,
    ) -> None:
        """Process new decoded packets and update the internal state."""
        received_at = datetime.now(timezone.utc).isoformat()

        for packet in packets:
            # Skip BootPackets or packets without decoded values
            if not isinstance(packet, GatewayPacket):
                continue
            if not packet.decoded_values:
                continue

            self._latest_packets[packet.sensor_id] = packet
            self._reception_times[packet.sensor_id] = received_at
            if client_ip is not None:
                self._gateway_ips[packet.sensor_id] = client_ip

    def _is_stale(self, sensor_id: str) -> bool:
        """True, wenn der letzte Empfang für diesen Sensor zu lange her ist."""
        if sensor_id not in self._reception_times:
            return True

        received_at = datetime.fromisoformat(self._reception_times[sensor_id])
        age_seconds = (datetime.now(timezone.utc) - received_at).total_seconds()
        return age_seconds > self.stale_after_seconds

    @property
    def gateway_timestamps(self) -> dict[str, int]:
        """Return the latest gateway timestamp for each known sensor.

        Preserves the Gateway timestamp separately from the LoggerPi reception time,
        similar to how AtmoWebReader exposes device_time.
        """
        return {
            sensor_id: packet.gateway_timestamp
            for sensor_id, packet in self._latest_packets.items()
        }

    def read_measurements(self) -> dict[str, Measurement]:
        """Return all current valid measurements from known sensors."""
        measurements: dict[str, Measurement] = {}

        for sensor_id, packet in self._latest_packets.items():
            received_at = self._reception_times[sensor_id]
            sensor_type = packet.sensor_type
            decoded = packet.decoded_values

            prefix = f"weatherhub_{sensor_id.lower()}"

            fields_to_extract = {}

            if sensor_type == 0x01:
                fields_to_extract = {
                    "temperature_1": ("celsius", decoded.get("temperature_1")),
                    "temperature_2": ("celsius", decoded.get("temperature_2")),
                }
            elif sensor_type == 0x02:
                fields_to_extract = {
                    "temperature": ("celsius", decoded.get("temperature")),
                }
            elif sensor_type == 0x03:
                fields_to_extract = {
                    "temperature": ("celsius", decoded.get("temperature")),
                    "humidity": ("percent", decoded.get("humidity")),
                }
            elif sensor_type == 0x04:
                # water_contact_raw is intentionally ignored here
                fields_to_extract = {
                    "temperature": ("celsius", decoded.get("temperature")),
                    "humidity": ("percent", decoded.get("humidity")),
                }
            elif sensor_type == 0x07:
                fields_to_extract = {
                    "temperature_indoor": (
                        "celsius",
                        decoded.get("temperature_indoor"),
                    ),
                    "humidity_indoor": (
                        "percent",
                        decoded.get("humidity_indoor"),
                    ),
                    "temperature_outdoor": (
                        "celsius",
                        decoded.get("temperature_outdoor"),
                    ),
                    "humidity_outdoor": (
                        "percent",
                        decoded.get("humidity_outdoor"),
                    ),
                }
            elif sensor_type == 0x0E:
                fields_to_extract = {
                    "temperature": ("celsius", decoded.get("temperature")),
                    "humidity": ("percent", decoded.get("humidity")),
                }
            elif sensor_type == 0x10:
                # ID10 contact is intentionally ignored here (no measurements)
                pass

            for field_name, config in fields_to_extract.items():
                unit = config[0]
                value_dict = config[1]

                if not isinstance(value_dict, dict):
                    continue

                value = value_dict.get("value")
                validity = "valid"
                validity_reason = None

                if value_dict.get("error"):
                    validity = "invalid"
                    validity_reason = "sensor_error"
                elif value_dict.get("overflow"):
                    validity = "invalid"
                    validity_reason = "overflow"
                elif self._is_stale(sensor_id):
                    validity = "stale"

                measurement = Measurement(
                    value=value if validity in ("valid", "stale") else None,
                    unit=unit,
                    measured_at=received_at,
                    validity=validity,
                    source="weatherhub",
                    validity_reason=validity_reason,
                )

                measurements[f"{prefix}.{field_name}"] = measurement

        return measurements

    def measurements_from_packet(
        self,
        packet: GatewayPacket,
    ) -> dict[str, Measurement]:
        """Liefert die Measurements eines einzelnen Pakets.

        Anders als ``read_measurements()`` werden nur die Measurements
        dieses Pakets zurückgegeben, nicht die aller bekannten Sensoren.
        """
        if not isinstance(packet, GatewayPacket):
            return {}
        if not packet.decoded_values:
            return {}

        sensor_id = packet.sensor_id
        received_at = self._reception_times.get(
            sensor_id,
            datetime.now(timezone.utc).isoformat(),
        )
        sensor_type = packet.sensor_type
        decoded = packet.decoded_values
        prefix = f"weatherhub_{sensor_id.lower()}"

        fields_to_extract = {}

        if sensor_type == 0x01:
            fields_to_extract = {
                "temperature_1": ("celsius", decoded.get("temperature_1")),
                "temperature_2": ("celsius", decoded.get("temperature_2")),
            }
        elif sensor_type == 0x02:
            fields_to_extract = {
                "temperature": ("celsius", decoded.get("temperature")),
            }
        elif sensor_type == 0x03:
            fields_to_extract = {
                "temperature": ("celsius", decoded.get("temperature")),
                "humidity": ("percent", decoded.get("humidity")),
            }
        elif sensor_type == 0x04:
            fields_to_extract = {
                "temperature": ("celsius", decoded.get("temperature")),
                "humidity": ("percent", decoded.get("humidity")),
            }
        elif sensor_type == 0x07:
            fields_to_extract = {
                "temperature_indoor": ("celsius", decoded.get("temperature_indoor")),
                "humidity_indoor": ("percent", decoded.get("humidity_indoor")),
                "temperature_outdoor": ("celsius", decoded.get("temperature_outdoor")),
                "humidity_outdoor": ("percent", decoded.get("humidity_outdoor")),
            }
        elif sensor_type == 0x0E:
            fields_to_extract = {
                "temperature": ("celsius", decoded.get("temperature")),
                "humidity": ("percent", decoded.get("humidity")),
            }
        elif sensor_type == 0x10:
            pass

        measurements: dict[str, Measurement] = {}
        for field_name, config in fields_to_extract.items():
            unit = config[0]
            value_dict = config[1]

            if not isinstance(value_dict, dict):
                continue

            value = value_dict.get("value")
            validity = "valid"
            validity_reason = None

            if value_dict.get("error"):
                validity = "invalid"
                validity_reason = "sensor_error"
            elif value_dict.get("overflow"):
                validity = "invalid"
                validity_reason = "overflow"
            elif sensor_id in self._reception_times and self._is_stale(sensor_id):
                validity = "stale"

            measurement = Measurement(
                value=value if validity in ("valid", "stale") else None,
                unit=unit,
                measured_at=received_at,
                validity=validity,
                source="weatherhub",
                validity_reason=validity_reason,
            )

            measurements[f"{prefix}.{field_name}"] = measurement

        return measurements

    def read_state(self, sensor_id: Optional[str] = None) -> dict[str, object]:
        """Liefert die States für einen Sensor oder alle.

        Enthält ``battery_low`` (alle Sensoren), ``water_contact`` (ID04)
        und ``contact_open`` (ID10).
        """
        states: dict[str, object] = {}
        for sid, packet in self._latest_packets.items():
            if sensor_id is not None and sid != sensor_id:
                continue
            prefix = f"weatherhub_{sid.lower()}"
            decoded = packet.decoded_values
            sensor_states: dict[str, object] = {}

            status = decoded.get("status")
            if isinstance(status, dict):
                if "battery_low" in status:
                    sensor_states["battery_low"] = status["battery_low"]
                if "event_transmission" in status:
                    sensor_states["event_transmission"] = status["event_transmission"]
                if "counter" in status:
                    sensor_states["counter"] = status["counter"]

            # ID04: water_contact
            if packet.sensor_type == 0x04 and "water_contact_raw" in decoded:
                sensor_states["water_contact"] = bool(decoded["water_contact_raw"])

            # ID10: contact_open + Zeitpunkt + previous events
            if packet.sensor_type == 0x10:
                for suffix in ("", "_previous", "_previous_1", "_previous_2"):
                    contact = decoded.get(f"contact{suffix}")
                    if isinstance(contact, dict):
                        sensor_states[f"contact{suffix}_open"] = contact.get("open", False)
                        if "time_unit" in contact:
                            sensor_states[f"contact{suffix}_since"] = _contact_timestamp(
                                contact, packet.gateway_timestamp
                            )

            if sensor_states:
                states[prefix] = sensor_states
        return states

    def read_device_info(self) -> dict[str, object]:
        info: dict[str, object] = {}
        for sensor_id, packet in self._latest_packets.items():
            prefix = f"weatherhub_{sensor_id.lower()}"
            info[prefix] = {
                "sensor_id": sensor_id,
                "sensor_type": packet.sensor_type,
                "gateway_ip": self._gateway_ips.get(sensor_id),
                "gateway_timestamp": packet.gateway_timestamp,
            }
        return info
