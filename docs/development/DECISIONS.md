# OtterPi-SmartHome — Architekturentscheidungen

Dieses Dokument hält wichtige Entscheidungen fest, die während der
Vorbereitung und Implementierung des Projekts OtterPi-SmartHome getroffen
wurden.

Entscheidungen sollen kurz begründet und bei einer Änderung ihres
Status aktualisiert werden.

---

## DEC-001 — Eigenständiges Projekt, parallel zu LoggerPi-OtterPi

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

OtterPi-SmartHome ist ein privates SmartHome-Monitoring. Es soll parallel
zum dienstlichen LoggerPi-OtterPi laufen.

### Entscheidung

OtterPi-SmartHome ist ein eigenständiges Projekt mit eigener Datenbank,
eigenem Service und eigenem Dashboard. Keine gemeinsame Datenbank, kein
gemeinsamer Service, kein gemeinsames Dashboard.

### Begründung

Dienstlich und privat sollen getrennt bleiben. Kein gemeinsames Deployment,
keine gemeinsame Datenbank, kein gemeinsames Dashboard.

### Konsequenz

Zwei getrennte Services auf dem OtterPi:

| Service | Port | Datenbank | Zweck |
|---|---:|---|---|
| `otterpi.observer.service` | 8090 | `batches.sqlite3` | Dienstlich (LoggerPi) |
| `otterpi-smarthome.observer.service` | 8091 | `smarthome.sqlite3` | Privat (SmartHome) |

---

## DEC-002 — Gateway im selben Netz wie der OtterPi

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Das neue WeatherHub-Gateway ist auf `192.168.178.x` und kann direkt an den
OtterPi senden.

### Entscheidung

Das Gateway sendet direkt an `192.168.178.100:3779`. Kein Tunnel, kein
öffentlicher Endpoint nötig.

### Begründung

Das Gateway und der OtterPi sind im selben Netz. Ein Tunnel wäre unnötig.

### Konsequenz

- `SMARTHOME_WEATHERHUB_HOST=0.0.0.0`
- `SMARTHOME_WEATHERHUB_PORT=3779`
- `SMARTHOME_WEATHERHUB_ALLOWLIST=192.168.178.<gateway-ip>`

---

## DEC-003 — Cloud-Forward aktiv

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Das Gateway sendet normalerweise an `www.data199.com` (TFA-Cloud). Im
Proxymodus sendet es an den OtterPi.

### Entscheidung

Der `WeatherHubGatewayListener` sendet die Daten zusätzlich an
`www.data199.com` (Cloud-Forward). Der Cloud-Forward ist optional
(`SMARTHOME_CLOUD_FORWARD_ENABLED=1`).

### Begründung

Die TFA-Cloud soll weiterhin Daten bekommen (semi-redundanter Speicher).
Der Cloud-Forward ist im Listener schon eingebaut.

### Konsequenz

- `SMARTHOME_CLOUD_FORWARD_ENABLED=1`
- Cloud-Forward läuft asynchron (Thread), blockiert den lokalen Empfang nicht.

---

## DEC-004 — Kein Batch-Zirkus

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Im LoggerPi-OtterPi gibt es eine persistente Queue, Delivery, Retry,
Dead-Letter und einen LoggerPi-Runner. Die Daten kommen dort vom LoggerPi
über HTTP an.

### Entscheidung

Im SmartHome entfallen Queue, Delivery, Retry, Dead-Letter und
LoggerPi-Runner. Die Daten kommen direkt vom Gateway im OtterPi an. Der
`Batch` bleibt als Datencontainer, weil Dashboard/Admin/Alert-Engine darauf
aufbauen.

### Begründung

Die Daten kommen direkt im OtterPi an. Es gibt keinen LoggerPi, der die
Daten über HTTP sendet. Die `SmartHomeBridge` erzeugt den Batch direkt aus
dem Packet und speichert ihn.

### Konsequenz

- `batch_queue.py`, `delivery.py`, `runtime.py`, `loggerpi_runner.py`,
  `loggerpi_observer.py`, `composer.py`, `system_info.py` entfallen.
