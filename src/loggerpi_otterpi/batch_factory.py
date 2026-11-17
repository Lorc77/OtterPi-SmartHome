import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from uuid import uuid4

from model.batch import Batch
from model.measurement import Measurement

LOGGER = logging.getLogger(__name__)


class SequenceStore:
    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def next(self) -> int:
        try:
            current = int(self.path.read_text()) if self.path.exists() else -1
        except (ValueError, OSError) as exc:
            LOGGER.warning(
                "Sequence file corrupted or unreadable (%s); using timestamp-based sequence",
                exc,
            )
            current = int(time.time() * 1000) - 1

        sequence = current + 1

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(str(sequence))
        except OSError as exc:
            LOGGER.error(
                "Failed to write sequence file (%s); using timestamp-based sequence",
                exc,
            )
            sequence = int(time.time() * 1000)

        return sequence


def create_batch(
    logger_id: str,
    sequence_store: SequenceStore,
    measurements: Optional[dict[str, Measurement]] = None,
    system: Optional[dict] = None,
    memory: Optional[dict] = None,
    states: Optional[dict] = None,
    operation: Optional[dict] = None,
    serial: Optional[dict] = None,
    setpoints: Optional[dict] = None,
    device: Optional[dict] = None,
    connectivity: Optional[dict] = None,
) -> Batch:
    return Batch(
        batch_id=str(uuid4()),
        logger_id=logger_id,
        sequence=sequence_store.next(),
        created_at=datetime.now(timezone.utc).isoformat(),
        measurements=measurements or {},
        system=system,
        memory=memory,
        states=states,
        operation=operation,
        serial=serial,
        setpoints=setpoints,
        device=device,
        connectivity=connectivity,
    )
