import json

from batch_factory import SequenceStore, create_batch
from batch_queue import BatchQueue
from delivery import DeliveryResult
from model.measurement import Measurement
from runtime import LoggerRuntime


class FakeReader:
    def __init__(self, measurements):
        self.measurements = measurements
        self.calls = 0

    def read_measurements(self):
        self.calls += 1
        return self.measurements

    def read_state(self):
        return {}, {}

    def read_setpoints(self):
        return {}

    def read_device_info(self):
        return {}


class FakeDelivery:
    def __init__(self, result):
        if isinstance(result, list):
            self.results = list(result)
        else:
            self.results = None
            self.result = result
        self.batches = []

    def send(self, batch):
        self.batches.append(batch)
        if self.results is not None:
            return self.results.pop(0)
        return self.result


def _patch_system_info(monkeypatch):
    monkeypatch.setattr(
        "composer.get_system_info",
        lambda: {
            "time": {
                "current": "2026-09-17T12:00:00+00:00",
                "timezone": "UTC",
                "clock_state": "unknown",
            },
            "boot": {
                "last_boot_at": "2026-09-17T08:00:00+00:00",
                "uptime_seconds": 14400,
            },
            "cpu": {
                "usage_percent": 10.0,
                "load": {
                    "load_1m": 0.1,
                    "load_5m": 0.1,
                    "load_15m": 0.1,
                },
                "temperature_celsius": 45.0,
            },
            "memory": {
                "total_bytes": 100,
                "available_bytes": 50,
                "used_bytes": 50,
            },
        },
    )


def test_runtime_creates_and_delivers_one_batch(tmp_path, monkeypatch):
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.SUCCESS)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    assert reader.calls == 1
    assert len(delivery.batches) == 1
    assert delivery.batches[0].to_dict() == batch.to_dict()
    assert batch.measurements == {"atmoweb_101.temperature_1": measurements["temperature_1"]}
    assert batch.sequence == 0
    assert queue.pending() == []


def test_runtime_queues_batch_when_delivery_fails(tmp_path, monkeypatch):
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.TRANSIENT)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    assert reader.calls == 1
    assert len(delivery.batches) == 1

    pending = queue.pending()

    assert len(pending) == 1
    assert pending[0].to_dict() == batch.to_dict()


def test_runtime_combines_multiple_readers_into_one_batch(tmp_path, monkeypatch):
    reader_101 = FakeReader(
        {
            "temperature_1": Measurement(
                value=20.5,
                unit="celsius",
                measured_at="2026-09-17T12:00:00+00:00",
                validity="valid",
                source="atmoweb",
            )
        }
    )
    reader_102 = FakeReader(
        {
            "temperature_1": Measurement(
                value=21.5,
                unit="celsius",
                measured_at="2026-09-17T12:00:00+00:00",
                validity="valid",
                source="atmoweb",
            )
        }
    )

    delivery = FakeDelivery(DeliveryResult.SUCCESS)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={
            "atmoweb_101": reader_101,
            "atmoweb_102": reader_102,
        },
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    assert reader_101.calls == 1
    assert reader_102.calls == 1
    assert len(delivery.batches) == 1
    assert delivery.batches[0] is batch

    assert batch.measurements == {
        "atmoweb_101.temperature_1": reader_101.measurements["temperature_1"],
        "atmoweb_102.temperature_1": reader_102.measurements["temperature_1"],
    }
    assert batch.sequence == 0
    assert queue.pending() == []


def test_runtime_replays_queued_batch_before_new_batch(tmp_path, monkeypatch):
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    queue = BatchQueue(tmp_path / "queue.jsonl")
    sequence_store = SequenceStore(tmp_path / "sequence")

    queued_batch = create_batch(
        logger_id="logger-001",
        sequence_store=sequence_store,
        measurements=measurements,
    )
    queue.enqueue(queued_batch)

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.SUCCESS)

    monkeypatch.setattr(
        "composer.get_system_info",
        lambda: {
            "time": {
                "current": "2026-09-17T12:00:00+00:00",
                "timezone": "UTC",
                "clock_state": "unknown",
            },
            "boot": {
                "last_boot_at": "2026-09-17T08:00:00+00:00",
                "uptime_seconds": 14400,
            },
            "cpu": {
                "usage_percent": 10.0,
                "load": {
                    "load_1m": 0.1,
                    "load_5m": 0.1,
                    "load_15m": 0.1,
                },
                "temperature_celsius": 45.0,
            },
            "memory": {
                "total_bytes": 100,
                "available_bytes": 50,
                "used_bytes": 50,
            },
        },
    )

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=sequence_store,
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    assert reader.calls == 1
    assert len(delivery.batches) == 2
    assert delivery.batches[0].to_dict() == queued_batch.to_dict()
    assert delivery.batches[1].to_dict() == batch.to_dict()
    assert queue.pending() == []


