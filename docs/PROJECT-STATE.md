# OtterPi-SmartHome — Projektstatus

**Projekt:** OtterPi-SmartHome
**Rolle:** Privates, unabhängiges SmartHome-Monitoring auf dem OtterPi
**Abgrenzung:** Läuft parallel zu `loggerpi-otterpi` (dienstlich). Keine gemeinsame Datenbank, kein gemeinsamer Service, kein gemeinsames Dashboard.
**Stand:** 2026-11-18
**Version:** v0.1.5

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
| `smarthome.observer.service` | 8091 | `smarthome.sqlite3` | Privat (SmartHome) |

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
| Service | `smarthome.observer.service` |

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

**442 Tests, alle grün.** Ruff/Format clean.

---

## 5. Offen

### Phase 3 — Doku

- [x] `README.md`
- [x] `docs/PROJECT-STATE.md`
- [x] `docs/development/DECISIONS.md`
- [x] `docs/deployment/DEPLOYMENT.md`
- [x] `docs/development/DEVELOPMENT.md`
- [x] `docs/weatherhub.md`

### Phase 4 — Deploy

- [x] Repo auf GitHub pushen (`Lorc77/OtterPi-SmartHome`).
- [x] Auf dem OtterPi deployen (`sudo /usr/local/sbin/otterpi-smarthome-update smarthome`).
- [x] Verifikation (Service, DB, Dashboard, Admin).

### Phase 5 — Gateway konfigurieren

- [x] Gateway auf `192.168.178.100:3779` zeigen lassen.
- [x] Proxy-Modus aktivieren.
- [x] Cloud-Forward aktivieren (falls gewünscht).
- [x] Allowlist prüfen (`SMARTHOME_WEATHERHUB_ALLOWLIST`).

### Phase 6 — Verifizieren

- [x] Dashboard (`http://192.168.178.100:8091/`).
- [x] Admin (`http://192.168.178.100:8091/admin`).
- [x] Räume anlegen, Sensoren zuordnen.
- [x] Alarm Limits konfigurieren.
- [x] Mail/Notifications/Messages konfigurieren.
- [x] Datenbank wächst.
- [x] Cloud-Forward funktioniert.

---

## 6. Beantwortete Fragen

1. **Welche WeatherHub-Sensoren** gehen ins SmartHome? → ID01 (aktuell produktiv), ID03/ID0E/ID10 vorbereitet.
2. **Welche Räume/Geräte** sollen im Dashboard erscheinen? → 3 Räume, konfiguriert über Admin.
3. **Welche Alarm-Regeln** (Limits, States) sollen konfiguriert werden? → konfiguriert über Admin.
4. **Welche Notifier** (E-Mail, ntfy, Webhook)? → ntfy + E-Mail (Gmail).
5. **Welche Gateway-IP** ist die Allowlist? → `192.168.178.31`.
6. **Soll das SmartHome-Dashboard** auch loggerpi-otterpi-Daten zeigen? → Nein, zwei getrennte Dashboards.
7. **Soll das SmartHome** eine eigene Alert-Engine haben? → Ja, für SmartHome-Sensoren.
8. **Soll das SmartHome** eine eigene Archivierung haben? → Ja, gleicher Timer-Mechanismus.

---

## 7. Dateien

### Wiederverwendet (unverändert)

