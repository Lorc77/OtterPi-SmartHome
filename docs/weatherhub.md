# WeatherHub-Gateway — Protokoll und Integration

## Zweck

Dieses Dokument beschreibt das WeatherHub-Gateway-Protokoll und die
Integration in OtterPi-SmartHome.

---

## 1. Überblick

Die WeatherHub-Sensoren senden per Funk an ein MOBILE-ALERTS-Gateway.
Normalerweise überträgt das Gateway die Daten an die TFA-Cloud
(`www.data199.com`).

Im SmartHome wird das Gateway in den **Proxymodus** versetzt. Es sendet
seine Daten per HTTP PUT an den OtterPi (Port 3779). Der
`WeatherHubGatewayListener` empfängt die Daten, dekodiert sie und übergibt
sie an die `SmartHomeBridge`.

```text
WeatherHub-Sensor
    ↓ (Funk)
WeatherHub-Gateway (192.168.178.x)
    ↓ (HTTP PUT, binär)
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
SmartHomeBridge
    ↓
BatchStore → smarthome.sqlite3
```

---

## 2. Gateway-Payload

Das Gateway sendet binäre Payloads per HTTP PUT. Ein Payload besteht aus
einem oder mehreren 64-Byte-Paketen.

### Boot-Paket (15 Byte)

Ein 15-Byte-Paket ist ein Boot-/Control-Paket. Es enthält keine
Sensordaten und wird von der `SmartHomeBridge` ignoriert.

### Sensor-Paket (64 Byte)

Ein 64-Byte-Paket enthält:

| Offset | Länge | Bedeutung |
|---:|---:|---|
| 0 | 1 | Package-Header (Sensor-Typ-spezifisch) |
| 1–4 | 4 | Gateway-Timestamp (Big-Endian) |
| 5 | 1 | Packet-Length |
| 6–11 | 6 | Sensor-ID (Hex) |
| 12–… | n | Payload (Sensor-Typ-spezifisch) |
| 63 | 1 | CRC (Summe der ersten 63 Bytes & 0x7F) |

### CRC

Der CRC ist die Summe der ersten 63 Bytes, maskiert mit `0x7F`. Bei
einem CRC-Fehler wird das Paket verworfen (mit Logging).

---

## 3. Sensor-Typen

Der Decoder unterstützt folgende Sensor-Familien:

| Typ | Name | Header | Packet-Length | Payload-Length |
|---|---:|---:|---:|---:|
| `0x01` | ID01 | `0xD2` | `0x16` | 10 |
| `0x02` | ID02 | `0xCE` | `0x12` | 6 |
| `0x03` | ID03 | `0xD2` | `0x16` | 10 |
| `0x04` | ID04 | `0xD4` | `0x18` | 12 |
| `0x07` | ID07 | `0xDA` | `0x1E` | 18 |
| `0x0E` | ID0E | `0xD8` | `0x1C` | 16 |
| `0x10` | ID10 | `0xD3` | `0x17` | 11 |

Andere Sensor-Typen werden dekodiert, aber nicht in die
Measurement-Pipeline übernommen.

---

## 4. Sensor-Familien im Detail

### ID01 — Temperatursensor (2 Kanäle)

- **Measurements:** `temperature_1`, `temperature_2` (celsius)
- **States:** `battery_low` (bool)
- **Payload:** Status (2 Byte), Temp1 (2 Byte), Temp2 (2 Byte)

### ID02 — Temperatursensor (1 Kanal)

- **Measurements:** `temperature` (celsius)
- **States:** `battery_low` (bool)
- **Payload:** Status (2 Byte), Temp (2 Byte)

### ID03 — Temperatur + Feuchte

- **Measurements:** `temperature` (celsius), `humidity` (percent)
- **States:** `battery_low` (bool)
- **Payload:** Status (2 Byte), Temp (2 Byte), Humidity (2 Byte)

### ID04 — Temperatur + Feuchte + Wasserkontakt