- `batch_factory.py` entfällt (teilweise — `SequenceStore` wird extrahiert).
- `SmartHomeBridge` (neu) erzeugt den Batch direkt aus dem Packet.

---

## DEC-005 — Package-Umbenennung `loggerpi_otterpi` → `otterpi_smarthome`

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Das Projekt heißt OtterPi-SmartHome, nicht LoggerPi-OtterPi.

### Entscheidung

Der Package-Ordner wird von `src/loggerpi_otterpi` in
`src/otterpi_smarthome` umbenannt.

### Begründung

Klarheit. Der Deploy ist flach (Imports ohne Package-Prefix), also ist die
Umbenennung nur:

- Ordner `src/loggerpi_otterpi` → `src/otterpi_smarthome`.
- `pyproject.toml` (Name, pythonpath).
- `__init__.py` (Docstring, Version).

Die Imports (`from batch_queue import ...`) bleiben unverändert.

### Konsequenz

- `pyproject.toml`: `name = "otterpi-smarthome"`, `pythonpath` angepasst.
- `__init__.py`: Docstring, Version `0.1.0`.
- `ruff`-`per-file-ignores` angepasst (`src/otterpi_smarthome/*.py`).

---

## DEC-006 — Persistente Sequence pro SmartHome-Logger

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Der `Batch` braucht eine `sequence`. Im LoggerPi-OtterPi wird sie über
`SequenceStore` in `batch_factory.py` verwaltet.

### Entscheidung

`SequenceStore` wird aus `batch_factory.py` extrahiert und in
`sequence_store.py` neu angelegt.

### Begründung

`batch_factory.py` entfällt (DEC-004), aber `SequenceStore` wird weiterhin
gebraucht.

### Konsequenz

- `sequence_store.py` (neu) mit `SequenceStore`.
- `smarthome_bridge.py` nutzt `SequenceStore`.

---

## DEC-007 — UI-Texte englisch

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Die UI-Texte im LoggerPi-OtterPi sind englisch.

### Entscheidung

Die UI-Texte im SmartHome bleiben englisch.

### Begründung

Konsistenz mit dem LoggerPi-OtterPi. Kein Übersetzungsaufwand.

### Konsequenz

- `heartbeat.py`: „No packet received yet", „Last packet X min ago",
  „Gateway offline for X min".
- `admin.py`: „Gateway offline detection", „Warning threshold (minutes)",
  „Critical threshold (minutes)", „Save System".
- `dashboard.py`: „Last packet", „Packets (48h)".

---

## DEC-008 — Deinstallation im `update.sh`

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Es soll ein Deinstallations-Skript geben.

### Entscheidung

Die Deinstallation ist im `update.sh` integriert (`uninstall` /
`uninstall --purge`), kein separates `uninstall.sh`.

### Begründung

Ein Skript, ein Einstiegspunkt. Weniger Dateien.

### Konsequenz

- `update.sh` hat eine neue Rolle `uninstall`.
- `uninstall` entfernt Service, Install-Dir, Update-Wrapper.
- `uninstall --purge` entfernt zusätzlich State (DB, Sequence) und Config.

---

## DEC-009 — `_DEFAULT_ROOMS = {}`

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Im LoggerPi-OtterPi gibt es eine feste `_DEFAULT_ROOMS`-Konfiguration mit
8 Räumen und 17 Sensoren.

### Entscheidung

Im SmartHome ist `_DEFAULT_ROOMS = {}`. Die Räume und Sensoren werden über
den Admin (`/admin` → Rooms-Tab) angelegt.

### Begründung

Die SmartHome-Sensoren sind noch nicht bekannt. Der Admin ist generisch
genug, um Räume und Sensoren anzulegen.

### Konsequenz

- `dashboard_config.py`: `_DEFAULT_ROOMS = {}`.
- Beim ersten Start ist das Dashboard leer.
- Räume und Sensoren werden über den Admin angelegt.

---

## DEC-010 — Gateway-Heartbeat statt LoggerPi-Heartbeat

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Im LoggerPi-OtterPi gibt es eine LoggerPi-Offline-Erkennung
(`loggerpi_offline_*`). Im SmartHome gibt es keinen LoggerPi, aber ein
Gateway.

### Entscheidung

