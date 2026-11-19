"""Tests fÃ¼r die SmartHomeBridge."""

from otterpi_store import BatchStore
from sequence_store import SequenceStore
from smarthome_bridge import SmartHomeBridge
from weatherhub import WeatherHubReader
from weatherhub_gateway_decoder import BootPacket, GatewayPacket


def _make_id01_packet(sensor_id="017A5CD3FC1C", temp1=23.4, temp2=-25.1):
    return GatewayPacket(
        gateway_timestamp=1000,
        sensor_id=sensor_id,
        sensor_type=0x01,
        decoded_values={
            "temperature_1": {"value": temp1, "error": False, "overflow": False},
            "temperature_2": {"value": temp2, "error": False, "overflow": False},
        },
        raw_data=bytes(64),
    )


def _make_bridge(tmp_path):
    store = BatchStore(tmp_path / "otter.db")
    reader = WeatherHubReader()
    sequence_store = SequenceStore(tmp_path / "sequence")
    bridge = SmartHomeBridge(
        store=store,
        reader=reader,
        sequence_store=sequence_store,
    )
    return bridge, store


def test_bridge_stores_batch(tmp_path):
    bridge, store = _make_bridge(tmp_path)
    packet = _make_id01_packet()

    bridge.on_packets_received([packet], client_ip="192.168.178.121")

    latest = store.latest()
    assert latest is not None
    assert latest.logger_id == "smarthome"
    assert latest.sequence == 0
    assert "weatherhub_017a5cd3fc1c.temperature_1" in latest.measurements
    assert "weatherhub_017a5cd3fc1c.temperature_2" in latest.measurements
    assert latest.measurements["weatherhub_017a5cd3fc1c.temperature_2"].value == -25.1


def test_bridge_skips_boot_packets(tmp_path):
    bridge, store = _make_bridge(tmp_path)
    boot = BootPacket(raw_data=bytes(15))

    bridge.on_packets_received([boot])

    assert store.latest() is None


def test_bridge_skips_empty_packets(tmp_path):
    bridge, store = _make_bridge(tmp_path)
    packet = GatewayPacket(
        gateway_timestamp=1000,
        sensor_id="017A5CD3FC1C",
        sensor_type=0x01,
        decoded_values={},
        raw_data=bytes(64),
    )

    bridge.on_packets_received([packet])

    assert store.latest() is None


def test_bridge_uses_sequence(tmp_path):
    bridge, store = _make_bridge(tmp_path)

    bridge.on_packets_received([_make_id01_packet()])
    bridge.on_packets_received([_make_id01_packet()])

    latest = store.latest()
    assert latest is not None
    assert latest.sequence == 1


def test_bridge_uses_logger_id(tmp_path):
    store = BatchStore(tmp_path / "otter.db")
    reader = WeatherHubReader()
    sequence_store = SequenceStore(tmp_path / "sequence")
    bridge = SmartHomeBridge(
        store=store,
        reader=reader,
        sequence_store=sequence_store,
        logger_id="custom-smarthome",
    )

    bridge.on_packets_received([_make_id01_packet()])

    latest = store.latest()
    assert latest is not None
    assert latest.logger_id == "custom-smarthome"
