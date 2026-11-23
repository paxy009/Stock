"""Typed configuration loaded from YAML. Secrets are never read from the file."""

from __future__ import annotations

from datetime import time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RegionId = Literal["us", "developed_europe", "developed_asia", "other_developed", "global"]
InstrumentKind = Literal["equity", "etf", "index", "future", "fx"]
Role = Literal["watch", "benchmark_only", "fx_only"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AppConfig(_Strict):
    timezone: str = "Europe/Warsaw"
    db_path: Path = Path("data/market.db")
    reports_dir: Path = Path("reports")


class CoverageConfig(_Strict):
    classification_provider: str = "MSCI"
    classification_name: str = "Developed Markets"
    classification_as_of: str | None = None
    developed_countries: frozenset[str]
    explicitly_excluded_countries: frozenset[str] = frozenset({"PL"})
    required_regions: tuple[RegionId, ...] = ("us", "developed_europe", "developed_asia")
    min_region_coverage: float = Field(0.8, ge=0, le=1)

    @field_validator("developed_countries", "explicitly_excluded_countries", mode="before")
    @classmethod
    def _upper(cls, v: object) -> object:
        if isinstance(v, list | tuple | set | frozenset):
            return frozenset(str(x).upper() for x in v)
        return v


class InstrumentConfig(_Strict):
    symbol: str
    name: str
    kind: InstrumentKind
    region: RegionId
    currency: str
    exchange: str  # exchange_calendars code, e.g. XNYS, XTKS
    role: Role = "watch"
    issuer_country: str | None = None
    exposure_countries: frozenset[str] | None = None  # ETF/index mandate
    is_regional_proxy: bool = False
    benchmark: str | None = None
    sector: Literal["commodities", "energy", "banks", "uranium"] | None = None  # section 7
    verified: bool = True  # provider symbol confirmed (doctor)
    eligibility_override: Literal["requires_review", "excluded"] | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> InstrumentConfig:
        if self.kind == "equity" and not self.issuer_country:
            raise ValueError(f"{self.symbol}: equity wymaga issuer_country")
        if self.kind in ("etf", "index") and self.exposure_countries is None:
            raise ValueError(f"{self.symbol}: {self.kind} wymaga exposure_countries")
        return self


class FeedConfig(_Strict):
    id: str
    name: str
    url: str
    tier: Literal["official", "media", "specialist"] = "official"
    region: RegionId = "global"


class NewsConfig(_Strict):
    feeds: tuple[FeedConfig, ...] = ()
    lookback_hours: int = 36
    max_items_per_feed: int = 40
    timeout_seconds: float = 15.0


class ScheduleConfig(_Strict):
    local_time: time = time(23, 30)
    timezone: str = "Europe/Warsaw"


class ReportConfig(_Strict):
    min_key_takeaways: int = 3
    max_key_takeaways: int = 5
    max_featured_events: int = 5
    fx_reporting_currency: str | None = "PLN"


class LlmConfig(_Strict):
    provider: Literal["template"] = "template"


class DeliveryConfig(_Strict):
    """Only env var *names* live here; values come from the environment (GitHub Secrets)."""

    enabled: bool = False
    channel: Literal["email"] = "email"
    smtp_host_env: str = "SMTP_HOST"
    smtp_port_env: str = "SMTP_PORT"
    smtp_username_env: str = "SMTP_USERNAME"
    smtp_password_env: str = "SMTP_PASSWORD"
    recipient_env: str = "DIGEST_RECIPIENT_EMAIL"
    retries: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = 10.0
    timeout_seconds: float = 30.0


class MacroSeriesConfig(_Strict):
    id: str
    name: str
    region: RegionId = "us"
    unit: str = "%"
    transform: Literal["level", "yoy"] = "level"


class FundamentalsConfig(_Strict):
    enabled: bool = False
    # SEC fair access requires a declared contact; e-mail is read from this env var.
    user_agent_env: str = "SEC_USER_AGENT"
    refresh_hours: float = 20.0
    filings_lookback_days: int = 7


class MacroConfig(_Strict):
    enabled: bool = False
    refresh_hours: float = 6.0
    lookback_days: int = 800
    series: tuple[MacroSeriesConfig, ...] = ()


class UpcomingConfig(_Strict):
    enabled: bool = False
    horizon_days: int = Field(default=7, ge=1, le=31)
    weekly_horizon_days: int = Field(default=7, ge=1, le=31)  # Sunday "next week" calendar
    refresh_hours: float = 20.0
    central_banks: bool = True
    earnings: bool = True
    market_closures: bool = True


class AiConfig(_Strict):
    """Section 6. Requires fundamentals.enabled; tickers must be US 10-Q/10-K filers."""

    enabled: bool = True
    hyperscalers: tuple[str, ...] = ("MSFT", "GOOGL", "AMZN", "META")
    suppliers: tuple[str, ...] = ("NVDA", "AVGO", "AMD")


class ClaimsConfig(_Strict):
    path: Path = Path("claims.yaml")


class Config(_Strict):
    app: AppConfig = AppConfig()
    coverage: CoverageConfig
    schedule: ScheduleConfig = ScheduleConfig()
    report: ReportConfig = ReportConfig()
    news: NewsConfig = NewsConfig()
    llm: LlmConfig = LlmConfig()
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    fundamentals: FundamentalsConfig = Field(default_factory=FundamentalsConfig)
    macro: MacroConfig = Field(default_factory=MacroConfig)
    upcoming: UpcomingConfig = Field(default_factory=UpcomingConfig)
    ai: AiConfig = Field(default_factory=AiConfig)
    claims: ClaimsConfig = Field(default_factory=ClaimsConfig)
    price_history_days: int = 400
    instruments: tuple[InstrumentConfig, ...]
    fx_pairs: dict[str, str] = Field(default_factory=dict)  # "USD" -> "USDPLN=X"

    @model_validator(mode="after")
    def _check_refs(self) -> Config:
        symbols = [i.symbol for i in self.instruments]
        dupes = {s for s in symbols if symbols.count(s) > 1}
        if dupes:
            raise ValueError(f"Zduplikowane symbole: {sorted(dupes)}")
        known = set(symbols)
        for inst in self.instruments:
            if inst.benchmark and inst.benchmark not in known:
                raise ValueError(f"{inst.symbol}: nieznany benchmark {inst.benchmark}")
        return self

    def instrument(self, symbol: str) -> InstrumentConfig:
        for inst in self.instruments:
            if inst.symbol == symbol:
                return inst
        raise KeyError(symbol)


def load_config(path: Path) -> Config:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config.model_validate(data)