Die Offline-Erkennung wird auf das Gateway umgestellt:
`gateway_offline_*` statt `loggerpi_offline_*`. Die Texte werden angepasst
(„Gateway offline" statt „LoggerPi offline").

### Begründung

Es gibt keinen LoggerPi. Das Gateway ist die Datenquelle.

### Konsequenz

- `heartbeat.py`: `gateway_offline_warning_seconds`,
  `gateway_offline_critical_seconds`.
- `alert_engine.py`: `_check_gateway_heartbeat` statt
  `_check_loggerpi_heartbeat`.
- `config_store.py`: `gateway_offline_*` in `_validate_alarm_limits`.
- `admin.py`: „Gateway offline detection".

---

## DEC-011 — Queue/Dead-Letter entfernt

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Im LoggerPi-OtterPi gibt es `connectivity.queue` im Batch und eine
Queue-/Dead-Letter-Überwachung in der Alert-Engine.

### Entscheidung

Im SmartHome entfallen `connectivity.queue`, `_check_connectivity` und die
Queue-/Dead-Letter-Schwellenwerte in `alarm_limits.json`.

### Begründung

Es gibt keine Queue und keinen Dead-Letter. Die Daten kommen direkt an.

### Konsequenz

- `alert_engine.py`: `_check_connectivity` entfernt.
- `config_store.py`: `queue_depth_*`/`dead_letter_*` entfernt.
- `admin.py`: Queue/Dead-Letter aus Header und System-Karte entfernt.
- `dashboard.py`: Queue/Dead-Letter aus System-Karte entfernt.

---

## DEC-012 — `created_at`-Spalte in der `batches`-Tabelle

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

`created_at` steckt im JSON-Payload, nicht in einer Spalte. Ein SQL-Filter
nach `created_at` ist daher nicht möglich.

### Entscheidung

Die Tabelle `batches` bekommt eine Spalte `created_at` (TEXT) und einen
Index `idx_batches_created_at`. `store()` schreibt `created_at` beim
Insert mit. Beim Start wird eine Migration ausgeführt: Bestehende Zeilen
ohne `created_at` werden aus dem Payload nachgezogen.

`_recent_batches` filtert einheitlich per SQL nach `created_at` — für
Buttons, Default und Custom-Range.

### Begründung

- **Korrektheit:** `created_at` ist die Messzeit, `received_at` die
  Empfangszeit. Bei verspäteten Batches ist `created_at` die richtige
  Grundlage.
- **Performance:** SQL-Filter mit Index ist schneller als Python-Filter.
- **RAM:** Nur die relevanten Batches werden geladen, nicht alle `limit`.

### Konsequenz

- `otterpi_store.py`: Schema + Migration + Index + `store()` erweitert.
- `dashboard_data.py`: `_recent_batches` filtert nach `created_at`.
- Tests: `test_otterpi_store.py`, `test_dashboard_data.py` erweitert.

---

## DEC-013 — `measurements_from_packet` im WeatherHubReader

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Der `WeatherHubReader` hat `read_measurements()`, das alle bekannten
Sensoren zurückgibt. Die `SmartHomeBridge` braucht aber nur die
Measurements eines einzelnen Pakets.

### Entscheidung

Der `WeatherHubReader` bekommt eine neue Methode
`measurements_from_packet(packet)`, die nur die Measurements eines
einzelnen Pakets liefert.

### Begründung

Die `SmartHomeBridge` verarbeitet ein Paket nach dem anderen. Sie braucht
nicht alle Sensoren, sondern nur das aktuelle Paket.

### Konsequenz

- `weatherhub.py`: `measurements_from_packet` (neu).
- `smarthome_bridge.py`: nutzt `measurements_from_packet`.
- `test_weatherhub.py`: 9 neue Tests.

---

## DEC-014 — `tzdata` als Dev-Dependency

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Windows hat keine Zeitzonen-Datenbank. `ZoneInfo("Europe/Berlin")` schlägt
fehl mit `ZoneInfoNotFoundError`.

### Entscheidung

`tzdata` wird als Dev-Dependency in `pyproject.toml` aufgenommen.

### Begründung

