# Refactoring-Block – LoggerPi-OtterPi

**Status:** Phase 1 (v1.14.5), Phase 2 (v1.14.6), Phase 3a (v1.14.6), Phase 3b (v1.14.7), Phase 4a (v1.14.8) und Phase 4b (v1.15.0) abgeschlossen.
**Ziel:** Alle bekannten und neu gefundenen Duplikate, toten Codepfade und
Performance-Optimierungen in einem zusammenhängenden Block erledigen.

---

## Sicherheits- und Testkonzept

### Vor jeder Phase

- Baseline: `pytest`, `ruff check .`, `ruff format --check .` grün.
- `grep` nach allen Usages des zu ändernden Symbols:
  ```powershell
  Get-ChildItem -Path src, tests -Recurse -File | Select-String -Pattern "<symbol>"
  ```
- Teststand notieren (z. B. `605 passed`). Nach der Phase muss die Zahl gleich
  (oder höher bei neuen Tests) sein. Sinkt sie, wurde ein Test versehentlich
  entfernt.

### Während der Phase

- Eine Datei nach der anderen.
- Nach jeder Datei: `pytest` + `ruff check .`.
- Nach der Phase: `git diff` reviewen.
- Bei Dashboard-/UI-Änderungen: manuell im Browser prüfen. Tests decken das
  visuelle Verhalten nicht ab.

### Variablen-Shadowing (Lesson Learned v1.14.6)

Beim Verschieben von Code prüfen, ob der Variablenname im selben Scope nochmal
verwendet wird. `current` war in `_render_overview` doppelt belegt (global +
Geräte-Schleife). Die Tests haben es gefangen, aber ein `grep` vorher hätte es
auch gefangen.

**Regel:** Vor dem Verschieben einer Zeile mit `X = ...`:

```powershell
Select-String -Path <datei> -Pattern "\bX\b"
```

### Nach der Phase

- `pytest`, `ruff check .`, `ruff format --check .`.
- `git status` prüfen: nur beabsichtigte Dateien staged.
- `git diff --check`: keine Whitespace-Fehler.
- Commit + Push.
- Deploy + Verifikation auf OtterPi.

### Für Phase 4 (große Duplikate)

- Branch `refactor/phase-4`.
- Tests grün, Review, dann Merge.

### Wenn's schiefgeht

- `git reset --soft HEAD~1` (behält Änderungen)
- `git reset --hard HEAD~1` (wirft weg)
- `git revert <commit>`

### Lessons Learned (v1.14.6)

- **`timedelta` in `alert_store.py`:** Beim Entfernen von `include_older_active` wurde `timedelta` aus dem Import gestrichen, obwohl `count_by_day` es noch nutzt. Pylance hat es gefangen, bevor es committed wurde.
- **Lehre:** Nach **jeder** Änderung `ruff check .` laufen lassen, nicht nur am Ende der Datei. `ruff` fängt `F401` (unused import) und `F821` (undefined name).
- **Zusätzliches Gate:** Pylance im Editor als zweites Sicherheitsnetz.

---

## Phase 1 – Kleine Duplikate (✅ abgeschlossen, v1.14.5)

### Ziel

Drei Konstanten/Logiken, die an mehreren Stellen definiert waren, in eine
gemeinsame Quelle überführen.

### Änderungen

#### 1. `UNIT_LABELS` → `sensor_schemas.py`

**Vorher:**
- `alert_engine.py`: lokale `UNIT_LABELS`-Definition (Python).
- `admin.py`: lokale `UNIT_LABELS`-Definition (JavaScript in `buildDeviceContent`).

**Nachher:**
- `sensor_schemas.py`: `UNIT_LABELS` (Python-Dict, eine Quelle).
- `alert_engine.py`: `from sensor_schemas import UNIT_LABELS`.
- `admin.py`: `from sensor_schemas import UNIT_LABELS`, Injektion via
  `json.dumps(UNIT_LABELS)` in die JS-Konstante
  `const UNIT_LABELS = {unit_labels_json};`.

**Dateien:**
- `src/loggerpi_otterpi/sensor_schemas.py` (+7 Zeilen)
- `src/loggerpi_otterpi/alert_engine.py` (Import statt lokaler Definition)
- `src/loggerpi_otterpi/admin.py` (Import + `unit_labels_json` + JS-Injektion)

