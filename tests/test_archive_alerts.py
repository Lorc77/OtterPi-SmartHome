"""Tests für die Alert-Archivierung."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from archive_batches import (
    _archive_alerts,
    _connect_database,
    _delete_alerts,
    _get_alerts_archive_filename,
    _get_alerts_to_archive,
    _get_cutoff_date,
    main,
)


def _create_test_alert_database(
    db_path: Path,
    num_alerts: int = 5,
    days_old: int = 0,
    resolved: bool = True,
) -> None:
    """Erstellt eine Test-Datenbank mit Alerts."""
    conn = _connect_database(str(db_path))
    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    sensor TEXT NOT NULL,
                    rule TEXT NOT NULL,
                    value REAL,
                    threshold REAL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    dedup_key TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    acknowledged_at TEXT,
                    acknowledged_by TEXT,
                    resolved_at TEXT
                )
                """
            )

            for i in range(num_alerts):
                created_at = (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat()
                resolved_at = created_at if resolved else None
                conn.execute(
                    """
                    INSERT INTO alerts (
                        created_at, sensor, rule, severity, message,
                        dedup_key, resolved_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        created_at,
                        f"sensor_{i}",
                        "test_rule",
                        "critical",
                        f"message {i}",
                        f"sensor_{i}:test_rule:critical",
                        resolved_at,
                    ),
                )
    finally:
        conn.close()


def _count_alerts(db_path: Path) -> int:
    conn = _connect_database(str(db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    finally:
        conn.close()


def _read_alert_archive(file_path: Path) -> list[dict]:
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines if line.strip()]


class TestGetAlertsToArchive:
    def test_force_returns_all_resolved(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=5, resolved=True)
        conn = _connect_database(str(db_path))
        try:
            cutoff = _get_cutoff_date(force=True)
            alerts = _get_alerts_to_archive(conn, cutoff)
            assert len(alerts) == 5
        finally:
            conn.close()

    def test_only_resolved(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=3, resolved=True)
        _create_test_alert_database(db_path, num_alerts=2, resolved=False)
        conn = _connect_database(str(db_path))
        try:
            cutoff = _get_cutoff_date(force=True)
            alerts = _get_alerts_to_archive(conn, cutoff)
            assert len(alerts) == 3
        finally:
            conn.close()

    def test_cutoff_filters_old(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=3, days_old=400, resolved=True)
        _create_test_alert_database(db_path, num_alerts=2, days_old=0, resolved=True)
        conn = _connect_database(str(db_path))
        try:
            cutoff = _get_cutoff_date(force=False)
            alerts = _get_alerts_to_archive(conn, cutoff)
            assert len(alerts) == 3
        finally:
            conn.close()

    def test_year_month_filter(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=3, resolved=True)
        conn = _connect_database(str(db_path))
        try:
            now = datetime.now(timezone.utc)
            alerts = _get_alerts_to_archive(
                conn, "1970-01-01T00:00:00", year=now.year, month=now.month
            )
            assert len(alerts) == 3
        finally:
            conn.close()

    def test_invalid_month_raises(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path)
        conn = _connect_database(str(db_path))
        try:
            try:
                _get_alerts_to_archive(conn, "1970-01-01T00:00:00", year=2025, month=13)
                assert False, "Should have raised ValueError"
            except ValueError as exc:
                assert "Month must be 1-12" in str(exc)
        finally:
            conn.close()


class TestArchiveAlerts:
    def test_archive_creates_gzip_file(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=3)
        conn = _connect_database(str(db_path))
        try:
            cutoff = _get_cutoff_date(force=True)
            alerts = _get_alerts_to_archive(conn, cutoff)
            output_path = tmp_path / "alerts.json.gz"
            count = _archive_alerts(conn, alerts, output_path)
            assert count == 3
            assert output_path.exists()
            archived = _read_alert_archive(output_path)
            assert len(archived) == 3
            assert archived[0]["sensor"] == "sensor_0"
        finally:
            conn.close()

    def test_archive_does_not_overwrite_existing(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=3)
        output_path = tmp_path / "alerts.json.gz"
        output_path.write_text("existing", encoding="utf-8")
        conn = _connect_database(str(db_path))
        try:
            cutoff = _get_cutoff_date(force=True)
            alerts = _get_alerts_to_archive(conn, cutoff)
            count = _archive_alerts(conn, alerts, output_path)
            assert count == 0
            assert output_path.read_text(encoding="utf-8") == "existing"
        finally:
            conn.close()

    def test_archive_empty(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=0)
        conn = _connect_database(str(db_path))
        try:
            cutoff = _get_cutoff_date(force=True)
            alerts = _get_alerts_to_archive(conn, cutoff)
            output_path = tmp_path / "alerts.json.gz"
            count = _archive_alerts(conn, alerts, output_path)
            assert count == 0
            assert not output_path.exists()
        finally:
            conn.close()


class TestDeleteAlerts:
    def test_delete_specific(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=5)
        conn = _connect_database(str(db_path))
        try:
            deleted = _delete_alerts(conn, [1, 2])
            assert deleted == 2
            assert _count_alerts(db_path) == 3
        finally:
            conn.close()

    def test_delete_nonexistent(self, tmp_path):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=3)
        conn = _connect_database(str(db_path))
        try:
            deleted = _delete_alerts(conn, [999])
            assert deleted == 0
            assert _count_alerts(db_path) == 3
        finally:
            conn.close()


class TestGetAlertsArchiveFilename:
    def test_with_year_month(self):
        assert _get_alerts_archive_filename(2025, 10) == "otterpi-smarthome_alerts_2025-10.json.gz"

    def test_without_year_month(self):
        now = datetime.now(timezone.utc)
        assert (
            _get_alerts_archive_filename(None, None)
            == f"otterpi-smarthome_alerts_{now.strftime('%Y-%m')}.json.gz"
        )


class TestMainAlerts:
    def test_main_archives_and_deletes_alerts(self, tmp_path, monkeypatch):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=5, days_old=400)
        archive_dir = tmp_path / "archive"
        output_path = archive_dir / "alerts_TEST.json.gz"

        monkeypatch.setattr("archive_batches.DEFAULT_DATABASE", str(tmp_path / "nonexistent.db"))
        monkeypatch.setattr("archive_batches.DEFAULT_ALERT_DATABASE", str(db_path))
        monkeypatch.setattr("archive_batches.DEFAULT_ARCHIVE_DIR", str(archive_dir))
        monkeypatch.setattr(
            "sys.argv",
            [
                "archive_batches.py",
                "--force",
                "--output-alerts",
                str(output_path),
                "--no-delete",
            ],
        )

        main()

        assert output_path.exists()
        assert _count_alerts(db_path) == 5

    def test_main_without_output_deletes_alerts(self, tmp_path, monkeypatch):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=5, days_old=400)
        archive_dir = tmp_path / "archive"

        monkeypatch.setattr("archive_batches.DEFAULT_DATABASE", str(tmp_path / "nonexistent.db"))
        monkeypatch.setattr("archive_batches.DEFAULT_ALERT_DATABASE", str(db_path))
        monkeypatch.setattr("archive_batches.DEFAULT_ARCHIVE_DIR", str(archive_dir))
        monkeypatch.setattr(
            "sys.argv",
            ["archive_batches.py", "--force"],
        )

        main()

        files = list(archive_dir.glob("otterpi-smarthome_alerts_*.json.gz"))
        assert len(files) == 1
        assert _count_alerts(db_path) == 0

    def test_main_dry_run_no_changes(self, tmp_path, monkeypatch):
        db_path = tmp_path / "alerts.db"
        _create_test_alert_database(db_path, num_alerts=5, days_old=400)
        archive_dir = tmp_path / "archive"

        monkeypatch.setattr("archive_batches.DEFAULT_DATABASE", str(tmp_path / "nonexistent.db"))
        monkeypatch.setattr("archive_batches.DEFAULT_ALERT_DATABASE", str(db_path))
        monkeypatch.setattr("archive_batches.DEFAULT_ARCHIVE_DIR", str(archive_dir))
        monkeypatch.setattr(
            "sys.argv",
            ["archive_batches.py", "--force", "--dry-run"],
        )

        main()

        assert not list(archive_dir.glob("*.json.gz"))
        assert _count_alerts(db_path) == 5