`tzdata` liefert die Zeitzonen-Datenbank für Windows. Ohne `tzdata`
schlagen die Tests fehl.

### Konsequenz

- `pyproject.toml`: `tzdata>=2024.1` in `[dependency-groups] dev`.
- `python -m pip install --group dev` installiert `tzdata`.

---

## DEC-015 — Pylance auf `off`

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Pylance meldet viele `reportOptionalMemberAccess`- und
`reportOptionalSubscript`-Fehler, die größtenteils False Positives sind
(z.B. `store.latest()` gibt `Optional[Batch]` zurück, aber der Test weiß,
dass es nicht `None` ist).

### Entscheidung

Pylance wird auf `off` gestellt (in `.vscode/settings.json`).

### Begründung

Ruff und pytest sind die echten Gates. Pylance ist strenger als nötig.
Die Typ-Prüfung ist ein Nice-to-have, kein Muss.

### Konsequenz

- `.vscode/settings.json`: `"python.analysis.typeCheckingMode": "off"`.
- `.vscode/settings.json`: `"python.analysis.extraPaths"` für die Imports.

---

## DEC-016 — Pfade, Config-Dir und Messages-Keys auf SmartHome umgestellt

**Status:** Accepted
**Datum:** 2026-11-17

### Kontext

Nach dem Kopieren aus LoggerPi-OtterPi waren noch mehrere Pfade und
Config-Keys auf LoggerPi-OtterPi ausgerichtet:

- `archive_batches.py` und `backup.py` verwendeten
  `/var/lib/loggerpi-otterpi/` statt `/var/lib/otterpi-smarthome/`.
- `otterpi.py` lud das Bild von `/opt/loggerpi-otterpi/otter2.png`.
- `config_store.py`, `dashboard_config.py`, `dashboard_data.py` lasen
  `OTTERPI_CONFIG_DIR` statt `SMARTHOME_CONFIG_DIR`.
- `admin.py` Messages-Tab zeigte `loggerpi_offline`, `queue_depth`,
  `dead_letter` statt `gateway_offline`.

### Entscheidung

Alle Pfade und Config-Keys werden auf SmartHome umgestellt:

- `archive_batches.py`: `DEFAULT_DATABASE`, `DEFAULT_ALERT_DATABASE`,
  `DEFAULT_ARCHIVE_DIR` → `/var/lib/otterpi-smarthome/`.
- `archive_batches.py`: Dateinamen `loggerpi-otterpi_*` →
  `otterpi-smarthome_*`.
- `backup.py`: `BACKUP_DIR` → `backups_otterpi-smarthome`, `DB_DIR` →
  `/var/lib/otterpi-smarthome`.
- `otterpi.py`: Bildpfad → `/opt/otterpi-smarthome/otter2.png`.
- `config_store.py`, `dashboard_config.py`, `dashboard_data.py`:
  `OTTERPI_CONFIG_DIR` → `SMARTHOME_CONFIG_DIR`.
- `admin.py`: Messages-Tab `loggerpi_offline`/`queue_depth`/`dead_letter`
  → `gateway_offline`.

### Begründung

Die Pfade und Keys waren Überbleibsel aus LoggerPi-OtterPi. Im SmartHome
gibt es keinen LoggerPi, keine Queue und keinen Dead-Letter. Die
Config-Keys müssen zu den Env-Variablen in `smarthome.env` passen.

### Konsequenz

- `archive_batches.py`, `backup.py`, `otterpi.py`, `config_store.py`,
  `dashboard_config.py`, `dashboard_data.py`, `admin.py` angepasst.
- Tests angepasst.
- **424 Tests grün.**

---

## DEC-017 — `install.sh` legt `config/`-Verzeichnis an

**Status:** Accepted
**Datum:** 2026-11-18

### Kontext

Beim ersten Deploy fehlte `/var/lib/otterpi-smarthome/config/`. Es wurde
erst beim ersten `save_*` durch `path.parent.mkdir(parents=True,
exist_ok=True)` in `_write_json_atomic` angelegt. Wenn das Verzeichnis
aber bereits existierte (z.B. von einem manuellen Test mit `sudo`) und
`root` gehörte, schlug `tempfile.mkstemp` mit `PermissionError` fehl.