class FakeFreezerReader:
    def __init__(self, measurements):
        self.measurements = measurements
        self.calls = 0

    def read_measurements(self):
        self.calls += 1
        return self.measurements

    def read_state(self):
        return {}, {}

    def read_device_info(self):
        return {}

    @property
    def serial(self):
        return {"device": "/dev/test/freezer", "state": "connected"}


class FakeReaderWithState:
    def __init__(self, measurements, states, operation, setpoints, device):
        self.measurements = measurements
        self.states = states
        self.operation = operation
        self.setpoints = setpoints
        self.device = device

    def read_measurements(self):
        return self.measurements

    def read_state(self):
        return self.states, self.operation

    def read_setpoints(self):
        return self.setpoints

    def read_device_info(self):
        return self.device


class FakeFreezerReaderWithState:
    def __init__(self, measurements, states, device, serial):
        self.measurements = measurements
        self.states = states
        self.device = device
        self._serial = serial

    def read_measurements(self):
        return self.measurements

    def read_state(self):
        return self.states, {}

    def read_device_info(self):
        return self.device

    @property
    def serial(self):
        return self._serial


def test_runtime_with_freezer_reader(tmp_path, monkeypatch):
    """Freezer-Reader trägt freezer.temperature in den Batch ein."""
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }
    freezer_measurements = {
        "freezer.temperature": Measurement(
            value=-82.0,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="freezer_serial",
        )
    }

    reader = FakeReader(measurements)
    freezer_reader = FakeFreezerReader(freezer_measurements)
    delivery = FakeDelivery(DeliveryResult.SUCCESS)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
        freezer_reader=freezer_reader,
    )

    batch = runtime.run_once()

    assert reader.calls == 1
    assert freezer_reader.calls == 1
    assert len(delivery.batches) == 1

    assert batch.measurements == {
        "atmoweb_101.temperature_1": measurements["temperature_1"],
        "freezer.temperature": freezer_measurements["freezer.temperature"],
    }


def test_runtime_without_freezer_reader(tmp_path, monkeypatch):
    """Ohne Freezer-Reader gibt es keinen freezer.temperature im Batch."""
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.SUCCESS)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
        # kein freezer_reader → None
    )

    batch = runtime.run_once()

    assert reader.calls == 1
    assert "freezer.temperature" not in batch.measurements


def test_runtime_with_freezer_queued_when_delivery_fails(tmp_path, monkeypatch):
    """Freezer-Batch wird bei fehlgeschlagener Zustellung in die Queue gelegt."""
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }
    freezer_measurements = {
        "freezer.temperature": Measurement(
            value=-82.0,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="freezer_serial",
        )
    }

    reader = FakeReader(measurements)
    freezer_reader = FakeFreezerReader(freezer_measurements)
    delivery = FakeDelivery(DeliveryResult.TRANSIENT)  # schlägt fehl
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
        freezer_reader=freezer_reader,
    )

    batch = runtime.run_once()

    assert len(delivery.batches) == 1

    pending = queue.pending()

    assert len(pending) == 1
    assert pending[0].to_dict() == batch.to_dict()
    assert "freezer.temperature" in pending[0].measurements


def test_runtime_merges_states_operation_setpoints_device(tmp_path, monkeypatch):
    _patch_system_info(monkeypatch)

    reader = FakeReaderWithState(
        measurements={},
        states={"door_open": True},
        operation={"mode": "program"},
        setpoints={"temperature": 24.0},
        device={"host": "141.51.190.101"},
    )

    delivery = FakeDelivery(DeliveryResult.SUCCESS)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    assert batch.states == {"atmoweb_101": {"door_open": True}}
    assert batch.operation == {"atmoweb_101": {"mode": "program"}}
    assert batch.setpoints == {"atmoweb_101": {"temperature": 24.0}}
    assert batch.device == {"atmoweb_101": {"host": "141.51.190.101"}}


