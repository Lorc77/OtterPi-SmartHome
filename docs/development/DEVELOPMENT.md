# OtterPi-SmartHome — Entwicklungsumgebung

## Zweck

Dieses Dokument beschreibt die Entwicklungsumgebung für das Projekt
OtterPi-SmartHome.

Die Entwicklungsumgebung ist bewusst von der Laufzeitumgebung des OtterPi
getrennt.

---

## 1. Entwicklungsrechner

### Betriebssystem

- Windows 11

### IDE / Editor

- Visual Studio Code (stabile Version, nicht Insiders)

### KI-Unterstützung

ChatGPT wird als KI-Unterstützung bei Entwicklung, Dokumentation, Analyse,
Reviews und Fehlersuche eingesetzt.

---

## 2. Versionsverwaltung

### Git

Git for Windows wird für die lokale Versionsverwaltung eingesetzt.

### Repository

GitHub-Repository:

```text
Lorc77/OtterPi-SmartHome
```

Lokaler Pfad:

```text
D:\Misc\_Makki_Heimserver\OtterPi-SmartHome
```

### Git-Konfiguration

- Hauptbranch: `main`
- Remote: `origin`
- Transport: HTTPS
- Credential Helper: Git Credential Manager

---

## 3. Python

Für die Windows-Entwicklung wird Python 3.13 verwendet.

Installationspfad:

```text
C:\Program Files\Python313\
```

### Virtuelle Umgebung

Jedes Python-Projekt verwendet eine eigene virtuelle Umgebung.

Für dieses Repository liegt sie unter:

```text
.venv\
```

Die Umgebung wird mit

```powershell
python -m venv .venv
```

erstellt und kann in PowerShell mit

```powershell
.\.venv\Scripts\Activate.ps1
```

aktiviert werden.

Falls PowerShell die Ausführung von Skripten verhindert:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Die `.venv` wird nicht versioniert.

### VS-Code-Python-Unterstützung

Für die Python-Entwicklung sind folgende VS-Code-Erweiterungen installiert:

- Python
- Pylance
- Python Debugger
- Python Environments

Die Workspace-Konfiguration liegt unter:

```text
.vscode/settings.json
```

und verwendet relative Pfade:

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
    "python.analysis.extraPaths": [
        "${workspaceFolder}/src",
        "${workspaceFolder}/src/otterpi_smarthome",
        "${workspaceFolder}/src/otterpi_smarthome/model"
    ],
    "python.analysis.typeCheckingMode": "off"
}
```

**Hinweis:** Pylance ist auf `off` gestellt. Ruff und pytest sind die
echten Gates. Die Typ-Prüfung ist ein Nice-to-have, kein Muss.

---

## 4. Python-Versionen

OtterPi-SmartHome unterstützt aktuell Python **3.9 und höher**.

Python 3.9 ist die minimale unterstützte Version und damit Teil des
Kompatibilitätsvertrags des Projekts.

Für die lokale Entwicklung wird aktuell Python **3.13** verwendet.

```text
Lokale Entwicklung:        Python 3.13
Minimale Unterstützung:    Python 3.9
CI-Kompatibilitätstest:     Python 3.9 + Python 3.13
```

### Technische Vorgaben

- `pyproject.toml` definiert `requires-python = ">=3.9"`.
- Ruff verwendet `target-version = "py39"`.
- Python-3.9-kompatible Type-Annotation-Syntax wird verwendet
  (`Optional`, `Union` statt `str | None`).
- Ruff `FA102` dient als statisches Teil-Gate für Type-Annotation-
  Kompatibilität.
- Die GitHub Actions testen den Code unter Python 3.9 und Python 3.13.

---

## 5. Tests und Qualität

### Tests

Die Tests werden mit `pytest` ausgeführt:

```powershell
pytest
```

Die `pyproject.toml` definiert:

- `testpaths = ["tests"]`
- `pythonpath = ["src", "src/otterpi_smarthome", "src/otterpi_smarthome/model"]`

Aktueller Stand: **424 Tests**, alle bestehen.

### Linting und Formatierung

Ruff wird für Linting und Formatierung verwendet:

```powershell
ruff check .
ruff format .
```

Bei Import-Reihenfolge-Fehlern:

```powershell
ruff check . --fix
```

### Quality Gates

Vor einem Commit werden alle drei Prüfungen ausgeführt:

```powershell
ruff check .
ruff format --check .
pytest
git diff --check
```

Alle drei Befehle müssen erfolgreich sein.

---

## 6. Import-Struktur

Die Import-Struktur ist auf die flache Deploy-Struktur des OtterPi
ausgelegt.

Lokal unter Windows funktionieren die Imports über die `pythonpath`-Angabe
in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = [
    "src",
    "src/otterpi_smarthome",
    "src/otterpi_smarthome/model",
]
```