### Entscheidung

`install.sh` legt `/var/lib/otterpi-smarthome/config/` explizit an:

```bash
install -d -o makki -g makki -m 0750 \
    /var/lib/otterpi-smarthome/config
```

### Begründung

- Das Verzeichnis gehört dann garantiert `makki:makki` mit 0750.
- Kein `PermissionError` beim ersten `save_*`.
- Kein manueller `chown` nach dem Deploy nötig.

### Konsequenz

- `deploy/smarthome/install.sh` erweitert.
- `docs/deployment/DEPLOYMENT.md` dokumentiert das Verzeichnis.

---

## DEC-018 — `_validate_rooms` erlaubt leere `rooms`

**Status:** Accepted
**Datum:** 2026-11-18

### Kontext

`_validate_rooms` in `config_store.py` verlangte ein nicht-leeres
`rooms`-Objekt:

```python
if not isinstance(rooms, dict) or not rooms:
    raise ConfigValidationError("rooms.json must contain a non-empty 'rooms' object.")
```

Da `_DEFAULT_ROOMS = {}` ist (DEC-009), schlug das erste Raum-Anlegen
über das Formular fehl (`rooms.json must contain a non-empty 'rooms'
object`).

### Entscheidung

`_validate_rooms` erlaubt leere `rooms`:

```python
if not isinstance(rooms, dict):
    raise ConfigValidationError("rooms.json must contain a 'rooms' object.")
```

### Begründung

- `_DEFAULT_ROOMS = {}` ist bewusst leer (DEC-009).
- Der erste Raum muss über das Formular angelegt werden können.
- Ein leeres `rooms`-Objekt ist ein valider Zustand (frischer Deploy).

### Konsequenz

- `config_store.py::_validate_rooms` angepasst.
- `tests/test_config_store.py` ggf. anpassen (Test für leeres `rooms`).

---

## DEC-019 — System-Metriken direkt aus `/proc` und `/sys`

**Status:** Accepted
**Datum:** 2026-11-18

### Kontext

CPU-Temperatur und Memory wurden aus dem Batch gelesen (`system`/`memory`), existieren im SmartHome-Batch aber nicht. Die Anzeige zeigte immer `0.0 °C` / `0%`.

### Entscheidung

`_system_metrics()` in `dashboard_data.py` liest die Werte direkt vom Host:
- CPU-Temperatur: `/sys/class/thermal/thermal_zone*/temp` (Milligrad)
- Memory: `/proc/meminfo` (`MemTotal`, `MemAvailable`)

Unter Windows (Tests) gibt die Funktion `None` zurück, die Anzeige zeigt „–".

### Konsequenz

- `dashboard_data.py`: `_system_metrics()` (neu).
- `dashboard.py`: `_render_overview` nutzt `_system_metrics()`.
- `_current_values` bereinigt (`cpu_temp`/`memory_used` raus).

---

## DEC-020 — `_latest_batch_for_device` für die Übersicht

**Status:** Accepted
**Datum:** 2026-11-18

### Kontext

Im SmartHome kommt jeder Sensor als eigener Batch. `_device_current`, `_device_status`, `_device_chips`, `_led_value` schauten in `batches[-1]` und fanden nur den zuletzt sendenden Sensor.

### Entscheidung

Neue Funktion `_latest_batch_for_device(batches, key)` findet den letzten Batch, der Measurements für `key` enthält. Die vier Funktionen nutzen sie statt `batches[-1]`.

### Konsequenz

- `dashboard_data.py`: `_latest_batch_for_device()` (neu).
- `_device_current`, `_device_status`, `_device_chips`, `_led_value` angepasst.
- Übersicht zeigt jetzt alle Sensoren.

---

## DEC-021 — Batch-Limits als Workaround hochgesetzt

**Status:** Accepted (Workaround)
**Datum:** 2026-11-18

### Kontext

`_recent_batches` lud max. 192 Batches (Annahme: 4/Stunde). Im SmartHome sendet jeder Sensor unabhängig (~24 Batches/Stunde bei 3 Sensoren). Die Charts waren lückenhaft.

### Entscheidung