def test_runtime_merges_freezer_serial_and_alarms(tmp_path, monkeypatch):
    _patch_system_info(monkeypatch)

    reader = FakeReader({})
    freezer = FakeFreezerReaderWithState(
        measurements={},
        states={"alarms": ["ac_power_failure"]},
        device={"port": "/dev/test/freezer"},
        serial={"device": "/dev/test/freezer", "state": "connected"},
    )

    delivery = FakeDelivery(DeliveryResult.SUCCESS)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
        freezer_reader=freezer,
    )

    batch = runtime.run_once()

    assert batch.states["freezer"] == {"alarms": ["ac_power_failure"]}
    assert batch.serial == {"device": "/dev/test/freezer", "state": "connected"}
    assert batch.device["freezer"] == {"port": "/dev/test/freezer"}


def test_runtime_moves_permanent_failure_to_dead_letter(tmp_path, monkeypatch):
    """Neuer Batch mit PERMANENT → Dead-Letter, nicht in Queue."""
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.PERMANENT)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    assert queue.pending() == []

    dead_letter_path = tmp_path / "dead_letter.jsonl"
    assert dead_letter_path.exists()

    with dead_letter_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["batch_id"] == batch.batch_id


def test_runtime_replay_moves_permanent_to_dead_letter(tmp_path, monkeypatch):
    """Queued Batch mit PERMANENT → Dead-Letter, aus Queue entfernt."""
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    queue = BatchQueue(tmp_path / "queue.jsonl")
    sequence_store = SequenceStore(tmp_path / "sequence")

    queued_batch = create_batch(
        logger_id="logger-001",
        sequence_store=sequence_store,
        measurements=measurements,
    )
    queue.enqueue(queued_batch)

    reader = FakeReader(measurements)
    delivery = FakeDelivery([DeliveryResult.PERMANENT, DeliveryResult.SUCCESS])

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=sequence_store,
        delivery=delivery,
        queue=queue,
    )

    runtime.run_once()

    assert queue.pending() == []

    dead_letter_path = tmp_path / "dead_letter.jsonl"
    assert dead_letter_path.exists()

    with dead_letter_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["batch_id"] == queued_batch.batch_id


def test_runtime_replay_stops_on_transient(tmp_path, monkeypatch):
    """Queued Batch mit TRANSIENT → bleibt in Queue, neuer Batch wird enqueued."""
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    queue = BatchQueue(tmp_path / "queue.jsonl")
    sequence_store = SequenceStore(tmp_path / "sequence")

    queued_batch = create_batch(
        logger_id="logger-001",
        sequence_store=sequence_store,
        measurements=measurements,
    )
    queue.enqueue(queued_batch)

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.TRANSIENT)

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=sequence_store,
        delivery=delivery,
        queue=queue,
    )

    runtime.run_once()

    # Queued Batch bleibt (TRANSIENT), neuer Batch wird zusätzlich enqueued
    pending = queue.pending()
    assert len(pending) == 2
    assert pending[0].batch_id == queued_batch.batch_id


def test_runtime_includes_connectivity(tmp_path, monkeypatch):
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.SUCCESS)
    queue = BatchQueue(tmp_path / "queue.jsonl")

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=SequenceStore(tmp_path / "sequence"),
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    assert batch.connectivity == {
        "queue": {
            "depth": 0,
            "dead_letter_count": 0,
        }
    }


def test_runtime_connectivity_reflects_queue(tmp_path, monkeypatch):
    measurements = {
        "temperature_1": Measurement(
            value=20.5,
            unit="celsius",
            measured_at="2026-09-17T12:00:00+00:00",
            validity="valid",
            source="atmoweb",
        )
    }

    queue = BatchQueue(tmp_path / "queue.jsonl")
    sequence_store = SequenceStore(tmp_path / "sequence")

    # Zwei Batches in die Queue legen
    for _ in range(2):
        queue.enqueue(create_batch("logger-001", sequence_store, measurements=measurements))

    reader = FakeReader(measurements)
    delivery = FakeDelivery(DeliveryResult.TRANSIENT)

    _patch_system_info(monkeypatch)

    runtime = LoggerRuntime(
        logger_id="logger-001",
        readers={"atmoweb_101": reader},
        sequence_store=sequence_store,
        delivery=delivery,
        queue=queue,
    )

    batch = runtime.run_once()

    # Queue hatte 2 Batches, Replay schlägt fehl (TRANSIENT), neuer Batch wird enqueued
    # connectivity wird VOR dem neuen Batch berechnet → depth = 2
    assert batch.connectivity["queue"]["depth"] == 2