#### 2. `MEASUREMENT_DISPLAY_NAMES` → `sensor_schemas.py`

**Vorher:**
- `sensor_schemas.py`: `MEASUREMENT_DISPLAY_NAMES` (bereits vorhanden).
- `dashboard_data.py::_device_chips`: lokale `display_name`-Map.

**Nachher:**
- `dashboard_data.py`: `from sensor_schemas import MEASUREMENT_DISPLAY_NAMES`,
  `display_name = MEASUREMENT_DISPLAY_NAMES.get(measurement_name, measurement_name)`.

**Dateien:**
- `src/loggerpi_otterpi/dashboard_data.py` (Import + Ersetzung)

**Hinweis:** `fan_speed` ändert sich von `"Fan Speed"` zu `"Fan speed"`
(konsistent mit `alert_engine.py`).

#### 3. Offline-Thresholds → `heartbeat.py`

**Vorher:**
- `dashboard.py::_offline_thresholds()`: liest `alarm_limits.json`.
- `alert_engine.py::_check_loggerpi_heartbeat()`: liest `system_config`.
- `admin.py::render_admin()`: liest `system_config`.

**Nachher:**
- `heartbeat.py::load_offline_thresholds(system_config=None)`:
  - Ohne Argument: liest `alarm_limits.json`.
  - Mit Argument: liest aus dem übergebenen Dict.
- `dashboard.py`: `load_offline_thresholds()`.
- `alert_engine.py`: `load_offline_thresholds(system_config)`.
- `admin.py`: `load_offline_thresholds(system_config)`.

**Dateien:**
- `src/loggerpi_otterpi/heartbeat.py` (+16 Zeilen)
- `src/loggerpi_otterpi/dashboard.py` (Import + Aufruf, `_offline_thresholds` entfernt)
- `src/loggerpi_otterpi/alert_engine.py` (Import + Aufruf)
- `src/loggerpi_otterpi/admin.py` (Import + Aufruf)

### Teststand

- 560 Tests grün.
- `ruff check .` + `ruff format --check .` clean.

---

## Phase 2 – Aufräumen (✅ abgeschlossen, v1.14.6)

### Ziel

Toten Code, tote CSS-Klassen und ungenutzte Config entfernen.

### Geänderte Dateien (Übersicht)

| Datei | Änderung | Zeilen |
|---|---|---|
| `src/loggerpi_otterpi/dashboard_data.py` | 3 tote Funktionen entfernt | ~15 |
| `src/loggerpi_otterpi/admin.py` | 9 tote CSS-Klassen entfernt | ~50 |
| `src/loggerpi_otterpi/otterpi.py` | `include_older_active` entfernt | ~5 |
| `src/loggerpi_otterpi/alert_store.py` | `include_older_active` entfernt | ~10 |
| `tests/test_alert_store.py` | `test_include_older_active` entfernt | ~7 |
| `tests/test_admin.py` | Flaky Windows-Test gefixt | ~3 |
| `deploy/loggerpi/loggerpi.env.example` | `LOGGERPI_STATE_DIR` entfernt | 1 |
| `deploy/otterpi/otterpi.env.example` | `OTTERPI_STATE_DIR` entfernt | 1 |

**Nicht geändert:** `deploy/otterpi/archive-batches.service` – `WantedBy` war bereits in einem früheren Fix entfernt.

### Änderungen im Detail

#### 1. Tote Funktionen in `dashboard_data.py`

**Entfernt:**
- `_latest_states(batches, device_key)` – nicht mehr verwendet.
- `_latest_setpoints(batches, device_key)` – nicht mehr verwendet.
- `_latest_serial(batches)` – nicht mehr verwendet.

**Behalten:**
- `_latest_batch(batches)` – wird von `_latest_device` genutzt.
- `_latest_device(batches, device_key)` – wird von `_render_device_detail` genutzt.

**Datei:** `src/loggerpi_otterpi/dashboard_data.py` (~15 Zeilen entfernt).

**Sicherheitscheck:** `grep` nach den drei Symbolen → nur in `dashboard_data.py` selbst. Keine externen Usages.