- `weatherhub_gateway_listener.py`
- `weatherhub_gateway_decoder.py`
- `weatherhub.py` (mit Erweiterung)
- `otterpi.py` (noch nicht umbenannt, siehe Phase 7)
- `otterpi_store.py` (noch nicht umbenannt, siehe Phase 7)
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
systemctl status smarthome.observer.service --no-pager
journalctl -u smarthome.observer.service -n 50 --no-pager
cat /opt/otterpi-smarthome/DEPLOYED_VERSION
ls -la /var/lib/otterpi-smarthome/
```

---

## 10. Nächster konkreter Schritt

**Phase 5.5 (nginx + Extern)** oder **Phase 7 (Refactoring)** — je nach Priorität.

Danach: Phase 8 (Serverseitige Aggregation).

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

#### Bugfixes (v0.1.1) ✅
- `archive_batches.py`: Pfade `/var/lib/loggerpi-otterpi/` → `/var/lib/otterpi-smarthome/`, Dateinamen `loggerpi-otterpi_*` → `otterpi-smarthome_*`.
- `backup.py`: `BACKUP_DIR` → `backups_otterpi-smarthome`, `DB_DIR` → `/var/lib/otterpi-smarthome`.
- `otterpi.py`: Bildpfad `/opt/loggerpi-otterpi/otter2.png` → `/opt/otterpi-smarthome/otter2.png`.
- `config_store.py`, `dashboard_config.py`, `dashboard_data.py`: `OTTERPI_CONFIG_DIR` → `SMARTHOME_CONFIG_DIR`.
- `admin.py`: Messages-Tab `loggerpi_offline`/`queue_depth`/`dead_letter` → `gateway_offline`.
- **424 Tests grün.**

#### CI-Fix (teilweise) 🟡
- `runs-on: ubuntu-22.04` eingetragen.
- **Noch offen:** Python-3.9-Job läuft noch in der Matrix. Entweder `ubuntu-22.04` beibehalten (dann läuft 3.9) oder auf 3.13-only umstellen (Phase 7).

#### Deploy (v0.1.2) ✅
- Repo auf GitHub gepusht.
- Tag `v0.1.2` gesetzt und gepusht.
- Auf dem OtterPi deployt (`sudo /usr/local/sbin/otterpi-smarthome-update smarthome`).
- Service läuft (`smarthome.observer.service`).
- Pakete kommen an (Batch mit Measurements und States in `smarthome.sqlite3`).

#### Gateway (v0.1.2) ✅
- Gateway sendet an `192.168.178.100:3779`.
- Proxy-Modus aktiv.
- Pakete kommen an (ID01-Sensoren mit `temperature_1`/`temperature_2`, `battery_low`-States).

#### Bugfixes (v0.1.2) ✅
- **`config/`-Verzeichnis in `install.sh`:** Wird jetzt explizit angelegt (`install -d -o makki -g makki -m 0750 /var/lib/otterpi-smarthome/config`). Vorher fehlte es, und beim ersten `save_*` schlug `tempfile.mkstemp` mit `PermissionError` fehl, wenn das Verzeichnis von `root` angelegt worden war.
- **`chmod`-Fixes auf dem OtterPi:** `config/` auf 0750, DBs und Sequence auf 0640 (manuell).
- **`smarthome_bridge.py`:** Schreibt jetzt auch `states` (nicht nur `measurements`).
- **`weatherhub.py`:** `measurements_from_packet` prüft `sensor_id in self._reception_times` (verhindert `stale` beim ersten Paket).
- **`otterpi_store.py`:** `created_at`-Spalte + Migration + Index.
- **`dashboard_data.py`:** SQL-Filter nach `created_at`.

#### Bugfixes (v0.1.3) ✅
- `backup.py`: DB-Name `batches.sqlite3` → `smarthome.sqlite3`, Env `OTTERPI_BACKUP_HEALTHCHECK_URL` → `SMARTHOME_BACKUP_HEALTHCHECK_URL`.
- `dashboard.py`/`dashboard_data.py`: `_system_metrics()` liest CPU-Temperatur und Memory direkt aus `/sys`/`/proc`.
- `dashboard.py`/`dashboard_data.py`: ID03 in `_device_measurement_keys`/`_device_current`/`_device_status` ergänzt.
- `admin.py`/`dashboard.py`: „ZOOLOGY-Observer" → „OtterPi-SmartHome", Dashboard-Icon `📡` → `🏡`.
- `weatherhub.py`/`smarthome_bridge.py`: `read_state(sensor_id)` filtert States auf das aktuelle Paket.
- `dashboard_data.py`: `_count_recent_batches()` für exakte „Packets (48h)"-Anzeige.
- `dashboard_data.py`: `_latest_batch_for_device()` — Übersicht und Raumklima zeigen jetzt alle Sensoren, nicht nur den letzten.
- `dashboard_data.py`/`dashboard.py`: Limits hochgesetzt (`_recent_batches` 192 → 5000, Detailseiten `hours * 4 + 100` → `hours * 30 + 100`).
- `notifier.py`: `EmailNotifier.send()` fällt bei leerem `routing.<severity>` auf `recipients` zurück (`self.routing.get(alert.severity) or self.recipients`).

#### Bugfixes (v0.1.4) ✅
- `weatherhub.py`: `read_state()` liefert jetzt auch `water_contact` (ID04) und `contact_open` (ID10).
- `dashboard.py`/`dashboard_data.py`: ID04 (Temperatur + Feuchte + Wasserkontakt) und ID10 (Tür-/Fensterkontakt, nur States) unterstützt.
- `dashboard_data.py`: `_latest_batch_for_device()` berücksichtigt jetzt auch States (für ID10, das keine Measurements hat).
- `dashboard_data.py`: `_device_chips()` zeigt `water_contact` und `contact_open` als Chips.
- `sensor_schemas.py`: `DASHBOARD_DEVICE_TYPES` (nur die im Dashboard unterstützten Typen).
- `admin.py`: „Add Device"-Dropdown zeigt nur noch `DASHBOARD_DEVICE_TYPES` (ID07 ausgeblendet).

#### Bugfixes (v0.1.5) ✅
- `weatherhub_gateway_decoder.py`: ID10 `previous`-Ereignisse (previous, previous 1, previous 2, previous 3) werden dekodiert.
- `weatherhub.py`: `read_state()` liefert für ID10 jetzt `contact_previous*_open`, `contact_previous*_since`, `counter`, `event_transmission`.
- `dashboard_data.py`: `_contact_events()` extrahiert die Kontakt-Ereignisse aus den States.
- `dashboard.py`: `_render_contact_events()` rendert die Ereignisse als Tabelle. Raumseite und Detailseite zeigen für ID10 statt Chart eine Ereignis-Tabelle.
- `dashboard_data.py`: `_device_chips()` zeigt für ID10 `counter` und `event_transmission` (Event/Heartbeat).

---

### Offen

#### Phase 5.5 — nginx + Extern-Vorbereitung
- [ ] nginx-Serverblock für `smarthome.makki.route64.de` → `127.0.0.1:8091`.
- [ ] TLS-Zertifikat (certbot).
- [ ] Basic Auth für `/admin` (`.htpasswd`).
- [ ] Rate Limiting (optional).
- [x] `SMARTHOME_HOST=0.0.0.0` für LAN-Zugriff (aktuell LAN-only).
- [ ] Verifikation: `https://smarthome.makki.route64.de/` und `/admin`.

