from batch_factory import SequenceStore, create_batch
from batch_queue import BatchQueue


def test_queue_persists_batch(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")

    batch = create_batch("logger-001", store)

    queue.enqueue(batch)

    pending = queue.pending()

    assert len(pending) == 1
    assert pending[0].to_dict() == batch.to_dict()


def test_empty_queue_has_no_pending_batches(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")

    assert queue.pending() == []


def test_queue_removes_specific_batch(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")

    first = create_batch("logger-001", store)
    second = create_batch("logger-001", store)

    queue.enqueue(first)
    queue.enqueue(second)

    queue.remove(first)

    pending = queue.pending()

    assert len(pending) == 1
    assert pending[0].to_dict() == second.to_dict()


def test_pending_skips_corrupted_line(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")

    batch = create_batch("logger-001", store)
    queue.enqueue(batch)

    # Korrupte Zeile anhängen
    with queue.path.open("a", encoding="utf-8") as f:
        f.write('{"batch_id": "broken", "sequ\n')

    pending = queue.pending()

    assert len(pending) == 1
    assert pending[0].batch_id == batch.batch_id


def test_remove_keeps_corrupted_line(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")

    batch = create_batch("logger-001", store)
    queue.enqueue(batch)

    with queue.path.open("a", encoding="utf-8") as f:
        f.write('{"batch_id": "broken", "sequ\n')

    queue.remove(batch)

    # Korrupte Zeile bleibt, Batch entfernt
    content = queue.path.read_text(encoding="utf-8")
    assert "broken" in content
    assert batch.batch_id not in content


def test_enqueue_handles_oserror(tmp_path, monkeypatch):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")
    batch = create_batch("logger-001", store)

    def broken_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.open", broken_open)

    # Kein Crash
    queue.enqueue(batch)


def test_move_to_dead_letter_handles_oserror(tmp_path, monkeypatch):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")
    batch = create_batch("logger-001", store)

    def broken_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.open", broken_open)

    # Kein Crash
    queue.move_to_dead_letter(batch)


def test_count_empty(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    assert queue.count() == 0


def test_count_with_batches(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")

    for _ in range(3):
        queue.enqueue(create_batch("logger-001", store))

    assert queue.count() == 3


def test_dead_letter_count_empty(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    assert queue.dead_letter_count() == 0


def test_dead_letter_count_with_batches(tmp_path):
    queue = BatchQueue(tmp_path / "queue.jsonl")
    store = SequenceStore(tmp_path / "sequence")

    batch = create_batch("logger-001", store)
    queue.enqueue(batch)
    queue.move_to_dead_letter(batch)

    assert queue.dead_letter_count() == 1