#### 2. Tote CSS-Klassen in `admin.py`

**Entfernt:**
- `.alert-card`
- `.alert-header`
- `.alert-header strong`
- `.alert-severity`
- `.alert-severity-critical`
- `.alert-severity-warn`
- `.alert-meta`
- `.alert-message`
- `.alerts-list` (class, nicht ID)

**Behalten:**
- `.alert-severity-badge` + `.critical` / `.warning` (in `renderAlertRow` genutzt)
- `.alert-actions`, `.alert-ack`, `.alert-resolved`, `.alert-active`
- `id="alerts-list"` (HTML-ID, nicht class)

**Datei:** `src/loggerpi_otterpi/admin.py` (~50 Zeilen entfernt).

**Sicherheitscheck:** `grep` nach den Klassen → nur in `admin.py` selbst (CSS-Definitionen). Keine `class="..."` im HTML/JS.

#### 3. `include_older_active` entfernt

**Entfernt aus:**
- `otterpi.py`: Query-Param-Parsing, Variable-Init, Call-Argumente in `list_alerts` und `count_alerts`.
- `alert_store.py`: Parameter in `_build_where`, `list_alerts`, `count_alerts`; der `if include_older_active:`-Block in `_build_where`.
- `tests/test_alert_store.py`: `test_include_older_active` in `TestBuildWhere`.

**Reihenfolge (wichtig):** Erst `otterpi.py` (Caller), dann `alert_store.py` (Callee), dann Test. Sonst `TypeError: unexpected keyword argument`.

**Dateien:**
- `src/loggerpi_otterpi/otterpi.py`
- `src/loggerpi_otterpi/alert_store.py`
- `tests/test_alert_store.py`

**Sicherheitscheck:** `grep` nach `include_older_active` → nach der Änderung leer.

**Hinweis:** `timedelta` bleibt im Import von `alert_store.py`, weil `count_by_day` es nutzt. (Kurzzeitig entfernt, von Pylance gefangen, wiederhergestellt.)

#### 4. `LOGGERPI_STATE_DIR` / `OTTERPI_STATE_DIR` entfernt

**Entfernt aus:**
- `deploy/loggerpi/loggerpi.env.example`: `LOGGERPI_STATE_DIR=/var/lib/loggerpi-otterpi`
- `deploy/otterpi/otterpi.env.example`: `OTTERPI_STATE_DIR=/var/lib/loggerpi-otterpi`

**Grund:** Werden im Code nicht gelesen.

**Deployment-Note:** Die produktiven `/etc/loggerpi-otterpi/*.env` auf den Zielsystemen haben die Zeilen auch. Manuell entfernen (nicht kritisch, Code liest sie nicht).

**Dateien:**
- `deploy/loggerpi/loggerpi.env.example`
- `deploy/otterpi/otterpi.env.example`

#### 5. `WantedBy` in `archive-batches.service`

**Status:** Bereits in einem früheren Fix entfernt. Kein Change in Phase 2.

**Grund:** Der Service wird nur per Timer gestartet, nicht beim Boot.

#### 6. Flaky Windows-Test gefixt

**Problem:** `test_put_unknown_returns_404` in `tests/test_admin.py` schlug unter Windows sporadisch mit `ConnectionAbortedError` fehl.

**Fix:** `except ConnectionAbortedError: pass` ergänzt (analog zu `test_otterpi.py`).

**Datei:** `tests/test_admin.py`

### Teststand

- **559 Tests grün** (ein Test weniger: `test_include_older_active` entfernt).
- `ruff check .` + `ruff format --check .` clean.

### Nächster Schritt

Phase 3 (Kleine Performance-Optimierungen).

---

## Phase 3 – Kleine Performance-Optimierungen (Phase 3a ✅, Phase 3b ✅)

### Ziel

~10–20 % CPU pro Dashboard-Render sparen.

### Phase 3a – Abgeschlossen (v1.14.6)

#### 1. `_current_values(batches)` aus der Raum-Schleife ziehen ✅

- `dashboard.py::_render_overview`: `system_current = _current_values(batches)` vor die Schleife.
- Variable umbenannt (`current` → `system_current`), weil `current` in der Geräte-Schleife
  für `_device_current()` wiederverwendet wird (Shadowing).

