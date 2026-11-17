#!/bin/bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_DIR="/opt/otterpi-smarthome"
SERVICE_NAME="otterpi-smarthome.observer.service"
SERVICE_FILE="$REPO_DIR/deploy/smarthome/$SERVICE_NAME"

echo "Installing OtterPi-SmartHome to $INSTALL_DIR"

install -d -o root -g root -m 0755 "$INSTALL_DIR"
install -d -o root -g root -m 0755 "$INSTALL_DIR/model"

SMARTHOME_FILES=(
    otterpi.py
    otterpi_store.py
    dashboard.py
    dashboard_config.py
    dashboard_constants.py
    dashboard_data.py
    dashboard_charts.py
    admin.py
    config_store.py
    notifier.py
    archive_batches.py
    backup.py
    sensor_schemas.py
    alert_store.py
    alert_engine.py
    heartbeat.py
    status.py
    weatherhub.py
    weatherhub_gateway_decoder.py
    weatherhub_gateway_listener.py
    sequence_store.py
    smarthome_bridge.py
    smarthome_observer.py
    otter2.png
)

for file in "${SMARTHOME_FILES[@]}"; do
    install -o root -g root -m 0644 \
        "$REPO_DIR/src/otterpi_smarthome/$file" \
        "$INSTALL_DIR/$file"
done

install -o root -g root -m 0644 \
    "$REPO_DIR/src/otterpi_smarthome/model/__init__.py" \
    "$INSTALL_DIR/model/__init__.py"

install -o root -g root -m 0644 \
    "$REPO_DIR/src/otterpi_smarthome/model/batch.py" \
    "$INSTALL_DIR/model/batch.py"

install -o root -g root -m 0644 \
    "$REPO_DIR/src/otterpi_smarthome/model/measurement.py" \
    "$INSTALL_DIR/model/measurement.py"

# Schreibe VERSION-Datei
VERSION=$(grep '^version = ' "$REPO_DIR/pyproject.toml" | sed 's/version = "//;s/"//')
printf '%s\n' "$VERSION" > "$INSTALL_DIR/VERSION"
chown root:root "$INSTALL_DIR/VERSION"
chmod 0644 "$INSTALL_DIR/VERSION"

install -d -o root -g root -m 0755 /etc/otterpi-smarthome

if [ ! -f /etc/otterpi-smarthome/smarthome.env ]; then
    install -o root -g root -m 0640 \
        "$REPO_DIR/deploy/smarthome/smarthome.env.example" \
        /etc/otterpi-smarthome/smarthome.env

    echo
    echo "Created /etc/otterpi-smarthome/smarthome.env"
    echo "Please review it before starting the service."
fi

install -o root -g root -m 0644 \
    "$SERVICE_FILE" \
    "/etc/systemd/system/$SERVICE_NAME"

install -d -o makki -g makki -m 0750 \
    /var/lib/otterpi-smarthome

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

install -o root -g root -m 0755 \
    "$REPO_DIR/deploy/update.sh" \
    /usr/local/sbin/otterpi-smarthome-update

echo
echo "OtterPi-SmartHome installation complete."
echo
echo "Check configuration:"
echo "  sudoedit /etc/otterpi-smarthome/smarthome.env"
echo
echo "Start service:"
echo "  sudo systemctl restart $SERVICE_NAME"
echo
echo "Status:"
echo "  systemctl status $SERVICE_NAME --no-pager"
echo
echo "Current version:"
echo "  cat $INSTALL_DIR/VERSION"