- **Measurements:** `temperature` (celsius), `humidity` (percent)
- **States:** `battery_low` (bool), `water_contact` (bool)
- **Payload:** Status (2 Byte), Temp (2 Byte), Humidity (2 Byte),
  Water-Contact (1 Byte)

**Hinweis:** `water_contact` wird als State verarbeitet (seit v0.1.4).

### ID07 — Innen-/Außensensor

- **Measurements:** `temperature_indoor`, `humidity_indoor`,
  `temperature_outdoor`, `humidity_outdoor`
- **States:** `battery_low` (bool)
- **Payload:** Status (2 Byte), Temp-Indoor (2 Byte), Humidity-Indoor
  (2 Byte), Temp-Outdoor (2 Byte), Humidity-Outdoor (2 Byte)

### ID0E — Temperatur + Feuchte (dezimal)

- **Measurements:** `temperature` (celsius), `humidity` (percent)
- **States:** `battery_low` (bool)
- **Payload:** Status (2 Byte), Temp (2 Byte), Humidity (2 Byte, dezimal)

### ID10 — Tür-/Fensterkontakt

- **Measurements:** keine
- **States:** `battery_low` (bool), `contact_open` (bool),
  `contact_previous*_open` (bool), `contact_*_since` (Unix-Timestamp),
  `counter` (int), `event_transmission` (bool)
- **Payload:** Status (2 Byte), Contact current (2 Byte),
  Contact previous (2 Byte), Contact previous 1 (2 Byte),
  Contact previous 2 (2 Byte), Contact previous 3 (1 Byte)

**Hinweis:** ID10 liefert die letzten 5 Zustandswechsel (current +
previous 1–3). `time_unit`/`elapsed_value` werden in einen Unix-Timestamp
umgerechnet (`_contact_timestamp`). `previous 3` hat kein `time`.

---

## 5. Decoder

Der `WeatherHubGatewayDecoder` (`weatherhub_gateway_decoder.py`) dekodiert
die binären Payloads.

### Funktionen

- `decode_payload(body)` — dekodiert einen HTTP-PUT-Body (15 Byte oder
  Vielfaches von 64 Byte).
- `decode_packet(packet)` — dekodiert ein einzelnes 64-Byte-Paket.
- `decode_temperature(data)` — dekodiert einen Temperaturwert.
- `decode_humidity(data)` — dekodiert einen Feuchtewert.
- `decode_humidity_decimal(data)` — dekodiert einen dezimalen
  Feuchtewert (ID0E).
- `decode_sensor_status(data)` — dekodiert den Status (Battery, Counter).
- `decode_door_window(data)` — dekodiert den Tür-/Fensterkontakt (ID10):
  `open`, `time_unit`, `elapsed_value`.

### Fehlerbehandlung

- CRC-Fehler → Paket wird verworfen (mit Logging).
- Header-Mismatch → `WeatherHubDecoderError`.
- Length-Mismatch → `WeatherHubDecoderError`.
- Unbekannter Sensor-Typ → Paket wird ohne `decoded_values` zurückgegeben.

---

## 6. Listener

Der `WeatherHubGatewayListener` (`weatherhub_gateway_listener.py`) ist ein
TCP-Server, der auf HTTP-PUT-Requests vom Gateway wartet.

### Konfiguration

- `SMARTHOME_WEATHERHUB_HOST` — Bind-Adresse (Default: `0.0.0.0`)
- `SMARTHOME_WEATHERHUB_PORT` — Port (Default: `3779`)
- `SMARTHOME_WEATHERHUB_ALLOWLIST` — Erlaubte Gateway-IPs
  (Komma-getrennt)
- `SMARTHOME_CLOUD_FORWARD_ENABLED` — Cloud-Forward an
  `www.data199.com` (Default: `0`)

### Ablauf

1. Verbindung akzeptieren.
2. IP-Allowlist prüfen.
3. HTTP-Header lesen (max. 16 KB).
4. `PUT`-Methode prüfen.
5. `Content-Length` parsen (max. 2 MB).
6. Body lesen.
7. Cloud-Forward (optional, asynchron).
8. Payload dekodieren.
9. Callback (`SmartHomeBridge.on_packets_received`).
10. Gateway-Response senden (24 Byte, binär).