#### 2. `last_update` aus der Raum-Schleife ziehen ✅

- `dashboard.py::_render_overview`: `last_update = system_current["last_batch"]` vor die Schleife.

**Teststand:** 559 Tests grün.

**Lesson Learned (Variablen-Shadowing):** `current` war doppelt belegt (global +
Geräte-Schleife). Beim Verschieben von Code prüfen, ob der Variablenname im selben
Scope nochmal verwendet wird. `grep` vor dem Verschieben hätte es gefangen.

### Phase 3b – Abgeschlossen (v1.14.7)

#### 6. `series_by_device` dynamisch statt hardcodiert ✅

- `dashboard.py::_render_room_detail`: hardcodierte Keys (`atmoweb_101`, `freezer`, …)
  durch `_device_series` ersetzt.
- Neue Helper `_device_measurement_keys(device)` und `_device_series(batches, device)`.
- `_render_device_detail` nutzt `_device_measurement_keys(device_info)`.

#### 7. `_render_device_detail` Datasets als Liste statt String ✅

- `dashboard.py`: `limit_datasets` und `legend_datasets` als Liste + `"".join`.
- Template nutzt `{limit_datasets_str}{legend_datasets_str}`.

#### 8. `_render_climate_detail` Datasets als Liste statt String ✅

- `dashboard.py`: `temp_sensor_datasets` und `hum_sensor_datasets` waren bereits
  Listen + `",\n".join`. Kein Change nötig.

### Nicht umgesetzt (marginal)

#### 3. `_device_limits` cachen (pro Render) ❌

- **Grund:** `_load_alarm_limits_cached()` ist bereits mtime-gecacht. Der zusätzliche
  Cache spart ~12 `stat()` + 552 Iterationen → ~1 ms. Nicht worth it.

#### 4. `_recent_batches` cachen (pro Render) ❌

- **Grund:** `_recent_batches` wird **einmal** pro Render aufgerufen (jede Render-Funktion
  ruft es genau einmal). Kein mehrfacher Aufruf → kein Cache nötig.

#### 5. `_series` cachen (pro Render) ❌

- **Grund:** Jeder `_series`-Aufruf hat einen **anderen** Key (`atmoweb_101.temperature_1`,
  `atmoweb_101.humidity`, …). Ein Cache würde nie greifen.

### Sicherheitscheck

- `pytest` nach jeder Datei.
- Dashboard manuell prüfen (visuell).
- **Neu:** Vor dem Verschieben einer Zeile mit `X = ...` prüfen, ob `X` im selben Scope
  nochmal verwendet wird (`grep`).

---

## Phase 4 – Große Duplikate (Phase 4a ✅, Phase 4b ✅)

**Status:** ✅ Abgeschlossen (v1.14.8 + v1.15.0).
**Ziel:** Alert-Logik und Chart-Logik vereinheitlichen – **ohne Verhaltensänderung**.
**Prinzip:** Reines Refactoring. Keine neuen Features, keine geänderten Schwellen,
keine geänderten Texte, keine geänderten Chips, keine geänderten Charts.

## Phase 4b – Chart-Logik (✅ abgeschlossen, v1.15.0)

**Status:** ✅ Abgeschlossen (v1.15.0).
**Branch:** `refactor/phase-4b` (von `main`, Stand v1.14.8).
**Ziel:** `_render_device_script` (in `dashboard_charts.py`) und
`_render_device_detail` (in `dashboard.py`) teilen die Chart.js-Logik
über eine gemeinsame Funktion `_render_chart_script`.
**Prinzip:** Reines Refactoring. Keine Verhaltensänderung an den Charts.

### Wichtig: `_render_climate_detail` bleibt unverändert

Die vier Climate-Charts (Average Temperature, Average Humidity, Individual
Sensors Temperature, Individual Sensors Humidity) werden aus separaten
Werten gebildet und sind zu unterschiedlich für eine gemeinsame Funktion.
Sie bleiben wie sie sind.

### Ansatz: Option B (vollständige Vereinheitlichung)

`_render_chart_script` deckt **beide** Fälle ab:

