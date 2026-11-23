from __future__ import annotations

import smtplib
from datetime import UTC, timedelta
from email.message import EmailMessage

import pytest

from market_digest import pipeline
from market_digest.config import Config, DeliveryConfig
from market_digest.delivery import DeliveryConfigError, SmtpSettings, send_with_retry
from market_digest.storage import Storage
from tests.conftest import FakeCalendar
from tests.test_pipeline import MONDAY, NOW, _news, _prices

ENV = {"SMTP_HOST": "smtp.test", "SMTP_PORT": "465", "SMTP_USERNAME": "from@test",
       "SMTP_PASSWORD": "abcd efgh ijkl mnop", "DIGEST_RECIPIENT_EMAIL": "to@test"}


class FakeMailer:
    def __init__(self, fail_times: int = 0, exc: Exception | None = None) -> None:
        self.sent: list[EmailMessage] = []
        self.fail_times = fail_times
        self.exc = exc or ConnectionError("down")
        self.calls = 0

    def send(self, msg: EmailMessage) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise self.exc
        self.sent.append(msg)


def _generated(cfg: Config) -> Storage:
    st = Storage(cfg.app.db_path)
    pipeline.fetch(cfg, st, _prices(), _news(), NOW)
    pipeline.generate(cfg, st, FakeCalendar(), NOW)
    return st


def _deliver(cfg: Config, st: Storage, mailer: FakeMailer) -> pipeline.DeliverOutcome:
    return pipeline.deliver(cfg, st, MONDAY, mailer, "from@test", "to@test", NOW)


def test_settings_from_env_strips_app_password_spaces() -> None:
    s = SmtpSettings.from_env(DeliveryConfig(), ENV)
    assert s.password == "abcdefghijklmnop" and s.port == 465


def test_missing_env_reports_names_not_values() -> None:
    with pytest.raises(DeliveryConfigError) as e:
        SmtpSettings.from_env(DeliveryConfig(), {**ENV, "SMTP_PASSWORD": ""})
    assert "SMTP_PASSWORD" in str(e.value) and "abcd" not in str(e.value)


def test_sends_md_attachment_with_status_subject(cfg: Config) -> None:
    st = _generated(cfg)
    mailer = FakeMailer()
    out = _deliver(cfg, st, mailer)
    assert out.status == "sent"
    msg = mailer.sent[0]
    assert msg["Subject"] == "Market Digest | 2025-11-24 | Complete"
    att = next(msg.iter_attachments())
    assert att.get_filename() == "2025-11-24.md"
    assert att.get_content_type() == "text/markdown"
    body = msg.get_body(preferencelist=("plain",))
    assert body is not None and "Ostatnie zakończone sesje" in body.get_content()


def test_second_delivery_is_not_duplicated(cfg: Config) -> None:
    st = _generated(cfg)
    mailer = FakeMailer()
    _deliver(cfg, st, mailer)
    again = _deliver(cfg, st, mailer)
    assert again.status == "already_sent"
    assert len(mailer.sent) == 1


def test_failed_delivery_can_be_retried_without_regenerating(cfg: Config) -> None:
    cfg = cfg.model_copy(update={"delivery": DeliveryConfig(retries=1, retry_delay_seconds=0)})
    st = _generated(cfg)
    runs_before = st.next_report_version(MONDAY)
    assert _deliver(cfg, st, FakeMailer(fail_times=5)).status == "failed"
    ok = FakeMailer()
    assert _deliver(cfg, st, ok).status == "sent"
    assert st.next_report_version(MONDAY) == runs_before
    assert len(ok.sent) == 1


def test_new_report_version_with_changed_content_is_sent(cfg: Config) -> None:
    st = _generated(cfg)
    mailer = FakeMailer()
    _deliver(cfg, st, mailer)
    st.conn.execute("DELETE FROM prices WHERE symbol='EWJ'")
    pipeline.generate(cfg, st, FakeCalendar(), NOW)
    assert _deliver(cfg, st, mailer).status == "sent"
    assert mailer.sent[1]["Subject"].endswith("| Partial")


def test_no_report_means_no_email(cfg: Config) -> None:
    st = Storage(cfg.app.db_path)
    mailer = FakeMailer()
    assert _deliver(cfg, st, mailer).status == "no_report"
    assert not mailer.sent


def test_transient_errors_retried_permanent_not() -> None:
    msg = EmailMessage()
    msg["Message-ID"] = "<x@y>"
    flaky = FakeMailer(fail_times=2)
    assert send_with_retry(flaky, msg, 3, 0, sleep=lambda _: None).status == "sent"
    auth = FakeMailer(fail_times=9, exc=smtplib.SMTPAuthenticationError(535, b"bad"))
    res = send_with_retry(auth, msg, 3, 0, sleep=lambda _: None)
    assert res.status == "failed" and res.error_category == "auth" and auth.calls == 1


def test_heartbeat_source(cfg: Config) -> None:
    st = _generated(cfg)
    assert st.last_successful_delivery() is None
    _deliver(cfg, st, FakeMailer())
    last = st.last_successful_delivery()
    assert last is not None and NOW - last < timedelta(minutes=1)
    assert last.tzinfo is not None and last.astimezone(UTC) == NOW


def test_preview_has_no_markdown_links() -> None:
    md = ("> **Ostatnie zakończone sesje (wg rynku):** USA: 2025-11-24  \n"
          "## TL;DR\n\n1. **A** x [źródło](https://a.net)\n\n## 1. X\n")
    out = pipeline._preview(md, "Complete")
    assert "USA: 2025-11-24" in out and "1. A x" in out


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2025-11-24T23:35+01:00", "2025-11-24T23:30+01:00"),  # on time
        ("2025-11-25T00:40+01:00", "2025-11-24T23:30+01:00"),  # late start after midnight
        ("2025-03-30T00:20+01:00", "2025-03-29T23:30+01:00"),  # night before DST switch
        ("2025-11-25T14:00+01:00", "2025-11-25T14:00+01:00"),  # manual daytime run untouched
    ],
)
def test_scheduled_moment_keeps_report_date(cfg: Config, now: str, expected: str) -> None:
    from datetime import datetime

    got = pipeline.scheduled_moment(datetime.fromisoformat(now).astimezone(UTC), cfg)
    assert got == datetime.fromisoformat(expected).astimezone(UTC)
