# OtterPi-SmartHome — Projektstatus

**Projekt:** OtterPi-SmartHome
**Rolle:** Privates, unabhängiges SmartHome-Monitoring auf dem OtterPi
**Abgrenzung:** Läuft parallel zu `loggerpi-otterpi` (dienstlich). Keine gemeinsame Datenbank, kein gemeinsamer Service, kein gemeinsames Dashboard.
**Stand:** 2026-11-17
**Version:** v0.1.0

---

## 1. Ziel

Ein eigenständiger Service, der WeatherHub-Sensoren über ein eigenes Gateway
direkt empfängt, speichert, visualisiert und alarmiert — unabhängig vom
dienstlichen LoggerPi-OtterPi.

---

## 2. Architektur

```text
WeatherHub-Gateway (192.168.178.x)
    ↓
HTTP PUT (binär)
    ↓
OtterPi-SmartHome (192.168.178.100:3779)
    ↓
WeatherHubGatewayListener
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

## 3. Entscheidungen

### 3.1 Option B: Zwei Services (parallel)

`loggerpi-otterpi` bleibt unverändert. OtterPi-SmartHome läuft zusätzlich.

**Begründung:** Dienstlich und privat sollen getrennt bleiben. Kein
gemeinsames Deployment, keine gemeinsame Datenbank, kein gemeinsames
Dashboard.

### 3.2 Gateway im selben Netz wie der OtterPi

Das neue Gateway ist auf `192.168.178.x` und sendet direkt an
`192.168.178.100:3779`. Kein Tunnel, kein öffentlicher Endpoint nötig.

### 3.3 Cloud-Forward aktiv

Das Gateway sendet zusätzlich an `www.data199.com` (TFA-Cloud). Der
`WeatherHubGatewayListener` hat `cloud_forward_enabled` schon eingebaut.

### 3.4 Ports

| Zweck | Port |
|---|---:|
| HTTP (Dashboard/Admin) | 8091 |
| WeatherHub-Listener (TCP) | 3779 |

### 3.5 Verzeichnisse

| Zweck | Pfad |
|---|---|
| Install | `/opt/otterpi-smarthome/` |
| Persistenz | `/var/lib/otterpi-smarthome/` |
| Datenbank | `/var/lib/otterpi-smarthome/smarthome.sqlite3` |
| Config | `/var/lib/otterpi-smarthome/config/` |
| Env | `/etc/otterpi-smarthome/smarthome.env` |
| Service | `otterpi-smarthome.observer.service` |

### 3.6 Package-Name

`loggerpi_otterpi` → `otterpi_smarthome`.

**Warum?** Klarheit. Der Deploy ist flach (Imports ohne Package-Prefix),
also ist die Umbenennung nur:

- Ordner `src/loggerpi_otterpi` → `src/otterpi_smarthome`.
- `pyproject.toml` (Name, pythonpath).
- `__init__.py` (Docstring, Version).

Die Imports (`from batch_queue import ...`) bleiben unverändert.

### 3.7 Sequence

Persistente Sequence pro SmartHome-Logger, wie beim LoggerPi. Neue Datei
`sequence_store.py` mit `SequenceStore` (aus `batch_factory.py` extrahiert).

### 3.8 Kein Batch-Zirkus

Queue, Delivery, Retry, Dead-Letter, LoggerPi-Runner entfallen. Die Daten
kommen direkt im OtterPi an. Der `Batch` bleibt als Datencontainer, weil
Dashboard/Admin/Alert-Engine darauf aufbauen.

### 3.9 UI-Texte englisch

Die UI-Texte bleiben englisch (wie im LoggerPi-OtterPi).

### 3.10 Deinstallation im `update.sh`

Die Deinstallation ist im `update.sh` integriert (`uninstall` /
`uninstall --purge`), kein separates `uninstall.sh`.

---

## 4. Aktueller Stand

### Erledigt

- Repo kopiert, `.git`/`.venv`/`__pycache__` entfernt, `git init`.
- LoggerPi-Dateien entfernt (Code, Tests, `deploy/loggerpi/`).
- Package umbenannt: `loggerpi_otterpi` → `otterpi_smarthome`.
- `pyproject.toml` angepasst (`name`, `version`, `pythonpath`, `tzdata`).
- `__init__.py` angepasst (Docstring, Version `0.1.0`).
- `sequence_store.py` angelegt (extrahiert aus `batch_factory.py`).
- `smarthome_bridge.py` angelegt (Packet → Batch → Store).
- `smarthome_observer.py` angelegt (Einstiegspunkt).
- `weatherhub.py` um `measurements_from_packet` erweitert.
- `deploy/smarthome/install.sh` angelegt.
- `deploy/smarthome/smarthome.observer.service` angelegt.
- `deploy/smarthome/smarthome.env.example` angelegt.
- `deploy/update.sh` angepasst (Rolle `smarthome`, `uninstall`).
- `dashboard_config.py` auf `_DEFAULT_ROOMS = {}` gesetzt.
- `heartbeat.py` angepasst (`loggerpi_offline_*` → `gateway_offline_*`, „Batch" → „Packet").
- `admin.py` angepasst (Queue/Dead-Letter entfernt, `loggerpi_offline_*` → `gateway_offline_*`).
- `dashboard.py` angepasst (Queue/Dead-Letter entfernt, „Batch" → „Packet").
- `alert_engine.py` angepasst (`_check_loggerpi_heartbeat` → `_check_gateway_heartbeat`, `_check_connectivity` entfernt).
- `sensor_schemas.py` angepasst (AtmoWEB/Freezer/MEMMERT entfernt, WeatherHub bleibt inkl. ID10).
- `config_store.py` angepasst (`loggerpi_offline` → `gateway_offline`, Queue/Dead-Letter entfernt).
- Tests angepasst (`test_dashboard.py`, `test_dashboard_data.py`, `test_alert_engine.py`, `test_otterpi.py`, `test_otterpi_store.py`, `test_admin.py`, `test_sensor_schemas.py`, `test_config_store.py`, `test_heartbeat.py`).
- Neue Tests: `test_sequence_store.py`, `test_smarthome_bridge.py`, `test_weatherhub.py`.
- `README.md` angelegt.

### Teststand

**429 Tests, alle grün.** Ruff/Format clean.

---

## 5. Offen

### Phase 3 — Doku (in Arbeit)

- [x] `README.md`
- [x] `docs/PROJECT-STATE.md`
- [ ] `docs/development/DECISIONS.md`
- [ ] `docs/deployment/DEPLOYMENT.md`
- [ ] `docs/development/DEVELOPMENT.md`
- [ ] `docs/weatherhub.md`

### Phase 4 — Deploy

- [ ] Repo auf GitHub pushen (`Lorc77/OtterPi-SmartHome`).
- [ ] Auf dem OtterPi deployen (`sudo /usr/local/sbin/otterpi-smarthome-update smarthome`).
- [ ] Verifikation (Service, DB, Dashboard, Admin).

### Phase 5 — Gateway konfigurieren

- [ ] Gateway auf `192.168.178.100:3779` zeigen lassen.
- [ ] Proxy-Modus aktivieren.
- [ ] Cloud-Forward aktivieren (falls gewünscht).
- [ ] Allowlist prüfen (`SMARTHOME_WEATHERHUB_ALLOWLIST`).

### Phase 6 — Verifizieren

- [ ] Dashboard (`http://192.168.178.100:8091/`).
- [ ] Admin (`http://192.168.178.100:8091/admin`).
- [ ] Räume anlegen, Sensoren zuordnen.
- [ ] Alarm Limits konfigurieren.
- [ ] Mail/Notifications/Messages konfigurieren.
- [ ] Datenbank wächst.
- [ ] Cloud-Forward funktioniert.

