#!/bin/bash
set -euo pipefail

REPO_URL="https://github.com/Lorc77/OtterPi-SmartHome.git"
BRANCH="main"
ROLE="${1:-}"

SERVICE_NAME="smarthome.observer.service"
INSTALL_DIR="/opt/otterpi-smarthome"
STATE_DIR="/var/lib/otterpi-smarthome"
CONFIG_DIR="/etc/otterpi-smarthome"
UPDATE_WRAPPER="/usr/local/sbin/otterpi-smarthome-update"

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root."
    exit 1
fi

case "$ROLE" in
    smarthome)
        INSTALL_SCRIPT="deploy/smarthome/install.sh"
        ;;
    uninstall)
        PURGE=0
        if [ "${2:-}" = "--purge" ]; then
            PURGE=1
        fi

        echo "Stopping and disabling $SERVICE_NAME..."
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true

        echo "Removing service file..."
        rm -f "/etc/systemd/system/$SERVICE_NAME"
        systemctl daemon-reload

        echo "Removing install directory $INSTALL_DIR..."
        rm -rf "$INSTALL_DIR"

        echo "Removing update wrapper $UPDATE_WRAPPER..."
        rm -f "$UPDATE_WRAPPER"

        if [ "$PURGE" -eq 1 ]; then
            echo "Removing state directory $STATE_DIR..."
            rm -rf "$STATE_DIR"
            echo "Removing config directory $CONFIG_DIR..."
            rm -rf "$CONFIG_DIR"
        else
            echo
            echo "State directory $STATE_DIR kept (use --purge to remove)."
            echo "Config directory $CONFIG_DIR kept (use --purge to remove)."
        fi

        echo
        echo "OtterPi-SmartHome uninstalled."
        exit 0
        ;;
    *)
        echo "Usage: sudo $0 {smarthome|uninstall [--purge]}"
        exit 2
        ;;
esac

TMP_DIR="$(mktemp -d /tmp/otterpi-smarthome-update.XXXXXX)"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Fetching $REPO_URL ($BRANCH)..."
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$TMP_DIR/repo"

chmod +x "$TMP_DIR/repo/deploy/smarthome/install.sh"

REPO_DIR="$TMP_DIR/repo"
COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"

echo "Deploying commit: $COMMIT"
echo

cd "$REPO_DIR"
"./$INSTALL_SCRIPT"

echo
echo "Restarting $SERVICE_NAME..."
systemctl restart "$SERVICE_NAME"

echo
echo "Checking $SERVICE_NAME..."
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    echo
    echo "ERROR: $SERVICE_NAME did not become active."
    systemctl status "$SERVICE_NAME" --no-pager || true
    exit 1
fi

printf '%s\n' "$COMMIT" > /opt/otterpi-smarthome/DEPLOYED_COMMIT

VERSION=$(git -C "$REPO_DIR" describe --tags --exact-match 2>/dev/null || echo "dev")
printf '%s\n' "$VERSION" > /opt/otterpi-smarthome/DEPLOYED_VERSION

chown root:root /opt/otterpi-smarthome/DEPLOYED_COMMIT /opt/otterpi-smarthome/DEPLOYED_VERSION
chmod 0644 /opt/otterpi-smarthome/DEPLOYED_COMMIT /opt/otterpi-smarthome/DEPLOYED_VERSION

echo
echo "Deployment successful."
echo "Commit:  $COMMIT"
echo "Version: $VERSION"
echo "Service: $SERVICE_NAME"
echo
systemctl status "$SERVICE_NAME" --no-pager