- `_recent_batches`: `limit = 192` → `5000`.
- Detailseiten: `limit = hours * 4 + 100` → `hours * 30 + 100`.

### Konsequenz

- Charts zeigen mehr Daten.
- **Offen:** Serverseitige Aggregation (SQL `GROUP BY` Zeitfenster) für 30d+, um nicht ~20000 Pakete laden zu müssen.

---

## DEC-022 — ID04 und ID10 unterstützt

**Status:** Accepted
**Datum:** 2026-11-18

### Kontext

ID04 (Temperatur + Feuchte + Wasserkontakt) und ID10 (Tür-/Fensterkontakt) waren im Decoder vorbereitet, aber nicht im Dashboard. `read_state()` gab nur `battery_low` zurück.

### Entscheidung

- `read_state()` liefert jetzt auch `water_contact` (ID04) und `contact_open` (ID10).
- `_device_measurement_keys`, `_device_current`, `_device_status`, `_primary_measurement` behandeln ID04 wie ID03/ID0E.
- ID10 hat keine Measurements; `_device_measurement_keys` gibt `(None, None)` zurück, `_device_status` prüft nur States.
- `_latest_batch_for_device` berücksichtigt jetzt auch States (für ID10).

### Konsequenz

- ID04 zeigt Temperatur + Feuchte + Wasserkontakt-Chip.
- ID10 zeigt „–" für Temperatur (Anzeige kommt später), aber Status + Contact-Chip.
- ID07 bleibt vorerst außen vor (4 Measurements, eigene Karten-Logik nötig).

---

## DEC-023 — `DASHBOARD_DEVICE_TYPES` für Admin-Dropdown

**Status:** Accepted
**Datum:** 2026-11-18

### Kontext

Die „Add Device"-Dropdown im Admin zeigte alle Typen aus `SENSOR_SCHEMAS` — auch `weatherhub_id07`, das im Dashboard nicht funktioniert.

### Entscheidung

Neue Konstante `DASHBOARD_DEVICE_TYPES` in `sensor_schemas.py` mit den im Dashboard unterstützten Typen. `admin.py` verwendet sie für die Dropdown-Liste.

### Konsequenz

- `sensor_schemas.py`: `DASHBOARD_DEVICE_TYPES` (neu).
- `admin.py`: Dropdown nutzt `DASHBOARD_DEVICE_TYPES` statt `Object.keys(SENSOR_SCHEMAS)`.
- ID07 ist ausgeblendet, bis es im Dashboard unterstützt wird.

---

## DEC-024 — ID10 previous events, counter, heartbeat

**Status:** Accepted
**Datum:** 2026-11-18

### Kontext

ID10 liefert mehr als nur den aktuellen Kontakt-Zustand: die letzten 4 Zustandswechsel (`previous`, `previous 1`, `previous 2`, `previous 3`), `counter` und `event_transmission` (Heartbeat/Event).

### Entscheidung

- Decoder liest alle `previous`-Ereignisse.
- Reader gibt sie als States weiter (`contact_previous*_open`, `contact_previous*_since`).
- `counter` und `event_transmission` werden als States weitergegeben.
- Dashboard zeigt die Ereignisse als Tabelle (statt Chart) auf Raum- und Detailseite.
- `counter` und `event_transmission` werden als Chips angezeigt.

### Konsequenz

- ID10 zeigt jetzt: aktuellen Zustand, letzte 4 Ereignisse, Counter, Event/Heartbeat.
- Die Bedeutung von `event_transmission` (Event vs. Heartbeat) muss noch getestet werden.
- `previous 3` hat kein `time` (nur `sensor`), wird aber trotzdem angezeigt.

---

## Offene Entscheidungen

Folgende Punkte sind derzeit bewusst noch offen:

- Welche WeatherHub-Sensoren gehen ins SmartHome? (Sensor-IDs?)
- Welche Räume/Geräte sollen im Dashboard erscheinen?
- Welche Alarm-Regeln (Limits, States) sollen konfiguriert werden?
- Welche Notifier (E-Mail, ntfy, Webhook)?
- Welche Gateway-IP ist die Allowlist?
- Soll das SmartHome eine eigene Archivierung haben? (Ja, gleicher Timer-Mechanismus.)