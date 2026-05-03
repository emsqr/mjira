"""Tiny SMTP sender. Points at MailHog locally; same code talks to any
real SMTP relay in production."""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)

SMTP_HOST = os.environ["SMTP_HOST"]
SMTP_PORT = int(os.environ["SMTP_PORT"])
SMTP_FROM = os.environ["SMTP_FROM"]


def send(*, to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5) as s:
            s.send_message(msg)
    except Exception:
        log.exception("failed to send email to %s", to)
