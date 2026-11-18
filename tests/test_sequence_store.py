"""Tests für den SequenceStore."""

from sequence_store import SequenceStore


def test_sequence_is_persistent(tmp_path):
    path = tmp_path / "sequence"

    first_store = SequenceStore(path)
    assert first_store.next() == 0
    assert first_store.next() == 1

    second_store = SequenceStore(path)
    assert second_store.next() == 2


def test_sequence_handles_corrupted_file(tmp_path):
    path = tmp_path / "sequence"
    path.write_text("not-a-number", encoding="utf-8")

    store = SequenceStore(path)
    sequence = store.next()

    # Timestamp-basierte Sequence (große Zahl)
    assert sequence > 1_000_000_000_000

    # Datei ist jetzt gültig
    assert int(path.read_text()) == sequence


def test_sequence_handles_oserror_on_write(tmp_path, monkeypatch):
    path = tmp_path / "sequence"
    store = SequenceStore(path)

    def broken_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.write_text", broken_write)

    sequence = store.next()

    # Timestamp-basierte Sequence (große Zahl)
    assert sequence > 1_000_000_000_000