---

## 6. Offene Fragen

1. **Welche WeatherHub-Sensoren** gehen ins SmartHome? (Sensor-IDs?)
2. **Welche Räume/Geräte** sollen im Dashboard erscheinen?
3. **Welche Alarm-Regeln** (Limits, States) sollen konfiguriert werden?
4. **Welche Notifier** (E-Mail, ntfy, Webhook)?
5. **Welche Gateway-IP** ist die Allowlist?
6. **Soll das SmartHome-Dashboard** auch loggerpi-otterpi-Daten zeigen? (Aktuell: nein, zwei getrennte Dashboards.)
7. **Soll das SmartHome** eine eigene Alert-Engine haben? (Ja, für SmartHome-Sensoren.)
8. **Soll das SmartHome** eine eigene Archivierung haben? (Ja, gleicher Timer-Mechanismus.)

---

## 7. Dateien

### Wiederverwendet (unverändert)

- `weatherhub_gateway_listener.py`
- `weatherhub_gateway_decoder.py`
- `weatherhub.py` (mit Erweiterung)
- `otterpi.py` → `smarthome.py`
- `otterpi_store.py` → `smarthome_store.py`
- `dashboard.py`, `dashboard_config.py`, `dashboard_constants.py`, `dashboard_data.py`, `dashboard_charts.py`
- `admin.py`, `config_store.py`, `notifier.py`
- `alert_store.py`, `alert_engine.py`, `heartbeat.py`
- `sensor_schemas.py`, `archive_batches.py`
- `model/batch.py`, `model/measurement.py`

