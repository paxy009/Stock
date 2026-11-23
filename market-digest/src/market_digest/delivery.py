"""E-mail delivery (SMTP) with idempotency. Secrets are read from the environment only."""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Protocol

from market_digest.config import DeliveryConfig

log = logging.getLogger(__name__)


class DeliveryConfigError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    recipient: str

    @classmethod
    def from_env(cls, cfg: DeliveryConfig, env: Mapping[str, str] | None = None) -> SmtpSettings:
        env = os.environ if env is None else env
        names = {
            "host": cfg.smtp_host_env, "port": cfg.smtp_port_env,
            "username": cfg.smtp_username_env, "password": cfg.smtp_password_env,
            "recipient": cfg.recipient_env,
        }
        values = {k: env.get(v, "").strip() for k, v in names.items()}
        missing = [names[k] for k, v in values.items() if not v]
        if missing:
            raise DeliveryConfigError(f"Brak zmiennych środowiskowych: {', '.join(missing)}")
        try:
            port = int(values["port"])
        except ValueError as exc:
            raise DeliveryConfigError(f"{cfg.smtp_port_env} musi być liczbą") from exc
        return cls(values["host"], port, values["username"],
                   values["password"].replace(" ", ""), values["recipient"])


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    status: str  # sent | failed
    delivery_id: str | None = None
    error_category: str | None = None


class Mailer(Protocol):
    def send(self, msg: EmailMessage) -> None: ...


class SmtpMailer:
    def __init__(self, settings: SmtpSettings, timeout: float) -> None:
        self.s = settings
        self.timeout = timeout

    def send(self, msg: EmailMessage) -> None:
        ctx = ssl.create_default_context()
        if self.s.port == 465:
            with smtplib.SMTP_SSL(self.s.host, self.s.port, timeout=self.timeout, context=ctx) as c:
                c.login(self.s.username, self.s.password)
                c.send_message(msg)
        else:
            with smtplib.SMTP(self.s.host, self.s.port, timeout=self.timeout) as c:
                c.starttls(context=ctx)
                c.login(self.s.username, self.s.password)
                c.send_message(msg)


def categorize(exc: BaseException) -> str:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "auth"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "recipient"
    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, OSError | smtplib.SMTPConnectError | smtplib.SMTPServerDisconnected):
        return "network"
    return "other"


PERMANENT = frozenset({"auth", "recipient"})


def build_message(report_path: Path, *, sender: str, recipient: str, subject: str,
                  preview: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="market-digest.local")
    msg.set_content(preview)
    msg.add_attachment(report_path.read_text(encoding="utf-8"), subtype="markdown",
                       filename=report_path.name)
    return msg


def send_with_retry(mailer: Mailer, msg: EmailMessage, retries: int, delay: float,
                    sleep: Callable[[float], None] = time.sleep) -> DeliveryResult:
    last = "other"
    for attempt in range(1, retries + 1):
        try:
            mailer.send(msg)
            return DeliveryResult("sent", str(msg["Message-ID"]))
        except Exception as exc:
            last = categorize(exc)
            # Never log exception text: SMTP errors can echo credentials or addresses
            log.warning("SMTP próba %d/%d nieudana: %s (%s)", attempt, retries, last,
                        type(exc).__name__)
            if last in PERMANENT:
                break
            if attempt < retries:
                sleep(delay * attempt)
    return DeliveryResult("failed", None, last)
