#!/usr/bin/env python3
"""
Versendet erzeugte Kunden-Mails per Google Workspace (SMTP).
"""

from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

from generate_reports import (
    CustomerConfig,
    ReportPeriod,
    load_config,
    parse_customers,
    resolve_report_period,
    safe_filename,
)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def report_path(output_dir: Path, customer: CustomerConfig, period: ReportPeriod) -> Path:
    base_name = customer.filename or safe_filename(customer.email)
    return output_dir / f"{base_name}_{period.year}-{period.month:02d}.txt"


def build_subject(period: ReportPeriod) -> str:
    return f"Monatliches Reporting für {period.label}"


def send_mail(
    *,
    smtp_user: str,
    smtp_password: str,
    from_name: str | None,
    to: str,
    subject: str,
    body: str,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{from_name} <{smtp_user}>" if from_name else smtp_user
    message["To"] = to
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Versendet Verfügbarkeitsberichte per Google Workspace."
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
        help="Nur anzeigen, keine E-Mails versenden",
    )
    parser.add_argument(
        "--only",
        metavar="EMAIL",
        help="Nur an diese Kunden-E-Mail senden",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv()

    smtp_user = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_APP_PASSWORD")
    from_name = os.getenv("SMTP_FROM_NAME")

    if not args.dry_run:
        if not smtp_user:
            print("Fehler: SMTP_EMAIL fehlt (.env anlegen, siehe .env.example).", file=sys.stderr)
            return 1
        if not smtp_password:
            print(
                "Fehler: SMTP_APP_PASSWORD fehlt (.env anlegen, siehe .env.example).",
                file=sys.stderr,
            )
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

    if args.only:
        customers = [c for c in customers if c.email == args.only]
        if not customers:
            print(f"Fehler: Kein Kunde mit E-Mail {args.only!r} gefunden.", file=sys.stderr)
            return 1

    period = resolve_report_period(config, args.year, args.month)
    output_dir = Path(config.get("report", {}).get("output_dir", "output"))
    subject = build_subject(period)

    print(f"Versand für {period.label} …")

    for customer in customers:
        path = report_path(output_dir, customer, period)
        if not path.exists():
            print(f"Fehler: Bericht nicht gefunden: {path}", file=sys.stderr)
            return 1

        body = path.read_text(encoding="utf-8")

        if args.dry_run:
            print(f"\n{'=' * 60}")
            print(f"An:   {customer.email}")
            print(f"Von:  {from_name or smtp_user or '(nicht gesetzt)'}")
            print(f"Betreff: {subject}")
            print(f"Datei: {path}")
            print(f"{'=' * 60}\n")
            print(body)
            continue

        send_mail(
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            from_name=from_name,
            to=customer.email,
            subject=subject,
            body=body,
        )
        print(f"Gesendet: {customer.email}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
