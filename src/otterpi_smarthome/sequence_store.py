"""Persistente Sequence pro SmartHome-Logger."""

import logging
import time
from pathlib import Path
from typing import Union

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