- **Temperature + Humidity** (atmoweb, weatherhub_id0e): `hasHumidity=True`.
- **Temperature only** (freezer, memmert, weatherhub_id01): `hasHumidity=False`
  (leeres `hum_values_json`).

Der bisherige separate Temperature-only-Branch in `_render_device_script`
entfällt. `_render_device_script` wird ein dünner Wrapper.

### Die Unterschiede zwischen den beiden Funktionen

| Unterschied | `_render_device_script` | `_render_device_detail` | Lösung |
|---|---|---|---|
| Variablen-Präfix | `{chart_var}` | `temp`/`hum`/kein | Parameter `chart_var` |
| Temperature-only | eigener Branch | `hasHumidity` | `hasHumidity=False` |
| Legend-Filter | `startsWith` | exakter Vergleich | Parameter `legend_filter` |
| Legend-`onClick` | nein | ja | Parameter `legend_onclick` |
| Legend-Datasets | nein | ja | Parameter `legend_datasets` |
| Humidity-Achse | immer | nur bei `hasHumidity` | immer nur bei `hasHumidity` |

### Neue Funktion `_render_chart_script`

In `dashboard_charts.py`:

```python
def _render_chart_script(
    *,
    chart_id: str,
    chart_var: str,
    labels_json: str,
    dates_json: str,
    temp_values_json: str,
    hum_values_json: str,
    limit_datasets: str,
    legend_datasets: str = "",
    legend_onclick: str = "",
    legend_filter: str = "!label.startsWith('Warning') && !label.startsWith('Critical')",
) -> str: ...
```

- `chart_var`: Präfix für JS-Variablen. Tiles: `device["chart_id"].replace("-", "_")`. Detail: `""`.
- `limit_datasets` / `legend_datasets`: vorformatierte JS-Strings (Caller baut sie).
- `legend_onclick`: optionaler JS-Handler (mit führendem Komma).
- `legend_filter`: JS-Ausdruck für den Legenden-Filter.
- Humidity-Achse wird **nur bei `hasHumidity`** hinzugefügt (keine leere Achse).

### Aufrufer

| Aufrufer | Parameter |
|---|---|
| `_render_device_script` | `chart_var=<prefix>`, `legend_filter=startsWith`, `legend_onclick=""`, `legend_datasets=""` |
| `_render_device_detail` | `chart_var=""`, `legend_filter=exakt`, `legend_onclick=<handler>`, `legend_datasets=<str>` |
| `_render_climate_detail` | **unverändert** |

### Schritte

1. **`_render_chart_script` in `dashboard_charts.py`** – neue Funktion, keine Caller. Tests bleiben grün.
2. **`_render_device_script`** wird dünner Wrapper: Placeholder-Check, `limit_datasets` bauen, `_render_chart_script` aufrufen. **Beide Branches** (temperature-only und temp+hum) entfallen.
3. **`_render_device_detail`** nutzt `_render_chart_script`. Limit-Datasets müssen auf `Labels.map(...)` umgestellt werden (statt `tempValues.map(...)`).

**Nach jedem Schritt:** `pytest` + `ruff check .`.

### Dateien

| Datei | Änderung |
|---|---|
| `src/loggerpi_otterpi/dashboard_charts.py` | neue Funktion `_render_chart_script` |
| `src/loggerpi_otterpi/dashboard.py` | `_render_device_detail` nutzt sie |
| `tests/test_dashboard.py` | ggf. anpassen |

### Risiko

Mittel. Reine JS-Generierung. Tests fangen Struktur, aber nicht visuelles
Verhalten. Browser-Check nötig (Charts, Limit-Linien, Legende, Tooltip,
`onClick`-Handler).

### Definition of Done

- Alle Tests grün (605 + ggf. neue).
- `ruff check .` + `ruff format --check .` clean.
- **Kein Verhaltensunterschied** an den Charts (Höhe, Limit-Linien, Tooltip,
  Legende, `onClick`).
- Browser-Check: Raumdetail (Tiles, inkl. freezer/memmert/id01), Device-Detail,
  Climate-Detail (unverändert).
- Doku aktualisiert (`REFACTORING.md`, `WIEDEREINSTIEG.md`).
- Deploy + Verifikation auf OtterPi.

### Was sich NICHT ändert

