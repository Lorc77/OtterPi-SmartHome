# OtterPi-SmartHome — Deployment

## Zweck

Dieses Dokument beschreibt den reproduzierbaren Deploymentweg des
OtterPi-SmartHome-Projekts auf dem OtterPi.

Die Anwendung wird aus dem GitHub-Repository `main` deployt.

Das Deployment der Anwendung ist von der Host-Infrastruktur
(nginx, TLS, DNS, Firewall und Routing) getrennt.

---

## 1. Voraussetzungen

### Entwicklungsrechner

Auf dem Entwicklungsrechner müssen vor einem Release mindestens
folgende Prüfungen erfolgreich sein:

```powershell
ruff check .
ruff format --check .
pytest
git diff --check
git status
```

Zusätzlich muss das gewünschte Commit nach GitHub gepusht worden sein.

---

## 2. Repository

Repository:

```text
https://github.com/Lorc77/OtterPi-SmartHome.git
```

Produktiver Branch:

```text
main
```

Der Deployment-Wrapper verwendet immer den tatsächlich ausgecheckten
Commit und schreibt diesen nach erfolgreichem Deployment nach:

```text
/opt/otterpi-smarthome/DEPLOYED_COMMIT
```

Zusätzlich werden folgende Dateien geschrieben:

```text
/opt/otterpi-smarthome/DEPLOYED_VERSION   menschenlesbare Version (z. B. v0.1.0)
/opt/otterpi-smarthome/VERSION            Version aus pyproject.toml (z. B. 0.1.0)
```

Die `DEPLOYED_*`-Dateien werden **nur bei erfolgreichem Update** geschrieben
(Fail-safe-Design). Schlägt der Service-Neustart fehl, bleibt die bisherige
Deployment-Version bestehen.

---

## 3. Deployment

Auf dem OtterPi:

```bash
sudo /usr/local/sbin/otterpi-smarthome-update smarthome
```

Der Wrapper:

1. klont den aktuellen `main`-Stand temporär,
2. bestimmt den Commit,
3. setzt `chmod +x` für `install.sh`,
4. führt `deploy/smarthome/install.sh` aus,
5. installiert die Anwendung unter `/opt/otterpi-smarthome`,
6. installiert die systemd-Service-Datei,
7. aktiviert `smarthome.observer.service`,
8. startet den Service neu,
9. prüft dessen Zustand,
10. schreibt den deployten Commit und die Version nach
    `/opt/otterpi-smarthome/DEPLOYED_COMMIT` und
    `/opt/otterpi-smarthome/DEPLOYED_VERSION`.

Service:

```text
smarthome.observer.service
```

Konfiguration:

```text
/etc/otterpi-smarthome/smarthome.env
```

### Flache Deploy-Struktur

Die Installation kopiert die Anwendungsdateien **flach** nach
`/opt/otterpi-smarthome/`:

```text
/opt/otterpi-smarthome/
├── admin.py
├── alert_engine.py
├── alert_store.py
├── archive_batches.py
├── backup.py
├── config_store.py
├── dashboard.py
├── dashboard_charts.py
├── dashboard_config.py
├── dashboard_constants.py
├── dashboard_data.py
├── heartbeat.py
├── notifier.py
├── otter2.png
├── otterpi.py
├── otterpi_store.py
├── sensor_schemas.py
├── sequence_store.py
├── smarthome_bridge.py
├── smarthome_observer.py
├── status.py
├── weatherhub.py
├── weatherhub_gateway_decoder.py
├── weatherhub_gateway_listener.py
└── model/
    ├── __init__.py
    ├── batch.py
    └── measurement.py
```

Da `model/` ein Unterverzeichnis ist und kein Python-Package-Setup
(`pip install -e .`) verwendet wird, muss `PYTHONPATH` explizit gesetzt
werden:

```bash
PYTHONPATH=/opt/otterpi-smarthome:/opt/otterpi-smarthome/model
```

Dies wird in der Service-Datei und der `.env`-Datei konfiguriert.