#### Bugfix — `_validate_rooms` erlaubt leere `rooms` ✅
- [x] `config_store.py::_validate_rooms`: `if not isinstance(rooms, dict) or not rooms:` → `if not isinstance(rooms, dict):`. (DEC-018, umgesetzt.)

#### Phase 7 — Python 3.13-Modernisierung + Refactoring
- [ ] `pyproject.toml`: `requires-python = ">=3.13"`, `target-version = "py313"`, `FA102` weg, `per-file-ignores` weg.
- [ ] `.github/workflows/ci.yml`: nur Python 3.13 (dann kann `ubuntu-22.04` wieder auf `ubuntu-latest`).
- [ ] `docs/development/DEVELOPMENT.md`: Python 3.13 als Minimum.
- [ ] Code: `Optional[str]` → `str | None`, `Union[str, Path]` → `str | Path` (Ruff `UP` meckert sonst).
- [ ] Tests: `pytest` grün.
- [ ] **Refactoring (toter Code aus LoggerPi-OtterPi):**
  - [ ] `otterpi.py`: `POST /api/v1/batches` entfernen (ungenutzt, Daten kommen über WeatherHub-Listener).
  - [ ] `otterpi.py`: `GET /api/admin/latest-measurements` mit `connectivity` bereinigen.
  - [ ] `dashboard.py`: `_USB_NAMES`, `_render_led_svg` entfernen.
  - [ ] `dashboard.py`: `_device_measurement_keys` auf WeatherHub-only reduzieren.
  - [ ] `dashboard_data.py`: `_current_values` auf WeatherHub-only reduzieren.
  - [ ] `dashboard_data.py`: `_device_current`, `_device_status`, `_primary_measurement` auf WeatherHub-only reduzieren.
  - [ ] `dashboard_data.py`: `_ALARM_LABELS` entfernen.
  - [ ] `sensor_schemas.py`: `MEASUREMENT_DISPLAY_NAMES` `loggerpi_offline` → `gateway_offline`.
  - [ ] `smarthome_observer.py`: `SMARTHOME_CONFIG_DIR` explizit lesen (optional, Default ist okay).
  - [ ] `admin.py`: `connectivity`-Parameter aus `render_admin` entfernen (ungenutzt).
  - [ ] `sensor_schemas.py`: `temperature_3`, `temperature_4` aus `MEASUREMENT_DISPLAY_NAMES` entfernen (ungenutzt).
  - [ ] `config_store.py`: `stale_after_seconds` aus `_ALLOWED_LIMIT_KEYS` entfernen (nicht ausgewertet).
  - [ ] `otterpi.py` / `otterpi_store.py` umbenennen → `smarthome.py` / `smarthome_store.py` (betrifft `install.sh`, `smarthome_observer.py`, Tests).
