# Uptime Robot – Kunden-Mail-Generator

Dieses Skript holt Verfügbarkeitsdaten aus [Uptime Robot](https://uptimerobot.com/) und erstellt daraus fertige Kunden-Mails für den monatlichen Verfügbarkeitsbericht.

## Voraussetzungen

- Python 3.10 oder neuer
- Ein Uptime-Robot-Konto mit API-Schlüssel
- Die Monitor-IDs der zu überwachenden Websites

## Installation

```bash
# Repository klonen oder herunterladen, dann ins Projektverzeichnis wechseln
cd Uptime-Robot---Kunden-Mail-Gen

# Virtuelle Umgebung anlegen (empfohlen)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Abhängigkeiten installieren
pip install -r requirements.txt
```

## Einrichtung

### 1. API-Schlüssel hinterlegen

Kopieren Sie `.env.example` nach `.env` und tragen Sie Ihren API-Schlüssel ein:

```bash
cp .env.example .env
```

In `.env`:

```env
UPTIMEROBOT_API_KEY=ihr_api_schlüssel_hier
```

Den Schlüssel finden Sie unter: [Uptime Robot → My Settings](https://uptimerobot.com/dashboard#mySettings)

### 2. Kunden konfigurieren

Kopieren Sie `config.example.yaml` nach `config.yaml` und passen Sie die Kunden an:

```bash
cp config.example.yaml config.yaml
```

Beispiel `config.yaml`:

```yaml
report:
  # Optional: Berichtsmonat (Standard = Vormonat)
  # year: 2026
  # month: 5
  output_dir: output

customers:
  - email: kunde@beispiel.de
    # filename: musterfirma          # optional, sonst E-Mail als Dateiname
    # salutation: |                  # optional, eigene Anrede
    #   Sehr geehrte Frau Muster,
    monitors:
      - id: 123456789                # Monitor-ID aus Uptime Robot
        domain: domain.de            # optional, sonst aus Monitor-URL
      - id: 987654321
        domain: zweite-domain.de
```

**Monitor-ID finden:** In Uptime Robot die gewünschten Monitore öffnen – die ID steht in der URL oder in den Monitor-Details.

**Mehrere Kunden:** Einfach weitere Einträge unter `customers` hinzufügen. Ein Kunde kann mehrere Monitore (Domains) haben.

### 3. Mail-Vorlage anpassen (optional)

Die Textvorlage liegt in `mail_template.txt`. Verfügbare Platzhalter:

| Platzhalter           | Inhalt                                              |
|-----------------------|-----------------------------------------------------|
| `{salutation}`        | Anrede (pro Kunde konfigurierbar)                   |
| `{availability_lines}`| Verfügbarkeit je Domain, z. B. `domain.de: 99,849%` |
| `{incidents}`         | Liste bekannter Ausfälle oder `-keine-`             |

## Verwendung

### Standardlauf (Vormonat)

```bash
python generate_reports.py
```

Ohne Angabe von Jahr und Monat wird automatisch der **Vormonat** verwendet (z. B. im Juni 2026 → Bericht für Mai 2026).

### Bestimmten Monat erzeugen

```bash
python generate_reports.py --year 2026 --month 5
```

Alternativ können `year` und `month` fest in `config.yaml` unter `report` gesetzt werden.

### Vorschau ohne Dateien

```bash
python generate_reports.py --dry-run
```

Gibt die Mails auf der Konsole aus, ohne Dateien zu schreiben. Nützlich zum Testen vor dem Versand.

### Andere Konfigurationsdatei

```bash
python generate_reports.py -c /pfad/zu/andere-config.yaml
```

## Ausgabe

Erzeugte Dateien landen im Ordner `output/` (oder dem in `config.yaml` konfigurierten `output_dir`).

Dateiname-Schema:

```
{filename_oder_email}_{jahr}-{monat}.txt
```

Beispiel: `nicole.mossell_lasi-24.de_2026-05.txt`

Die Dateien können direkt als E-Mail-Text verwendet oder in ein Mailprogramm kopiert werden.

## Typischer Monatsablauf

1. Prüfen, ob neue Kunden oder Monitore in `config.yaml` eingetragen werden müssen
2. Testlauf: `python generate_reports.py --dry-run`
3. Berichte erzeugen: `python generate_reports.py`
4. Dateien aus `output/` prüfen und an die jeweiligen Kunden senden

## Fehlerbehebung

| Fehlermeldung | Lösung |
|---------------|--------|
| `UPTIMEROBOT_API_KEY fehlt` | `.env` anlegen und API-Schlüssel eintragen |
| `config.yaml nicht gefunden` | `cp config.example.yaml config.yaml` |
| `Keine Kunden in der Konfiguration` | Mindestens einen Eintrag unter `customers` anlegen |
| `Monitor … nicht gefunden` | Monitor-ID in Uptime Robot prüfen |
| `Uptime Robot API-Fehler` | API-Schlüssel und Internetverbindung prüfen |

## Projektstruktur

```
.
├── generate_reports.py   # Hauptskript
├── config.yaml           # Ihre Kunden-Konfiguration (nicht committen)
├── config.example.yaml   # Vorlage für config.yaml
├── mail_template.txt     # E-Mail-Textvorlage
├── .env                  # API-Schlüssel (nicht committen)
├── .env.example          # Vorlage für .env
├── requirements.txt      # Python-Abhängigkeiten
└── output/               # Erzeugte Kunden-Mails
```