---

## 4. Verzeichnisse

| Zweck | Pfad | Owner | Rechte |
|---|---|---|---|
| Install | `/opt/otterpi-smarthome/` | `root:root` | 0755 |
| Persistenz | `/var/lib/otterpi-smarthome/` | `makki:makki` | 0750 |
| Datenbank | `/var/lib/otterpi-smarthome/smarthome.sqlite3` | `makki:makki` | 0640 |
| Alerts | `/var/lib/otterpi-smarthome/alerts.sqlite3` | `makki:makki` | 0640 |
| Sequence | `/var/lib/otterpi-smarthome/sequence` | `makki:makki` | 0640 |
| Config | `/var/lib/otterpi-smarthome/config/` | `makki:makki` | 0750 |
| Archive | `/var/lib/otterpi-smarthome/archive/` | `makki:makki` | 0750 |
| Env | `/etc/otterpi-smarthome/smarthome.env` | `root:root` | 0640 |
| Service | `smarthome.observer.service` | `root:root` | 0644 |

**Hinweis:** `config/` wird von `install.sh` explizit angelegt (DEC-017).
Die DBs und die Sequence werden von SQLite bzw. `SequenceStore` mit
Default-Rechten (0644) angelegt. Für 0640 entweder manuell `chmod`
oder `os.umask(0o027)` in `otterpi_store.py` und `alert_store.py` setzen.

---

## 5. Konfiguration

Die Konfiguration erfolgt über `/etc/otterpi-smarthome/smarthome.env`:

```bash
SMARTHOME_HOST=0.0.0.0
SMARTHOME_PORT=8091
SMARTHOME_TOKEN=<dein-token>
SMARTHOME_DATABASE=/var/lib/otterpi-smarthome/smarthome.sqlite3
SMARTHOME_SEQUENCE_FILE=/var/lib/otterpi-smarthome/sequence
SMARTHOME_ALERT_DB=/var/lib/otterpi-smarthome/alerts.sqlite3
SMARTHOME_ALERT_INTERVAL_SECONDS=300
SMARTHOME_CONFIG_DIR=/var/lib/otterpi-smarthome/config

SMARTHOME_WEATHERHUB_HOST=0.0.0.0
SMARTHOME_WEATHERHUB_PORT=3779
SMARTHOME_WEATHERHUB_ALLOWLIST=192.168.178.<gateway-ip>
SMARTHOME_CLOUD_FORWARD_ENABLED=1

PYTHONPATH=/opt/otterpi-smarthome:/opt/otterpi-smarthome/model
SMTP_PASSWORD=<app-passwort>
```

### Wichtige Variablen

| Variable | Bedeutung | Default |
|---|---|---|
| `SMARTHOME_HOST` | HTTP-Listener (Dashboard/Admin) | `0.0.0.0` |
| `SMARTHOME_PORT` | HTTP-Port | `8091` |
| `SMARTHOME_TOKEN` | Bearer-Token für `/api/v1/batches` | – |
| `SMARTHOME_DATABASE` | SQLite-Pfad | `/var/lib/otterpi-smarthome/smarthome.sqlite3` |
| `SMARTHOME_SEQUENCE_FILE` | Sequence-Datei | `/var/lib/otterpi-smarthome/sequence` |
| `SMARTHOME_ALERT_DB` | Alert-SQLite-Pfad | `/var/lib/otterpi-smarthome/alerts.sqlite3` |
| `SMARTHOME_ALERT_INTERVAL_SECONDS` | Alert-Engine-Intervall | `300` |
| `SMARTHOME_CONFIG_DIR` | Config-Verzeichnis | `/var/lib/otterpi-smarthome/config` |
| `SMARTHOME_WEATHERHUB_HOST` | Listener-Bind-Adresse | `0.0.0.0` |
| `SMARTHOME_WEATHERHUB_PORT` | Listener-Port | `3779` |
| `SMARTHOME_WEATHERHUB_ALLOWLIST` | Erlaubte Gateway-IPs (Komma-getrennt) | – |
| `SMARTHOME_CLOUD_FORWARD_ENABLED` | Cloud-Forward an `www.data199.com` | `0` |
| `SMTP_PASSWORD` | SMTP-Passwort (nur Secret) | – |

