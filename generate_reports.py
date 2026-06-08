#!/usr/bin/env python3
"""
Liest Uptime-Robot-Daten und erstellt Kunden-Mails für den Monatsbericht.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml
from dotenv import load_dotenv

API_URL = "https://api.uptimerobot.com/v2/getMonitors"
LOG_TYPE_DOWN = 1

GERMAN_MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)

DEFAULT_SALUTATION = "Liebe Kundin,\nLieber Kunde,"


@dataclass
class MonitorConfig:
    id: int
    domain: str | None = None


@dataclass
class CustomerConfig:
    email: str
    monitors: list[MonitorConfig]
    filename: str | None = None
    salutation: str = DEFAULT_SALUTATION


@dataclass
class ReportPeriod:
    year: int
    month: int
    start_ts: int
    end_ts: int

    @property
    def label(self) -> str:
        return f"{GERMAN_MONTHS[self.month - 1]} {self.year}"


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def resolve_report_period(config: dict[str, Any], year: int | None, month: int | None) -> ReportPeriod:
    report_cfg = config.get("report", {})
    resolved_year = year or report_cfg.get("year")
    resolved_month = month or report_cfg.get("month")

    now = datetime.now()
    if resolved_year is None or resolved_month is None:
        if now.month == 1:
            resolved_year = now.year - 1
            resolved_month = 12
        else:
            resolved_year = now.year
            resolved_month = now.month - 1

    start = datetime(resolved_year, resolved_month, 1, 0, 0, 0)
    if resolved_month == 12:
        end = datetime(resolved_year + 1, 1, 1, 0, 0, 0)
    else:
        end = datetime(resolved_year, resolved_month + 1, 1, 0, 0, 0)

    return ReportPeriod(
        year=resolved_year,
        month=resolved_month,
        start_ts=int(start.timestamp()),
        end_ts=int(end.timestamp()) - 1,
    )


def parse_customers(config: dict[str, Any]) -> list[CustomerConfig]:
    customers: list[CustomerConfig] = []
    for entry in config.get("customers", []):
        monitors = [
            MonitorConfig(id=int(item["id"]), domain=item.get("domain"))
            for item in entry.get("monitors", [])
        ]
        customers.append(
            CustomerConfig(
                email=entry["email"],
                monitors=monitors,
                filename=entry.get("filename"),
                salutation=entry.get("salutation", DEFAULT_SALUTATION),
            )
        )
    return customers


def collect_monitor_ids(customers: list[CustomerConfig]) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for customer in customers:
        for monitor in customer.monitors:
            if monitor.id not in seen:
                seen.add(monitor.id)
                ids.append(monitor.id)
    return ids


def fetch_monitors(
    api_key: str,
    monitor_ids: list[int],
    period: ReportPeriod,
) -> dict[int, dict[str, Any]]:
    if not monitor_ids:
        return {}

    payload = {
        "api_key": api_key,
        "format": "json",
        "monitors": "-".join(str(monitor_id) for monitor_id in monitor_ids),
        "custom_uptime_ranges": f"{period.start_ts}_{period.end_ts}",
        "logs": "1",
        "logs_start_date": str(period.start_ts),
        "logs_end_date": str(period.end_ts),
        "log_types": str(LOG_TYPE_DOWN),
    }

    response = requests.post(API_URL, data=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    if data.get("stat") != "ok":
        raise RuntimeError(f"Uptime Robot API-Fehler: {data.get('message', data)}")

    return {int(monitor["id"]): monitor for monitor in data.get("monitors", [])}


def domain_from_monitor(monitor: dict[str, Any]) -> str:
    url = monitor.get("url") or monitor.get("friendly_name") or ""
    if "://" in url:
        hostname = urlparse(url).hostname or url
    else:
        hostname = url
    return hostname.removeprefix("www.")


def format_uptime(ratio: str | float | None) -> str:
    if ratio is None or ratio == "":
        return "n/a"
    value = float(ratio)
    return f"{value:.3f}%"


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} Sekunden"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} Minute" if minutes == 1 else f"{minutes} Minuten"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if minutes:
        return f"{hours} Stunde{'n' if hours != 1 else ''} {minutes} Minuten"
    return f"{hours} Stunde" if hours == 1 else f"{hours} Stunden"


def format_incident(log: dict[str, Any]) -> str:
    timestamp = datetime.fromtimestamp(int(log["datetime"]))
    duration = format_duration(int(log.get("duration", 0)))
    return f"- {timestamp.strftime('%d.%m.%Y %H:%M')}: Ausfall für {duration}"


def incidents_for_monitor(monitor: dict[str, Any], period: ReportPeriod) -> list[str]:
    incidents: list[str] = []
    for log in monitor.get("logs", []):
        if int(log.get("type", 0)) != LOG_TYPE_DOWN:
            continue
        timestamp = int(log["datetime"])
        if period.start_ts <= timestamp <= period.end_ts:
            incidents.append(format_incident(log))
    return incidents


def uptime_for_monitor(monitor: dict[str, Any]) -> str:
    ratio = monitor.get("custom_uptime_ratio") or monitor.get("custom_uptime_ranges")
    return format_uptime(ratio)


def build_customer_mail(
    customer: CustomerConfig,
    monitors_by_id: dict[int, dict[str, Any]],
    period: ReportPeriod,
    template: str,
) -> str:
    availability_lines: list[str] = []
    all_incidents: list[str] = []

    for monitor_cfg in customer.monitors:
        monitor = monitors_by_id.get(monitor_cfg.id)
        if monitor is None:
            raise RuntimeError(
                f"Monitor {monitor_cfg.id} für {customer.email} nicht in Uptime Robot gefunden."
            )

        domain = monitor_cfg.domain or domain_from_monitor(monitor)
        uptime = uptime_for_monitor(monitor)
        availability_lines.append(
            f"{domain}: {uptime} Verfügbarkeit im {period.label}"
        )
        all_incidents.extend(incidents_for_monitor(monitor, period))

    incidents_text = "\n".join(all_incidents) if all_incidents else "-keine-"

    return template.format(
        salutation=customer.salutation,
        availability_lines="\n\n".join(availability_lines),
        incidents=incidents_text,
    )


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", value, flags=re.UNICODE)
    return cleaned.strip("._") or "kunde"


def write_report(content: str, output_dir: Path, customer: CustomerConfig, period: ReportPeriod) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = customer.filename or safe_filename(customer.email)
    path = output_dir / f"{base_name}_{period.year}-{period.month:02d}.txt"
    path.write_text(content, encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Erstellt Verfügbarkeitsberichte aus Uptime Robot für Kunden."
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Pfad zur Konfigurationsdatei (Standard: config.yaml)",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Berichtsjahr (Standard: Vormonat aus config oder Systemdatum)",
    )
    parser.add_argument(
        "--month",
        type=int,
        help="Berichtsmonat 1-12 (Standard: Vormonat aus config oder Systemdatum)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur auf stdout ausgeben, keine Dateien schreiben",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()

    api_key = os.getenv("UPTIMEROBOT_API_KEY")
    if not api_key:
        print("Fehler: UPTIMEROBOT_API_KEY fehlt (.env anlegen, siehe .env.example).", file=sys.stderr)
        return 1

    if not args.config.exists():
        print(
            f"Fehler: {args.config} nicht gefunden. "
            "Kopieren Sie config.example.yaml nach config.yaml.",
            file=sys.stderr,
        )
        return 1

    config = load_config(args.config)
    customers = parse_customers(config)
    if not customers:
        print("Fehler: Keine Kunden in der Konfiguration.", file=sys.stderr)
        return 1

    period = resolve_report_period(config, args.year, args.month)
    monitor_ids = collect_monitor_ids(customers)
    if not monitor_ids:
        print("Fehler: Keine Monitor-IDs in der Konfiguration.", file=sys.stderr)
        return 1

    template_path = Path(__file__).resolve().parent / "mail_template.txt"
    template = template_path.read_text(encoding="utf-8")

    print(f"Lade Daten für {period.label} …")
    monitors_by_id = fetch_monitors(api_key, monitor_ids, period)

    output_dir = Path(config.get("report", {}).get("output_dir", "output"))

    for customer in customers:
        mail = build_customer_mail(customer, monitors_by_id, period, template)
        if args.dry_run:
            print(f"\n{'=' * 60}\nAn: {customer.email}\n{'=' * 60}\n")
            print(mail)
            continue

        path = write_report(mail, output_dir, customer, period)
        print(f"Erstellt: {path}  (An: {customer.email})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
