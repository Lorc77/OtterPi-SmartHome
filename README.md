# OtterPi-SmartHome

> Privates SmartHome-Monitoring auf dem OtterPi — unabhängig vom dienstlichen LoggerPi-OtterPi.

OtterPi-SmartHome empfängt WeatherHub-Sensordaten über ein eigenes Gateway
direkt am OtterPi, speichert sie in einer eigenen SQLite-Datenbank und stellt
sie über ein eigenes Dashboard und einen eigenen Admin bereit.

---

## Überblick

```text
WeatherHub-Gateway (192.168.178.x)
    ↓
HTTP PUT (binär)
    ↓
OtterPi-SmartHome (192.168.178.100:3779)
    ↓
WeatherHubGatewayListener
    ↓
WeatherHubGatewayDecoder
    ↓
WeatherHubReader
    ↓
SmartHomeBridge
    ↓
BatchStore → smarthome.sqlite3
    ↓
Dashboard + Admin (Port 8091)
```

- **Eigenständig:** Eigene Datenbank, eigener Service, eigenes Dashboard.
- **Parallel:** Läuft neben `loggerpi-otterpi` (dienstlich), keine gemeinsame DB.
- **Push-basiert:** Das Gateway sendet direkt an den OtterPi.
- **Kein Batch-Zirkus:** Keine Queue, kein Delivery, kein Retry — die Daten kommen direkt an.

---

## Architektur

```text
Quelle (WeatherHub-Gateway)
    ↓
WeatherHubGatewayListener (TCP, Port 3779)
    ├── Cloud-Forward → www.data199.com (optional)
    └── Callback → SmartHomeBridge
    ↓
WeatherHubGatewayDecoder
    ↓
WeatherHubReader
    ↓
SmartHomeBridge (Packet → Batch → Store)
    ↓
BatchStore → smarthome.sqlite3
    ↓
Dashboard + Admin (Port 8091)
```

**Zwei getrennte Services auf dem OtterPi:**

| Service | Port | Datenbank | Zweck |
|---|---:|---|---|
| `otterpi.observer.service` | 8090 | `batches.sqlite3` | Dienstlich (LoggerPi) |
| `otterpi-smarthome.observer.service` | 8091 | `smarthome.sqlite3` | Privat (SmartHome) |

---

## Komponenten

| Komponente | Beschreibung |
|---|---|
| `src/otterpi_smarthome/model/` | Datenmodelle: `Batch`, `Measurement` |
| `src/otterpi_smarthome/weatherhub.py` | WeatherHub-Adapter (Reader) |
| `src/otterpi_smarthome/weatherhub_gateway_decoder.py` | WeatherHub-Gateway-Decoder |
| `src/otterpi_smarthome/weatherhub_gateway_listener.py` | WeatherHub-Gateway-Listener (TCP) |
| `src/otterpi_smarthome/smarthome_bridge.py` | Packet → Batch → Store |
| `src/otterpi_smarthome/sequence_store.py` | Persistente Sequence |
| `src/otterpi_smarthome/smarthome_observer.py` | Prozess-Einstiegspunkt |
| `src/otterpi_smarthome/otterpi.py` | HTTP-Ingestion + Dashboard + Admin |
| `src/otterpi_smarthome/otterpi_store.py` | BatchStore (SQLite) |
| `src/otterpi_smarthome/dashboard.py` | Dashboard (Charts, 48h) |
| `src/otterpi_smarthome/dashboard_config.py` | Raum-/Gerätekonfiguration |
| `src/otterpi_smarthome/dashboard_constants.py` | Dashboard-Konstanten |
| `src/otterpi_smarthome/dashboard_data.py` | Dashboard-Datenfunktionen |
| `src/otterpi_smarthome/dashboard_charts.py` | Chart-/JS-Helfer |
| `src/otterpi_smarthome/admin.py` | Admin-UI (Tabs, JSON-Editor, Alert History) |
| `src/otterpi_smarthome/config_store.py` | JSON-Config-Verwaltung |
| `src/otterpi_smarthome/notifier.py` | Notifier (E-Mail, ntfy, Webhook) |
| `src/otterpi_smarthome/alert_store.py` | SQLite-Speicher für Alerts |
| `src/otterpi_smarthome/alert_engine.py` | Alert-Engine (Regeln, Dedup, Quiet Hours, Gateway-Heartbeat) |
| `src/otterpi_smarthome/heartbeat.py` | Gemeinsame Offline-Status-Logik |
| `src/otterpi_smarthome/sensor_schemas.py` | Zentrale Schema-Definition pro Sensor-Typ |
| `src/otterpi_smarthome/status.py` | Gemeinsame Status-/Violation-Logik |
| `src/otterpi_smarthome/archive_batches.py` | Batch- und Alert-Archivierung |
| `src/otterpi_smarthome/backup.py` | NAS-Backup (täglich, SQL-Dump) |

---

## Deployment

Die Anwendung wird aus dem GitHub-Repository `main` deployt.

```bash
# Update
sudo /usr/local/sbin/otterpi-smarthome-update smarthome

# Deinstallation (State/Config behalten)
sudo /usr/local/sbin/otterpi-smarthome-update uninstall

# Deinstallation mit Purge (State/Config löschen)
sudo /usr/local/sbin/otterpi-smarthome-update uninstall --purge
```

Nach erfolgreichem Deployment werden geschrieben:

```text
/opt/otterpi-smarthome/DEPLOYED_COMMIT    technischer Git-Commit
/opt/otterpi-smarthome/DEPLOYED_VERSION   menschenlesbare Version (z. B. v0.1.0)
/opt/otterpi-smarthome/VERSION            Version aus pyproject.toml
```

### Flache Deploy-Struktur

Die Installation kopiert die Dateien **flach** nach `/opt/otterpi-smarthome/`.
Da `model/` ein Unterverzeichnis ist, wird `PYTHONPATH` gesetzt:

```bash
PYTHONPATH=/opt/otterpi-smarthome:/opt/otterpi-smarthome/model
```

### Verzeichnisse

| Zweck | Pfad |
|---|---|
| Install | `/opt/otterpi-smarthome/` |
| Persistenz | `/var/lib/otterpi-smarthome/` |
| Datenbank | `/var/lib/otterpi-smarthome/smarthome.sqlite3` |
| Config | `/var/lib/otterpi-smarthome/config/` |
| Env | `/etc/otterpi-smarthome/smarthome.env` |
| Service | `otterpi-smarthome.observer.service` |

---

## Entwicklung

### Voraussetzungen

- Windows 11
- Visual Studio Code
- Python 3.13 (Entwicklung)
- Python 3.9 (minimale Unterstützung)

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --group dev
```

### Quality Gates

```powershell
ruff check .
ruff format --check .
pytest
git diff --check
```

Aktueller Stand: **442 Tests**, alle bestehen.

---

## Version

Aktuelle Version: **v0.1.5**

Die Version wird geführt über:

- `pyproject.toml` → `version = "0.1.5"`
- `src/otterpi_smarthome/__init__.py` → `__version__ = "0.1.5"`
- `src/otterpi_smarthome/dashboard_constants.py` → `VERSION = "v0.1.5"`
- Git-Tag `v0.1.5`

---

## Dokumentation

Weitere Dokumentation:

```text
docs/PROJECT-STATE.md
docs/development/DECISIONS.md
docs/development/DEVELOPMENT.md
docs/deployment/DEPLOYMENT.md
docs/weatherhub.md
```

---

## Lizenz

(Noch nicht festgelegt)