- **Schwellen:** `critical_min`, `critical_max`, `warning_min`, `warning_max`,
  `rate_of_change_max_per_hour` – gleiche Werte, gleiche Semantik.
- **`dedup_key`s:** `{sensor_key}:{rule}:{severity}` – gleiches Format.
- **Alert-Texte:** `_build_message`, `_build_subject` – gleiche Ausgabe.
- **Chip-Texte:** `⛔ Temperature above limit`, `⚠ Battery low`, `OK`, `Offline`
  – gleiche Ausgabe.
- **`resolve()`-Semantik:** Nur bei normalem Wert, nicht bei `validity == "valid"`.
- **`is_acknowledged()`-Semantik:** Nur aktive Alerts.
- **Chart-Höhe:** 280 (Tile) vs. 400 (Detail).
- **Limit-Linien:** Gleiche Farben, gleiche Dash-Muster.
- **Tooltip:** Gleiche Formatierung.
- **Legende:** Gleiche Filter, gleicher `onClick`-Handler.
- **Climate-Charts:** **Unverändert** (eigene Datasets, siehe Phase 4b).

---

### Phase 4a – Alert-Logik (3.13.1) — ✅ abgeschlossen (v1.14.8)

#### Ziel

`alert_engine.py` und `dashboard_data.py` nutzen dieselbe Detection-Logik
(`status.py`), aber unterschiedliche Presentation (Alert vs. Chip).

#### Neue Datei `status.py`

```python
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LimitViolation:
    key: str
    rule: str  # "critical_max", "warning_min", "rate_of_change", ...
    severity: str  # "critical", "warning"
    value: float
    threshold: float
    unit: str


@dataclass(frozen=True)
class StateViolation:
    key: str
    rule: str  # "alarm", "battery_low", "door_open", "contact_open"
    severity: str
    value: object


@dataclass(frozen=True)
class DeviceViolation:
    device_key: str
    rule: str  # "stale", "invalid"
    severity: str
    reason: Optional[str]


def calculate_rate_of_change(
    values: list[tuple[str, float]],
) -> Optional[float]:
    """Berechnet die Rate of Change (pro Stunde) aus (created_at, value)-Tupeln."""
    ...


def check_limits(
    measurements: dict,
    limits: dict,
) -> list[LimitViolation]:
    """Prüft Grenzwerte. Gibt alle Violations zurück."""
    ...


def check_states(
    states: dict,
    rules: dict,
) -> list[StateViolation]:
    """Prüft States. Gibt alle Violations zurück."""
    ...


def check_stale_invalid(
    measurements: dict,
    device_config: dict,
) -> list[DeviceViolation]:
    """Prüft stale/invalid pro Gerät. Gibt alle Violations zurück."""
    ...
```

#### Detailentscheidungen

**1. `calculate_rate_of_change` nimmt `list[tuple[str, float]]`.**

Beide Caller extrahieren die Tupel selbst:

- `alert_engine`: `[(b.created_at, b.measurements[key].value) for b in recent_batches if ...]`
- `dashboard_data`: `[(b["created_at"], b["measurements"][key]["value"]) for b in batches if ...]`

Kein Konvertieren zwischen `Batch` und `dict`.

**2. `check_limits` gibt `list[LimitViolation]` zurück.**

Der Caller leitet den Status ab:

```python
violations = check_limits(measurements, limits)
if any(v.severity == "critical" for v in violations):
    status = "status-critical"
elif any(v.severity == "warning" for v in violations):
    status = "status-warn"
else:
    status = ""
```

**3. `_device_status` und `_device_chips` kombinieren die Check-Funktionen mit ihrer eigenen Logik.**

- `_device_status` ruft `check_limits`, `check_states`, `check_stale_invalid` auf
  und kombiniert mit `validity` (`valid`, `stale`, `invalid`, `unavailable`) und
  `battery_low`.
- `_device_chips` ruft die drei Check-Funktionen auf und baut zusätzlich die
  **Info-Chips** (`door_locked`, `defrost`, `flap`, `mode`, `operation_mode`) –
  die **keine** Violations sind.

**4. `resolve()` bleibt in `alert_engine`.**