### Gateway-Response

Das Gateway erwartet eine spezifische 24-Byte-Binärantwort mit
HTTP 200. Ohne diese Antwort sendet das Gateway die Daten erneut.

---

## 7. Reader

Der `WeatherHubReader` (`weatherhub.py`) ist der Adapter zwischen
Gateway-Paketen und Core Measurements.

### Funktionen

- `update_from_packets(packets, client_ip)` — verarbeitet neue Pakete
  und aktualisiert den internen Zustand.
- `read_measurements()` — liefert alle aktuellen Measurements aller
  bekannten Sensoren.
- `measurements_from_packet(packet)` — liefert die Measurements eines
  einzelnen Pakets (für die `SmartHomeBridge`).
- `read_state()` — liefert die States:
  - `battery_low` (alle Sensoren)
  - `water_contact` (ID04)
  - `contact_open`, `contact_previous*_open`, `contact_*_since` (ID10)
- `read_device_info()` — liefert Geräte-Infos (Sensor-ID, Typ,
  Gateway-IP, Gateway-Timestamp).

### Validity

- `valid` — Wert ist gültig.
- `invalid` — Wert ist ungültig (`sensor_error` oder `overflow`).

**Hinweis:** Stale/Offline wird nicht mehr im Reader berechnet, sondern
in `status.py` (`check_sensor_stale`). Der Reader ist nur noch Adapter.

---

## 8. Bridge

Die `SmartHomeBridge` (`smarthome_bridge.py`) ist die Brücke zwischen
Gateway-Paketen und dem `BatchStore`.

### Ablauf

1. Paket empfangen.
2. `BootPacket` ignorieren.
3. Paket ohne `decoded_values` ignorieren.
4. `reader.update_from_packets([packet], client_ip)` — Zustand
   aktualisieren.
5. `reader.measurements_from_packet(packet)` — Measurements extrahieren.
6. `Batch` erzeugen (mit `batch_id`, `logger_id`, `sequence`,
   `created_at`, `measurements`).
7. `store.store(batch)` — Batch speichern.

### Sequence

Die `SmartHomeBridge` verwendet einen `SequenceStore`, um eine persistente
Sequence pro SmartHome-Logger zu vergeben.

---

## 9. Cloud-Forward

Der Cloud-Forward ist optional (`SMARTHOME_CLOUD_FORWARD_ENABLED=1`).

Wenn aktiviert, sendet der Listener die Rohdaten zusätzlich an
`www.data199.com` (TFA-Cloud). Der Cloud-Forward läuft asynchron (Thread),
blockiert den lokalen Empfang nicht.

### Fehlerbehandlung

- Cloud-Forward-Fehler werden geloggt, aber nicht an den lokalen Empfang
  weitergegeben.
- Timeout: 10 s.

---

## 10. Tests

- `tests/test_weatherhub_decoder.py` — Decoder-Tests (mit Fixtures).
- `tests/test_weatherhub_stale.py` — Stale-Logik, `read_state` (ID04, ID10).
- `tests/test_weatherhub.py` — `measurements_from_packet` (ID01, ID02,
  ID03, ID04, ID0E, ID10).
- `tests/test_smarthome_bridge.py` — Packet → Batch → Store.

---

## 11. Bekannte Einschränkungen

- **ID07:** Wird dekodiert, aber im Dashboard noch nicht unterstützt
  (4 Measurements, eigene Karten-Logik nötig).
- **ID10 `event_transmission`:** Die Bedeutung (Event vs. Heartbeat) ist
  noch nicht verifiziert.
- **ID10 `previous 3`:** Hat kein `time` (nur `sensor`), wird aber
  angezeigt.
- **Gateway-Deduplizierung:** Wenn mehrere Gateways dieselben Sensordaten
  empfangen, werden die Daten doppelt verarbeitet. Eine Deduplizierung
  ist nicht implementiert.