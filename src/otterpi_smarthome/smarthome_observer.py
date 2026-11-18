"""Production entry point for OtterPi-SmartHome."""

import logging
import os

from alert_engine import AlertEngine
from alert_store import AlertStore
from otterpi import create_server
from otterpi_store import BatchStore
from sequence_store import SequenceStore
from smarthome_bridge import SmartHomeBridge
from weatherhub import WeatherHubReader
from weatherhub_gateway_listener import WeatherHubGatewayListener

LOGGER = logging.getLogger(__name__)


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    host = _required("SMARTHOME_HOST")
    port = int(_required("SMARTHOME_PORT"))
    database = _required("SMARTHOME_DATABASE")
    token = _required("SMARTHOME_TOKEN")
    sequence_file = _required("SMARTHOME_SEQUENCE_FILE")

    weatherhub_host = _required("SMARTHOME_WEATHERHUB_HOST")
    weatherhub_port = int(_required("SMARTHOME_WEATHERHUB_PORT"))
    weatherhub_allowlist = _required("SMARTHOME_WEATHERHUB_ALLOWLIST")
    cloud_forward = os.environ.get("SMARTHOME_CLOUD_FORWARD_ENABLED", "0") == "1"
    stale_after = float(os.environ.get("SMARTHOME_STALE_AFTER_SECONDS", "1800"))

    alert_db = os.environ.get(
        "SMARTHOME_ALERT_DB",
        "/var/lib/otterpi-smarthome/alerts.sqlite3",
    )
    alert_interval = int(os.environ.get("SMARTHOME_ALERT_INTERVAL_SECONDS", "300"))
    smtp_password = os.environ.get("SMTP_PASSWORD")

    store = BatchStore(database)
    alert_store = AlertStore(alert_db)
    alert_engine = AlertEngine(
        store=store,
        alert_store=alert_store,
        smtp_password=smtp_password,
        interval_seconds=alert_interval,
    )
    alert_engine.start()

    reader = WeatherHubReader(stale_after_seconds=stale_after)
    sequence_store = SequenceStore(sequence_file)
    bridge = SmartHomeBridge(
        store=store,
        reader=reader,
        sequence_store=sequence_store,
    )

    listener = WeatherHubGatewayListener(
        host=weatherhub_host,
        port=weatherhub_port,
        allowlist={ip.strip() for ip in weatherhub_allowlist.split(",") if ip.strip()},
        on_packets_received=bridge.on_packets_received,
        cloud_forward_enabled=cloud_forward,
    )
    listener.start()

    server = create_server(
        host,
        port,
        store,
        token=token,
        alert_engine=alert_engine,
        alert_store=alert_store,
    )

    LOGGER.info("OtterPi-SmartHome starting on %s:%s", host, port)

    try:
        server.serve_forever()
    finally:
        listener.stop()
        listener.join(timeout=5.0)
        alert_engine.stop()
        alert_engine.join(timeout=5.0)


if __name__ == "__main__":
    main()