`check_*` ruft **kein** `resolve()` auf. `alert_engine` ruft `resolve()` für alle
Keys auf, die **nicht** in den Violations sind:

```python
violated_keys = {v.key for v in violations}
for key in limits:
    if key not in violated_keys:
        self._alert_store.resolve(f"{key}:{rule}:{severity}")
```

**5. Keine Verhaltensänderung.**

- Gleiche Schwellen.
- Gleiche `dedup_key`s.
- Gleiche Alert-Texte.
- Gleiche Chip-Texte.
- Gleiche `resolve()`-Semantik.

#### Reihenfolge (bottom-up)

1. `status.py` mit `calculate_rate_of_change` (nur die Funktion, noch keine Caller).
2. `status.py` mit `check_limits`.
3. `status.py` mit `check_stale_invalid`.
4. `status.py` mit `check_states`.
5. `alert_engine.py` nutzt `calculate_rate_of_change`.
6. `alert_engine.py` nutzt `check_limits` + `check_stale_invalid` + `check_states`.
7. `dashboard_data.py` nutzt `calculate_rate_of_change`.
8. `dashboard_data.py` nutzt `check_limits` + `check_stale_invalid` + `check_states`.
9. `_device_status` und `_device_chips` refaktorieren.
10. Tests grün, manueller Check im Admin-Alerts-Tab.

**Nach jedem Schritt:** `pytest` + `ruff check .`.

#### Dateien

| Datei | Änderung |
|---|---|
| `src/loggerpi_otterpi/status.py` | neu |
| `src/loggerpi_otterpi/alert_engine.py` | nutzt `status.py` |
| `src/loggerpi_otterpi/dashboard_data.py` | nutzt `status.py` |
| `tests/test_status.py` | neu |
| `tests/test_alert_engine.py` | ggf. anpassen |
| `tests/test_dashboard_data.py` | ggf. anpassen |

#### Risiko

Hoch. Alert-Logik. Tests + manueller Check im Admin-Alerts-Tab.

---

### Phase 4b – Chart-Logik (3.13.2) — ✅ abgeschlossen (v1.15.0)

#### Ziel

`_render_device_script` (in `dashboard_charts.py`) und `_render_device_detail`
(in `dashboard.py`) teilen die Chart.js-Logik.

**Wichtig:** `_render_climate_detail` bleibt **unverändert**. Die vier
Climate-Charts (Average Temperature, Average Humidity, Individual Sensors
Temperature, Individual Sensors Humidity) werden aus separaten Werten
gebildet und sind zu unterschiedlich für eine gemeinsame Funktion.

#### Neue Funktion `_render_chart_script`

```python
def _render_chart_script(
    device: dict,
    *,
    height: int,
    show_limits: bool,
    show_legend: bool,
    legend_onclick: Optional[str] = None,
) -> str:
    """Gemeinsame Chart.js-Generierung für Device-Tiles und Device-Detail."""
    ...
```

#### Aufrufer

| Aufrufer | Parameter |
|---|---|
| `_render_device_script` | `height=280, show_limits=True, show_legend=True, legend_onclick=None` |
| `_render_device_detail` | `height=400, show_limits=True, show_legend=True, legend_onclick=<handler>` |
| `_render_climate_detail` | **unverändert** (eigene Charts) |

#### Detailentscheidungen

**1. `legend_onclick` als optionaler Parameter.**

`_render_device_detail` hat einen custom `onClick`-Handler für die Legende
(Limit-Paare toggeln). `_render_device_script` hat das nicht. Der Handler
wird als String übergeben und in die Chart-Optionen eingebaut.

**2. `_render_climate_detail` bleibt unverändert.**

Die vier Climate-Charts haben unterschiedliche Datasets, Skalen und
Tooltips. Eine gemeinsame Funktion würde mehr Komplexität als Klarheit
bringen.

**3. Keine Verhaltensänderung.**

- Gleiche Chart-Höhe (280 vs. 400).
- Gleiche Limit-Linien.
- Gleiche Tooltips.
- Gleiche Legende.
- Gleicher `onClick`-Handler.

#### Reihenfolge

1. `_render_chart_script` in `dashboard_charts.py` (gemeinsame Funktion).
2. `_render_device_script` nutzt sie.
3. `_render_device_detail` nutzt sie.
4. Tests grün, Browser-Check (Charts, Limit-Linien, Legende, Tooltip).

