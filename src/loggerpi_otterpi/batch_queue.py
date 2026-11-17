import json
import logging
from pathlib import Path
from typing import Union

from model.batch import Batch
from model.measurement import Measurement

LOGGER = logging.getLogger(__name__)


class BatchQueue:
    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def enqueue(self, batch: Batch) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)

            with self.path.open("a", encoding="utf-8") as file:
                json.dump(batch.to_dict(), file, ensure_ascii=False)
                file.write("\n")
        except OSError as exc:
            LOGGER.error(
                "Failed to enqueue batch %s: %s",
                batch.batch_id,
                exc,
            )

    def pending(self) -> list[Batch]:
        if not self.path.exists():
            return []

        batches = []

        try:
            with self.path.open("r", encoding="utf-8") as file:
                for line in file:
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError as exc:
                        LOGGER.warning(
                            "Skipping corrupted queue line: %s",
                            exc,
                        )
                        continue

                    measurements = {
                        name: Measurement(**measurement)
                        for name, measurement in data.pop("measurements", {}).items()
                    }

                    batches.append(
                        Batch(
                            **data,
                            measurements=measurements,
                        )
                    )
        except OSError as exc:
            LOGGER.error("Failed to read queue: %s", exc)

        return batches

    def count(self) -> int:
        """Zählt die Zeilen in der Queue-Datei."""
        if not self.path.exists():
            return 0

        try:
            with self.path.open("r", encoding="utf-8") as file:
                return sum(1 for _ in file)
        except OSError as exc:
            LOGGER.error("Failed to count queue: %s", exc)
            return 0

    def dead_letter_count(self) -> int:
        """Zählt die Zeilen in der Dead-Letter-Datei."""
        dead_letter_path = self.path.parent / "dead_letter.jsonl"

        if not dead_letter_path.exists():
            return 0

        try:
            with dead_letter_path.open("r", encoding="utf-8") as file:
                return sum(1 for _ in file)
        except OSError as exc:
            LOGGER.error("Failed to count dead-letter: %s", exc)
            return 0

    def remove(self, batch: Batch) -> None:
        if not self.path.exists():
            return

        remaining = []

        try:
            with self.path.open("r", encoding="utf-8") as file:
                for line in file:
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        # Keep corrupted lines (don't remove them)
                        remaining.append(line)
                        continue

                    if (
                        data.get("batch_id") == batch.batch_id
                        and data.get("sequence") == batch.sequence
                    ):
                        continue

                    remaining.append(line)

            with self.path.open("w", encoding="utf-8") as file:
                file.writelines(remaining)
        except OSError as exc:
            LOGGER.error(
                "Failed to remove batch %s from queue: %s",
                batch.batch_id,
                exc,
            )

    def move_to_dead_letter(self, batch: Batch) -> None:
        dead_letter_path = self.path.parent / "dead_letter.jsonl"

        try:
            dead_letter_path.parent.mkdir(parents=True, exist_ok=True)

            with dead_letter_path.open("a", encoding="utf-8") as file:
                json.dump(batch.to_dict(), file, ensure_ascii=False)
                file.write("\n")
        except OSError as exc:
            LOGGER.error(
                "Failed to write batch %s to dead-letter: %s",
                batch.batch_id,
                exc,
            )
            return

        self.remove(batch)