---

## 6. Service

Die Service-Datei `smarthome.observer.service`:

```ini
[Unit]
Description=OtterPi-SmartHome Observer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=makki
Group=makki
WorkingDirectory=/opt/otterpi-smarthome
EnvironmentFile=/etc/otterpi-smarthome/smarthome.env
Environment="PYTHONPATH=/opt/otterpi-smarthome:/opt/otterpi-smarthome/model"
ExecStart=/usr/bin/python3 -m smarthome_observer
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## 7. Verifikation

Nach jedem Deployment:

```bash
systemctl status smarthome.observer.service --no-pager
```

Commit prüfen:

```bash
cat /opt/otterpi-smarthome/DEPLOYED_COMMIT
```

Version prüfen:

```bash
cat /opt/otterpi-smarthome/DEPLOYED_VERSION
cat /opt/otterpi-smarthome/VERSION
```

Zusätzlich:

```bash
journalctl -u smarthome.observer.service -n 100 --no-pager
```

Datenbank prüfen:

```bash
ls -la /var/lib/otterpi-smarthome/
```

---

## 8. Deinstallation

Die Deinstallation ist im `update.sh` integriert:

```bash
# Standard: Service + Install-Dir + Wrapper entfernen, State/Config behalten
sudo /usr/local/sbin/otterpi-smarthome-update uninstall

# Mit --purge: auch State (DB, Sequence) und Config entfernen
sudo /usr/local/sbin/otterpi-smarthome-update uninstall --purge
```

---

## 9. Gateway konfigurieren

Das WeatherHub-Gateway muss auf den OtterPi zeigen:

1. Gateway-Webinterface öffnen.
2. Proxy-Modus aktivieren.
3. Ziel: `192.168.178.100:3779`.
4. Cloud-Forward aktivieren (falls gewünscht).
5. Allowlist prüfen (`SMARTHOME_WEATHERHUB_ALLOWLIST`).

Nach der Konfiguration:

```bash
sudo systemctl restart smarthome.observer.service
```

---

## 10. Verifikation nach Gateway-Konfiguration

- **Dashboard:** `http://192.168.178.100:8091/` öffnen.
- **Admin:** `http://192.168.178.100:8091/admin` öffnen.
- **Räume anlegen:** Rooms-Tab.
- **Sensoren zuordnen:** Rooms-Tab.
- **Alarm Limits konfigurieren:** Alarm Limits-Tab.
- **Mail/Notifications/Messages konfigurieren:** jeweilige Tabs.
- **Datenbank:** `smarthome.sqlite3` wächst.
- **Cloud-Forward:** `www.data199.com` empfängt Daten (falls aktiviert).

---

## 11. Wichtige Trennung

Das Application Deployment aktualisiert derzeit:

```text
Python-Anwendung
systemd-Service
Deployment-Wrapper
```

Es aktualisiert derzeit nicht automatisch:

```text
nginx
TLS-Zertifikate
DNS
Firewall
FRITZ!Box
IPv6-Freigaben
CDN/Tunnel
```

Diese Trennung ist absichtlich.

---

## 12. Aktueller Stand

Stand 2026-11-19:

```text
Repository:
    main

Version:
    v0.1.7

Application Deployment:
    implementiert

OtterPi Backend:
    0.0.0.0:8091

WeatherHub-Listener:
    0.0.0.0:3779

Dashboard:
    http://192.168.178.100:8091/

Admin:
    http://192.168.178.100:8091/admin

Datenbank:
    /var/lib/otterpi-smarthome/smarthome.sqlite3

Alerts:
    /var/lib/otterpi-smarthome/alerts.sqlite3

Config:
    /var/lib/otterpi-smarthome/config/

Service:
    smarthome.observer.service
```