### Neu

- `sequence_store.py`
- `smarthome_bridge.py`
- `smarthome_observer.py`

### Angepasst

- `pyproject.toml`
- `README.md`
- `deploy/smarthome/install.sh`
- `deploy/smarthome/smarthome.observer.service`
- `deploy/smarthome/smarthome.env.example`
- `deploy/update.sh`
- `dashboard_config.py` (SmartHome-Sensoren)
- Tests

---

## 8. Testing

### Unit-Tests

- `test_smarthome_bridge.py`: Packet → Batch → Store.
- `test_sequence_store.py`: persistente Sequence.
- `test_weatherhub.py`: `measurements_from_packet`.

### Integration

- Gateway → Listener → Bridge → Store.
- Dashboard zeigt SmartHome-Sensoren.
- Admin speichert Config.

### Manuell

- Gateway sendet an `192.168.178.100:3779`.
- Dashboard zeigt Daten.
- Cloud-Forward funktioniert.

---

## 9. Deployment

### Reihenfolge

1. Repo auf GitHub pushen.
2. Auf dem OtterPi: `sudo /usr/local/sbin/otterpi-smarthome-update smarthome`.
3. Gateway konfigurieren.
4. Verifizieren.

### Verifikation

```bash
systemctl status otterpi-smarthome.observer.service --no-pager
journalctl -u otterpi-smarthome.observer.service -n 50 --no-pager
cat /opt/otterpi-smarthome/DEPLOYED_VERSION
ls -la /var/lib/otterpi-smarthome/
```

---

## 10. Nächster konkreter Schritt

**Phase 3:** `docs/development/DECISIONS.md` anlegen.

Danach: `docs/deployment/DEPLOYMENT.md`, `docs/development/DEVELOPMENT.md`, `docs/weatherhub.md`.

Dann: Phase 4 (Deploy), Phase 5 (Gateway), Phase 6 (Verifizieren).

---

## 11. Fahrplan

### Erledigt

#### Phase 1 — Texte anpassen ✅
- `heartbeat.py`: `loggerpi_offline_*` → `gateway_offline_*`, „Batch" → „Packet", „LoggerPi" → „Gateway".
- `admin.py`: Queue/Dead-Letter entfernt, `loggerpi_offline_*` → `gateway_offline_*`.
- `dashboard.py`: Queue/Dead-Letter entfernt, „Batch" → „Packet".
- `alert_engine.py`: `_check_loggerpi_heartbeat` → `_check_gateway_heartbeat`, `_check_connectivity` entfernt.
- `sensor_schemas.py`: AtmoWEB/Freezer/MEMMERT entfernt, WeatherHub bleibt inkl. ID10.
- `config_store.py`: `loggerpi_offline` → `gateway_offline`, Queue/Dead-Letter entfernt.

