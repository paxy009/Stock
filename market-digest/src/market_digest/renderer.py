"""Markdown renderer following 02_REPORT_TEMPLATE. No network access, deterministic output."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from zoneinfo import ZoneInfo

from market_digest.evidence import REGION_LABELS, EvidencePackage, InstrumentRow
from market_digest.models import ReportContent

DAYS_PL = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
NA = "N/A"
UNAVAILABLE = "_Moduł niedostępny w tej wersji (planowany w kolejnym etapie)._"
REGION_ORDER = ["us", "developed_europe", "developed_asia", "other_developed", "global"]


def pct(v: float | None) -> str:
    return NA if v is None else f"{v:+.2f}%".replace(".", ",")


def pp(v: float | None) -> str:
    return NA if v is None else f"{v:+.2f} p.p.".replace(".", ",", 1)


def num(v: float | None) -> str:
    if v is None:
        return NA
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def _d(d: date | None) -> str:
    return d.isoformat() if d else NA


def _row(r: InstrumentRow) -> str:
    m = r.metrics
    label = f"{REGION_LABELS.get(r.region, r.region)} — {r.name} ({r.symbol})"
    if r.is_regional_proxy:
        label += " · ETF proxy, sesja USA"
    elif r.kind == "index":
        label += " · indeks lokalny"
    flags = f" ⚠ {'; '.join(m.flags)}" if m.flags else ""
    return (f"| {label} | {r.currency} / close | {num(m.last_close)} | {pct(m.ret_1d)} | "
            f"{pct(m.ret_5d)} | {pct(m.ret_21d)} | {pct(m.ret_ytd)} | {pct(m.drawdown_52w)} | "
            f"{pct(m.ret_21d_pln)} | {_d(m.last_session)}{flags} |")


def render(ev: EvidencePackage, content: ReportContent) -> str:
    tz = ZoneInfo(ev.timezone)
    gen_local = ev.generated_at_utc.astimezone(tz)
    by_reg = {r.region: r for r in ev.regions}

    def sess(reg: str) -> str:
        r = by_reg.get(reg)
        return f"{_d(r.last_session)}" if r else NA

    status = ev.content_status if content.generation_mode == "template" else content.generation_mode
    statuses = " · ".join(
        f"{REGION_LABELS.get(r.region, r.region)}: {r.day_status.value}" for r in ev.regions
    )
    out: list[str] = []
    w = out.append
    w(f"# Market Digest — {ev.report_date.isoformat()} ({DAYS_PL[ev.report_date.weekday()]})")
    w("")
    w(f"> **Stan na:** {gen_local:%Y-%m-%d %H:%M} {ev.timezone}  ")
    w(f"> **Ostatnie zakończone sesje (wg rynku):** USA: {sess('us')} · Europa: "
      f"{sess('developed_europe')} · Japonia: {sess('developed_asia')} · Kanada/Australia: "
      f"{sess('other_developed')}  ")
    w(f"> **Rodzaj dnia dla regionów (wg daty raportu):** {statuses}  ")
    w(f"> **Status raportu:** {status} (treść: {ev.content_status}, tryb: {content.generation_mode})  ")
    latest = max((p for e in ev.events if (p := e.published_at_utc) is not None), default=None)
    w(f"> **Źródła aktualizowane do:** {latest.isoformat() if latest else NA} (UTC)  ")
    w(f"> **Wersja danych / run:** {ev.fingerprint()} / {ev.run_id}")
    w("")
    w("## TL;DR — najważniejsze w 60 sekund")
    w("")
    for i, item in enumerate(content.tldr, 1):
        link = f" [{item.url_label}]({item.url})" if item.url else ""
        w(f"{i}. {item.text}{link}")
    w("")
    w(f"**Obraz rynku:** {content.overview}")
    w("")
    w("**Na co zwrócić uwagę w kolejnym dniu sesyjnym:** kalendarz wydarzeń nie jest jeszcze "
      "dostępny w tej wersji.")
    w("")
    w("## 1. Rynek w liczbach — globalne rynki rozwinięte")
    w("")
    w("Każdy wiersz ma własną datę sesji i walutę; ETF-y notowane w USA są **proxy ekspozycji "
      "na region**, a nie lokalną sesją giełdową.")
    w("")
    w("| Region / instrument | Waluta / baza | Ostatni kurs | 1 sesja | 5 sesji | 21 sesji | YTD "
      "| Od szczytu 52 tyg. | 21 sesji w PLN | Dane z |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    snapshot = [r for r in ev.rows if r.kind in ("etf", "index") and r.eligibility == "eligible"]
    snapshot.sort(key=lambda r: (REGION_ORDER.index(r.region), r.kind != "index", r.symbol))
    for r in snapshot:
        w(_row(r))
    w("")
    w("*Metodologia: „1 sesja” porównuje dwa ostatnie zakończone dni notowań właściwej giełdy; "
      "okresy liczone w sesjach. Od szczytu 52 tyg. — na cenach skorygowanych (adj. close). "
      "Zmiany cenowe, nie total return. PLN: (cena₁·FX₁)/(cena₀·FX₀)−1, kursy FX z obu dat. "
      "Wiersze w różnych walutach i strefach nie są bezpośrednio porównywalne.*")
    w("")
    w("### Największe ruchy (spółki z watchlisty)")
    w("")
    movers = [r for r in ev.rows if r.kind == "equity" and r.eligibility == "eligible"
              and r.metrics.ret_1d is not None]
    movers.sort(key=lambda r: (-abs(r.metrics.ret_1d or 0.0), r.symbol))
    if not movers:
        w("Brak danych o ruchach spółek.")
    for r in movers[:5]:
        rel = f"; względem {r.benchmark}: {pp(r.rel_1d_vs_benchmark)}" if r.benchmark else ""
        w(f"- **{r.symbol}** ({r.name}, sesja {_d(r.metrics.last_session)}): "
          f"{pct(r.metrics.ret_1d)}{rel}. **Przyczyna ruchu:** niepotwierdzona.")
    w("")
    w("## 2. Co zmieniło się od poprzedniego raportu?")
    w("")
    w(UNAVAILABLE)
    w("")
    w("## 3. Najważniejsze wiadomości i zdarzenia")
    w("")
    if not ev.events:
        w("Brak nowych wiadomości ze skonfigurowanych źródeł w oknie czasowym.")
    for e in ev.events:
        w(f"### {e.title}")
        w("")
        if e.summary:
            w(f"- **Co wiadomo (wg źródła):** {e.summary}")
        w(f"- **Status:** {'official_statement' if e.tier == 'official' else 'credible_media_report'}.")
        w(f"- **Publikacja:** {e.published_at_utc.isoformat() if e.published_at_utc else NA} (UTC).")
        w("- **Czego jeszcze nie wiadomo:** wpływ na rynek nie został zweryfikowany automatycznie.")
        extra = f" (+{len(e.items) - 1} powiązanych)" if len(e.items) > 1 else ""
        w(f"- **Źródło:** [{e.source_name}]({e.url}){extra}")
        w("")
    _render_fundamentals(ev, w)
    _render_macro(ev, w)
    for title in ("6. AI, infrastruktura i przewaga konkurencyjna",
                  "7. Sektory dodatkowe: uran, energia, banki, surowce",
                  "8. Główne scenariusze: wzrostowy, neutralny, spadkowy",
                  "9. Opinie z internetu — fact-check",
                  "10. Co warto obserwować dalej?"):
        w(f"## {title}")
        w("")
        w(UNAVAILABLE)
        w("")
    w("## 11. Jakość danych i ograniczenia")
    w("")
    cov = "; ".join(f"{REGION_LABELS.get(r.region, r.region)} {r.received}/{r.requested}"
                    for r in ev.regions)
    total_req = sum(r.requested for r in ev.regions)
    total_rec = sum(r.received for r in ev.regions)
    w(f"- **Pokrycie watchlisty:** {total_rec}/{total_req} instrumentów; {cov}.")
    excl = ", ".join(f"{s} ({why})" for s, why in ev.excluded) or "brak"
    w(f"- **Filtr geograficzny:** {ev.classification}; wykluczone/oznaczone: {excl}.")
    stale = [f"{r.symbol} ({'; '.join(r.metrics.flags)})" for r in ev.rows if r.metrics.flags]
    w(f"- **Nieaktualne / brakujące serie:** {', '.join(stale) or 'brak'}.")
    failed = ", ".join(f"{k} ({v})" for k, v in sorted(ev.failed_sources.items())) or "brak"
    w(f"- **Niedostępne źródła:** {failed}.")
    w(f"- **Niezweryfikowane symbole (pominięte):** {', '.join(ev.unverified_symbols) or 'brak'}.")
    w("- **Niepotwierdzone zależności przyczynowe:** wszystkie ruchy cen w tym raporcie.")
    w("- **Licencje:** dane cenowe z yfinance (Yahoo Finance) — wyłącznie użytek osobisty/research.")
    fb = f"tak — {content.fallback_reason}" if content.fallback_reason else "nie"
    w(f"- **Tryb awaryjny LLM:** {fb}.")
    if ev.missing_regions:
        w(f"- **Brakujące regiony:** {', '.join(REGION_LABELS.get(r, r) for r in ev.missing_regions)}.")
    w("")
    w("## 12. Źródła i metodologia")
    w("")
    for i, (url, label) in enumerate(sorted(ev.sources.items(), key=lambda x: x[1]), 1):
        w(f"{i}. [{label}]({url}), pobrano: {ev.generated_at_utc:%Y-%m-%d} (UTC).")
    w("")
    w("Metryki liczone z cen zamknięcia (adj. close dla drawdownu); okresy w sesjach danej giełdy; "
      "kalendarze: exchange_calendars; strefa raportu: " + ev.timezone + ".")
    w("")
    w("---")
    w("")
    w("*Raport informacyjny, nie stanowi indywidualnej rekomendacji inwestycyjnej. Decyzje "
      "wymagają samodzielnej oceny ryzyka.*")
    w("")
    return "\n".join(out)


def money(v: float | None) -> str:
    if v is None:
        return NA
    a = abs(v)
    if a >= 1e9:
        s = f"{v / 1e9:,.1f} mld"
    elif a >= 1e6:
        s = f"{v / 1e6:,.1f} mln"
    else:
        s = f"{v:,.0f}"
    return s.replace(",", " ").replace(".", ",") + " USD"


def plain(v: float | None, digits: int = 2) -> str:
    return NA if v is None else f"{v:.{digits}f}".replace(".", ",")


def _render_fundamentals(ev: EvidencePackage, w: Callable[[str], None]) -> None:
    w("## 4. Wyniki finansowe, wyceny i jakość biznesu")
    w("")
    if not ev.fundamentals:
        w("Brak danych SEC w tym przebiegu (moduł wyłączony lub źródło niedostępne).")
        w("")
        return
    w("| Spółka | Okres (koniec) | Przychody | r/r | Zysk netto | Marża netto | EPS rozw. "
      "| FCF (okres) | P/E TTM | Zgłoszenie |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for f in sorted(ev.fundamentals, key=lambda x: x.ticker):
        kind = {"quarter": "kw.", "annual": "rok"}.get(f.period_kind or "", "?")
        fcf = (f"{money(f.fcf)} ({_d(f.fcf_start)}→{_d(f.fcf_end)})" if f.fcf is not None else NA)
        pe = plain(f.pe_ttm, 1) if f.pe_ttm is not None else (
            "n/d (EPS ≤ 0)" if f.eps_ttm is not None and f.eps_ttm <= 0 else NA)
        w(f"| [{f.ticker}]({f.source_url}) | {kind} {_d(f.period_end)} | {money(f.revenue)} | "
          f"{pct(f.revenue_yoy)} | {money(f.net_income)} | {pct(f.net_margin)} | "
          f"{plain(f.eps_diluted)} | {fcf} | {pe} | {f.form or NA} {_d(f.filed)} |")
    w("")
    w("*Dane raportowane (US-GAAP, XBRL z SEC EDGAR), nie prognozy. r/r = ten sam okres rok "
      "wcześniej. FCF = CFO − CapEx za ten sam okres (YTD w 10-Q), może różnić się od non-GAAP "
      "FCF spółki. P/E TTM = ostatnie zamknięcie / EPS rozwodniony z 4 kwartałów (przybliżenie); "
      "przy EPS ≤ 0 nie podajemy P/E. ADR-y emitentów zagranicznych (20-F/IFRS) nie są objęte.*")
    notes = [f"{f.ticker}: {'; '.join(f.flags)}" for f in ev.fundamentals if f.flags]
    if notes:
        w("")
        w("**Uwagi do danych:** " + " · ".join(sorted(notes)))
    w("")
    w("### Nowe zgłoszenia 8-K (ostatnie dni)")
    w("")
    if not ev.filings:
        w("Brak nowych 8-K dla monitorowanych spółek z USA.")
    for fl in ev.filings[:8]:
        w(f"- **{fl['ticker']}** — {fl['filed']}: {fl['items']}. "
          f"[8-K]({fl['url']}) *(zdarzenie raportowane, nie ocena jakości spółki)*")
    w("")


def _render_macro(ev: EvidencePackage, w: Callable[[str], None]) -> None:
    w("## 5. Makro — USA i pozostałe rynki rozwinięte")
    w("")
    rows = [m for m in ev.macro if m.value is not None]
    if not rows:
        w("Brak danych makro w tym przebiegu (moduł wyłączony lub FRED niedostępny).")
        w("")
        return
    w("| Wskaźnik | Region | Ostatnia wartość | Okres danych | Poprzednio | Zmiana | Źródło |")
    w("|---|---|---:|---|---:|---:|---|")
    for m in rows:
        unit = "" if m.unit == "pkt" else " %"
        chg = NA if m.change is None else (
            f"{m.change:+.2f}".replace(".", ",") + (" p.p." if m.unit == "%" else ""))
        w(f"| {m.name} | {REGION_LABELS.get(m.region, m.region)} | {plain(m.value)}{unit} | "
          f"{_d(m.last_date)} | {plain(m.prev_value)}{unit if m.prev_value is not None else ''}"
          f" ({_d(m.prev_date)}) | {chg} | [FRED {m.series_id}]({m.source_url}) |")
    w("")
    w("*„Okres danych” to okres, którego dotyczy obserwacja (dla danych miesięcznych — miesiąc), "
      "nie data publikacji. Dane dzienne (stopy, rentowności, VIX) — ostatnia dostępna sesja. "
      "CPI/PCE jako zmiana r/r indeksu. Oczekiwania rynku co do przyszłych stóp ≠ bieżąca "
      "decyzja banku centralnego.*")
    w("")