Auf dem OtterPi (flache Deploy-Struktur) wird `PYTHONPATH` in der
Service-Datei und der `.env`-Datei gesetzt:

```bash
PYTHONPATH=/opt/otterpi-smarthome:/opt/otterpi-smarthome/model
```

Damit funktionieren Imports wie `from sequence_store import SequenceStore`
sowohl lokal unter Windows als auch auf dem OtterPi.

---

## 7. Entwicklungsabhängigkeiten

Die Entwicklungswerkzeuge werden in `pyproject.toml` definiert:

```toml
[dependency-groups]
dev = [
    "pytest>=8.4,<9",
    "ruff>=0.16.5,<0.17",
    "tzdata>=2024.1",
]
```

Die Entwicklungsabhängigkeiten werden aus der Projektkonfiguration
installiert:

```powershell
python -m pip install --group dev
```

**Hinweis:** `tzdata` ist nötig, weil Windows keine Zeitzonen-Datenbank
hat. Ohne `tzdata` schlägt `ZoneInfo("Europe/Berlin")` fehl.

---

## 8. Continuous Integration

GitHub Actions stellt das zweite und verbindliche Kompatibilitäts-Gate dar.

Der CI-Workflow befindet sich unter:

```text
.github/workflows/ci.yml
```

Die aktuelle Testmatrix enthält:

```yaml
matrix:
  python-version:
    - "3.9"
    - "3.13"
```

Für beide Python-Versionen werden dieselben grundlegenden Prüfungen
durchgeführt:

1. Repository auschecken
2. Projekt installieren
3. Entwicklungsabhängigkeiten installieren
4. Python- und Werkzeugversionen anzeigen
5. Ruff ausführen
6. Formatierung prüfen
7. Tests ausführen

---

## 9. Vorgehen vor einem Commit

Für normale Änderungen am Quellcode:

```powershell
ruff check .
ruff format --check .
pytest
git status
```

Anschließend sollte der Arbeitsbaum ausschließlich beabsichtigte
Änderungen enthalten.

Vor dem Staging sollte außerdem das tatsächliche Diff geprüft werden:

```powershell
git diff
```

Für bereits gestagte Änderungen:

```powershell
git diff --cached
```

Zusätzliche Prüfung auf Whitespace-Probleme:

```powershell
git diff --check
```

---

## 10. Definition of Done

Eine Änderung gilt als bereit, wenn:

- die gewünschte Funktionalität implementiert ist
- die vorhandenen Tests erfolgreich sind
- für neue Funktionalität geeignete Tests vorhanden sind
- `ruff check .` erfolgreich ist
- `ruff format --check .` erfolgreich ist
- Python-3.9-Kompatibilität erhalten bleibt
- Python 3.13 weiterhin unterstützt wird
- die GitHub-CI-Matrix vollständig grün ist
- keine unbeabsichtigten Änderungen im Arbeitsbaum verbleiben
- relevante Architektur- oder Entwicklungsdokumentation aktualisiert wurde

### Deployment-Gate

Wenn eine Änderung Deployment- oder Runtime-Verhalten betrifft, muss
zusätzlich geprüft werden:

```text
Deployment-Skript
systemd-Service
Environment-Datei
Installationspfade
Zielsystem-Python
```

Ein erfolgreicher lokaler Testlauf unter Windows gilt nicht als
Nachweis eines erfolgreichen OtterPi-Deployments.

---

## 11. Quellen der Wahrheit

Für die relevanten Bereiche gilt folgende Hierarchie:

1. `pyproject.toml` definiert die deklarierte Python- und
   Entwicklungswerkzeug-Konfiguration.
2. `.github/workflows/ci.yml` definiert die automatisierte
   Python-Kompatibilitätsmatrix.
3. Dieses Dokument beschreibt Entwicklungs- und Quality-Gate-Regeln.
4. `docs/development/DECISIONS.md` dokumentiert wesentliche
   Projektentscheidungen und deren Begründungen.
5. Die lokale `.venv` ist ein Detail der Entwicklungsumgebung und keine
   Kompatibilitätsdefinition.
6. `docs/deployment/DEPLOYMENT.md` dokumentiert den Deployment-Ablauf und
   den aktuellen Betriebsstand.