"""Bridge: WeatherHub-Packet → Batch → Store."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from model.batch import Batch
from otterpi_store import BatchStore
from sequence_store import SequenceStore
from weatherhub import WeatherHubReader
from weatherhub_gateway_decoder import GatewayPacket

LOGGER = logging.getLogger(__name__)


class SmartHomeBridge:
    def __init__(
        self,
        *,
        store: BatchStore,
        reader: WeatherHubReader,
        sequence_store: SequenceStore,
        logger_id: str = "smarthome",
    ) -> None:
        self.store = store
        self.reader = reader
        self.sequence_store = sequence_store
        self.logger_id = logger_id

    def on_packets_received(
        self,
        packets: list,
        client_ip: Optional[str] = None,
    ) -> None:
        for packet in packets:
            if not isinstance(packet, GatewayPacket):
                continue
            if not packet.decoded_values:
                continue

            self.reader.update_from_packets([packet], client_ip=client_ip)
            measurements = self.reader.measurements_from_packet(packet)

            if not measurements:
                continue

            states = self.reader.read_state(packet.sensor_id)
            batch = Batch(
                batch_id=str(uuid4()),
                logger_id=self.logger_id,
                sequence=self.sequence_store.next(),
                created_at=datetime.now(timezone.utc).isoformat(),
                measurements=measurements,
                states=states or None,
            )
            self.store.store(batch)