#### Phase 2 — Tests anpassen ✅
- Bestehende Tests angepasst.
- Neue Tests: `test_sequence_store.py`, `test_smarthome_bridge.py`, `test_weatherhub.py`.
- **424 Tests grün.**

#### Phase 3 — Doku ✅
- `README.md`, `docs/PROJECT-STATE.md`, `docs/development/DECISIONS.md`, `docs/deployment/DEPLOYMENT.md`, `docs/development/DEVELOPMENT.md`, `docs/weatherhub.md`.

#### Repo-Aufräumen ✅
- `docs/research/`, `docs/legacy/`, `docs/baselines/`, `docs/api/`, `docs/data-model/` entfernt.
- `docs/system-inventory.md`, `docs/WIEDEREINSTIEG.md`, `docs/development/DEVELOPMENT-ENVIRONMENT.md`, `docs/development/DEVELOPMENT-QUALITY.md`, `docs/development/REFACTORING.md` entfernt.
- `deploy/otterpi/` entfernt.
- `src/otterpi_smarthome/otterpi_observer.py` + `tests/test_otterpi_observer.py` entfernt.
- `deploy/smarthome/` um `smarthome-archive-batches.service`/`.timer` und `smarthome-backup.service`/`.timer` erweitert.
- `install.sh` um Timer-Installation erweitert.

#### Git ✅
- Repo auf GitHub gepusht (`Lorc77/OtterPi-SmartHome`).
- Tag `v0.1.0` gesetzt und gepusht.

#### CI-Fix (teilweise) 🟡
- `runs-on: ubuntu-22.04` eingetragen.
- **Noch offen:** Python-3.9-Job läuft noch in der Matrix. Entweder `ubuntu-22.04` beibehalten (dann läuft 3.9) oder auf 3.13-only umstellen (Phase 7).

---

### Offen

#### Phase 4 — Deploy (in Arbeit)
- [ ] `sudo /usr/local/sbin/otterpi-smarthome-update smarthome`
- [ ] Verifikation: `systemctl status`, `DEPLOYED_VERSION`, `ls -la /var/lib/otterpi-smarthome/`, `journalctl`

#### Phase 5 — Gateway konfigurieren
- [ ] Gateway auf `192.168.178.100:3779` zeigen lassen.
- [ ] Proxy-Modus aktivieren.
- [ ] Cloud-Forward aktivieren (falls gewünscht).
- [ ] Allowlist prüfen (`SMARTHOME_WEATHERHUB_ALLOWLIST`).

#### Phase 6 — Verifizieren
- [ ] Dashboard (`http://192.168.178.100:8091/`).
- [ ] Admin (`http://192.168.178.100:8091/admin`).
- [ ] Räume anlegen, Sensoren zuordnen.
- [ ] Alarm Limits konfigurieren.
- [ ] Mail/Notifications/Messages konfigurieren.
- [ ] Datenbank wächst.
- [ ] Cloud-Forward funktioniert.

#### Phase 7 — Python 3.13-Modernisierung (neu)
- [ ] `pyproject.toml`: `requires-python = ">=3.13"`, `target-version = "py313"`, `FA102` weg, `per-file-ignores` weg.
- [ ] `.github/workflows/ci.yml`: nur Python 3.13 (dann kann `ubuntu-22.04` wieder auf `ubuntu-latest`).
- [ ] `docs/development/DEVELOPMENT.md`: Python 3.13 als Minimum.
- [ ] Code: `Optional[str]` → `str | None`, `Union[str, Path]` → `str | Path` (Ruff `UP` meckert sonst).
- [ ] Tests: `pytest` grün.

---

### Nächster konkreter Schritt

**Phase 4:** Deploy auf dem OtterPi (`sudo /usr/local/sbin/otterpi-smarthome-update smarthome`).

Danach: Phase 5 (Gateway), Phase 6 (Verifizieren), Phase 7 (Python 3.13-Modernisierung).

**Hinweis:** Der CI-Fix (`ubuntu-22.04`) ist nur eine Zwischenlösung. Mit Phase 7 (3.13-only) kann `ubuntu-latest` wieder verwendet werden.