**Nach jedem Schritt:** `pytest` + `ruff check .`.

#### Dateien

| Datei | Änderung |
|---|---|
| `src/loggerpi_otterpi/dashboard_charts.py` | gemeinsame Funktion |
| `src/loggerpi_otterpi/dashboard.py` | `_render_device_detail` nutzt sie |
| `tests/test_dashboard.py` | ggf. anpassen |

#### Risiko

Mittel. Reine JS-Generierung. Tests fangen Struktur, aber nicht visuelles
Verhalten. Browser-Check nötig.

---

### Test-Strategie

**Automatisch:**

- `pytest` nach jedem Schritt.
- `ruff check .` nach jedem Schritt.
- Neue `tests/test_status.py` für die gemeinsamen Funktionen.

**Manuell (nach Phase 4a):**

- Admin-Alerts-Tab: Aktive Alerts prüfen (gleiche Anzahl, gleiche Texte).
- Admin-Alerts-Tab: Acknowledge/Resolve prüfen.
- Dashboard: Statusleuchte prüfen (gleiche Farbe).
- Dashboard: Chips prüfen (gleiche Texte).

**Manuell (nach Phase 4b):**

- Dashboard: Device-Tile-Charts prüfen (Höhe 280, Limit-Linien, Tooltip).
- Device-Detail: Chart prüfen (Höhe 400, Limit-Linien, Legende, `onClick`).
- Climate-Detail: Charts prüfen (unverändert).

---

### Sicherheit

| Schritt | Was |
|---|---|
| 1 | Branch `refactor/phase-4` |
| 2 | Phase 4a umsetzen, `pytest` + `ruff`, Commit |
| 3 | Phase 4b umsetzen, `pytest` + `ruff`, Commit |
| 4 | Browser-Check (Charts, Limit-Linien, Alerts-Tab) |
| 5 | Merge nach `main`, Deploy, Verifikation |

**Wenn's schiefgeht:** `git checkout main`, Branch weg. Kein Risiko für `main`.

---

### Definition of Done

- Alle Tests grün (559 + neue `test_status.py`-Tests).
- `ruff check .` + `ruff format --check .` clean.
- **Kein Verhaltensunterschied** (Alerts, Chips, Charts, Texte, Schwellen).
- Manueller Check: Admin-Alerts-Tab, Dashboard-Charts, Device-Detail.
- Doku aktualisiert (`REFACTORING.md`, `Wiedereinstieg.md`).
- Deploy + Verifikation auf OtterPi.

---

## Phase 5 – Obsolet (3.13.6)

- SQL-Filter in `_recent_batches`: `LIMIT` deckelt bereits, `created_at` ist keine Spalte, RAM-Peak transient.

---

## Nicht im Block (bewusst)

### Minor (nicht worth it)

- `run_once` Reader-Schleife (`runtime.py`).
- Query-Parameter manuell (`otterpi.py::do_GET`).
- if/elif-Routen (`otterpi.py::do_GET`, `do_POST`).
- `archive_batches.py` Batch/Alert-Symmetrie.
- `batch_queue.py` JSON-Parsing.
- `otterpi_store.py` JSON-Parsing.
- if/elif Sensor-Typen (`weatherhub.py`, `weatherhub_gateway_decoder.py`).
- `to_dict` repetitiv (`model/batch.py`).
- HTML/JS-Strings (`admin.py`, `dashboard.py`).
- `_validate_*` (`config_store.py`).
- `_build_where` (`alert_store.py`).
- Lange Parameter-Listen (`alert_store.py`).

### Nicht im Scope (separate Themen)

- 3.14 Acknowledge-Button im Dashboard.
- 3.8 Hysterese.
- Advanced Updates 5.1–5.7.
- Verschobene Punkte (CSV, Statuspage, Dry-Run, Config-Backup/Restore, Audit-Log, Mobile).

---

## Definition of Done

- Alle Tests grün.
- `ruff check .` + `ruff format --check .` clean.
- Kein Verhaltensunterschied (außer Performance).
- Doku aktualisiert.
- Deploy + Verifikation auf OtterPi.