- [ ] `weatherhub_id07` im Dashboard unterstützen (4 Measurements, eigene Karten-Logik).

#### Phase 8 — Serverseitige Aggregation für lange Zeiträume
- [ ] **Problem:** Detailseiten laden aktuell alle Batches in den RAM (bei 30d und 3 Sensoren ~20000 Pakete). Das ist RAM-intensiv und skaliert nicht.
- [ ] **Ziel:** Aggregation in SQL (`GROUP BY` Zeitfenster), sodass nur ~500 Punkte geladen werden statt ~20000.
- [ ] **Ansatz:**
  - [ ] Neue Funktion `_aggregated_series(store, key, hours, buckets=500)` in `dashboard_data.py`.
  - [ ] SQL: `SELECT strftime('%Y-%m-%dT%H:%M', created_at) AS bucket, AVG(json_extract(payload, '$.measurements.<key>.value')) FROM batches WHERE created_at >= ? GROUP BY bucket`.
  - [ ] `_render_device_detail` und `_render_climate_detail` auf `_aggregated_series` umstellen.
  - [ ] `_recent_batches`-Limit kann dann wieder sinken (z.B. 5000 bleibt für 48h-Übersicht).
- [ ] **Offen:** Wie mit `validity` (stale/invalid) in der Aggregation umgehen? (Nur `valid` zählen?)
- [ ] **Offen:** Downsampling-Intervall pro Zeitraum (z.B. 24h → 5 min, 7d → 1 h, 30d → 6 h).

---

### Nächster konkreter Schritt

**Phase 5.5 (nginx + Extern)** oder **Phase 7 (Refactoring)** — je nach Priorität.

Danach: Phase 8 (Serverseitige Aggregation).

**Hinweis:** Der CI-Fix (`ubuntu-22.04`) ist nur eine Zwischenlösung. Mit Phase 7 (3.13-only) kann `ubuntu-latest` wieder verwendet werden.
