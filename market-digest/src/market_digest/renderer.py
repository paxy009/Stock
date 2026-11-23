"""Markdown renderer following 02_REPORT_TEMPLATE. No network access, deterministic output."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any
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
    return NA if v is None else f"{v:+.2f} p.p".replace(".", ",", 1)


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

    def other_sessions() -> str:
        # Canada and Australia close ~14h apart; one shared date would mislead.
        labels = {"XTSE": "Kanada", "XASX": "Australia"}
        found: dict[str, date] = {}
        for r in ev.rows:
            ls = r.metrics.last_session
            if r.exchange in labels and ls is not None:
                found[r.exchange] = max(found.get(r.exchange, ls), ls)
        if not found:
            return sess("other_developed")
        return " / ".join(f"{labels[x]} {found[x].isoformat()}" for x in labels if x in found)

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
      f"{other_sessions()}  ")
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
    w("**Na co zwrócić uwagę w kolejnym dniu sesyjnym:** " + _next_up(ev))
    w("")
    w("## 1. Rynek w liczbach — globalne rynki rozwinięte")
    w("")
    w("Każdy wiersz ma własną datę sesji i walutę; ETF-y notowane w USA są **proxy ekspozycji "
      "na region**, a nie lokalną sesją giełdową.")
    w("")
    w("| Region / instrument | Waluta / baza | Ostatni kurs | 1 sesja | 5 sesji | 21 sesji | YTD "
      "| Od szczytu 52 tyg. | 21 sesji w PLN | Dane z |")
    w("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    snapshot = [r for r in ev.rows if r.kind in ("etf", "index") and r.eligibility == "eligible"
                and r.sector is None]
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
    _render_changes(ev, w)
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
    for title in ("6. AI, infrastruktura i przewaga konkurencyjna",):
        w(f"## {title}")
        w("")
        w(UNAVAILABLE)
        w("")
    _render_sectors(ev, w)
    for title in ("8. Główne scenariusze: wzrostowy, neutralny, spadkowy",
                  "9. Opinie z internetu — fact-check"):
        w(f"## {title}")
        w("")
        w(UNAVAILABLE)
        w("")
    _render_upcoming(ev, w)
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


def _render_changes(ev: EvidencePackage, w: Callable[[str], None]) -> None:
    ch = ev.changes
    if ch is None or ch.prev_report_date is None:
        w("Brak wcześniejszego raportu w archiwum — porównanie pojawi się od następnego raportu.")
        w("")
        return
    w(f"Porównanie z raportem z **{ch.prev_report_date}**.")
    w("")
    if ch.rows:
        w("| Obszar | Poprzednio | Teraz | Znaczenie |")
        w("|---|---|---|---|")
        for c in ch.rows:
            w(f"| {c.area} | {c.before} | {c.now} | {c.meaning} |")
        w("")
    else:
        w("Brak zmian w monitorowanych wartościach.")
        w("")
    if ch.unchanged_sessions:
        w(f"- **Bez nowej sesji od poprzedniego raportu:** {', '.join(ch.unchanged_sessions)} "
          "(ceny bez zmian — to nie jest ruch 0%).")
    events = "; ".join(f"[{t}]({u}) ({s})" for t, s, u in ch.new_events) or "brak"
    w(f"- **Nowe potwierdzone wydarzenia:** {events}.")
    follow = "; ".join(f"[{t}]({u}) (+{n} nowe źródło/a)" for t, n, u in ch.followups) or "brak"
    w(f"- **Nowe informacje w istniejących sprawach:** {follow}.")
    filings = "; ".join(f"[{label}]({u})" for label, u in ch.new_filings) or "brak"
    w(f"- **Nowe zgłoszenia SEC:** {filings}.")
    w(f"- **Sprostowania / zmiany danych:** {'; '.join(ch.corrections) or 'brak'}.")
    w("")
    w("*Ruch „między raportami” liczony od ceny z dnia sesji poprzedniego raportu, według "
      "aktualnych danych dostawcy (uwzględnia splity i korekty).*")
    w("")


KIND_LABEL = {"central_bank": "bank centralny", "earnings": "wyniki spółki",
              "market_closure": "kalendarz giełdy"}


def _event_line(u: Any) -> str:
    est = " *(data szacunkowa — do potwierdzenia przez spółkę)*" if u.certainty == "estimated" else ""
    return (f"**{u.day.isoformat()} ({DAYS_PL[u.day.weekday()]})** — {u.title}{est} "
            f"[{u.source_name}]({u.source_url})")


def _next_up(ev: EvidencePackage) -> str:
    if not ev.upcoming:
        return "brak zaplanowanych wydarzeń w skonfigurowanych źródłach na najbliższe dni."
    first_day = ev.upcoming[0].day
    same = [u for u in ev.upcoming if u.day == first_day][:3]
    return "; ".join(f"{u.day.isoformat()}: {u.title}" for u in same) + " (szczegóły w sekcji 10)."


def _render_upcoming(ev: EvidencePackage, w: Callable[[str], None]) -> None:
    w("## 10. Co warto obserwować dalej?")
    w("")
    if not ev.upcoming:
        w("Brak zaplanowanych wydarzeń w skonfigurowanych źródłach w najbliższym tygodniu.")
        w("")
        return
    w("Najbliższe wydarzenia w kolejnych dniach:")
    w("")
    for i, u in enumerate(ev.upcoming, 1):
        w(f"{i}. {_event_line(u)} — *{KIND_LABEL.get(u.kind, u.kind)}, "
          f"{REGION_LABELS.get(u.region, u.region)}*")
    w("")
    w("*Daty posiedzeń Fed/EBC z oficjalnych kalendarzy; daty wyników spółek z Yahoo Finance są "
      "szacunkowe, dopóki spółka ich nie potwierdzi. Dni bez sesji wg exchange_calendars.*")
    w("")


SECTOR_LABELS = {"commodities": "Surowce (kontrakty terminowe)", "energy": "Energia",
                 "banks": "Banki / finanse", "uranium": "Uran i energetyka jądrowa"}
SIGNIFICANT_1D = 2.0
SIGNIFICANT_5D = 5.0


def _significant(r: InstrumentRow) -> bool:
    m = r.metrics
    return ((m.ret_1d is not None and abs(m.ret_1d) >= SIGNIFICANT_1D)
            or (m.ret_5d is not None and abs(m.ret_5d) >= SIGNIFICANT_5D))


def _render_sectors(ev: EvidencePackage, w: Callable[[str], None]) -> None:
    w("## 7. Sektory dodatkowe: uran, energia, banki, surowce")
    w("")
    rows = [r for r in ev.rows if r.sector in SECTOR_LABELS
            and r.eligibility in ("eligible", "benchmark_only") and r.metrics.last_close is not None]
    if not rows:
        w("Brak danych sektorowych w tym przebiegu.")
        w("")
        return
    w("| Sektor | Instrument | Waluta | Ostatni kurs | 1 sesja | 5 sesji | 21 sesji | YTD | Dane z |")
    w("|---|---|---|---:|---:|---:|---:|---:|---|")
    order = list(SECTOR_LABELS)
    for r in sorted(rows, key=lambda x: (order.index(x.sector or ""), x.kind != "future", x.symbol)):
        m = r.metrics
        kind = " · kontrakt ciągły" if r.kind == "future" else (" · ETF" if r.kind == "etf" else "")
        w(f"| {SECTOR_LABELS[r.sector or '']} | {r.name} ({r.symbol}){kind} | {r.currency} | "
          f"{num(m.last_close)} | {pct(m.ret_1d)} | {pct(m.ret_5d)} | {pct(m.ret_21d)} | "
          f"{pct(m.ret_ytd)} | {_d(m.last_session)} |")
    w("")
    sig = [r for r in rows if _significant(r)]
    if sig:
        parts = [f"{r.symbol} {pct(r.metrics.ret_1d)} (1 sesja), {pct(r.metrics.ret_5d)} (5 sesji)"
                 for r in sorted(sig, key=lambda x: -abs(x.metrics.ret_5d or 0.0))]
        w(f"**Istotne ruchy** (próg: ±{SIGNIFICANT_1D:.0f}% w 1 sesji lub ±{SIGNIFICANT_5D:.0f}% "
          f"w 5 sesjach): " + "; ".join(parts) + ". Przyczyny nie zostały zweryfikowane.")
    else:
        w(f"Brak istotnych ruchów w sektorach (próg: ±{SIGNIFICANT_1D:.0f}% w 1 sesji lub "
          f"±{SIGNIFICANT_5D:.0f}% w 5 sesjach).")
    w("")
    w("*Kontrakty ciągłe (=F) zawierają efekt rolowania serii i nie są ceną spot. Cena akcji "
      "spółek uranowych to nie cena uranu — notowania U3O8 nie są dostępne w darmowych źródłach. "
      "XLF to cały sektor finansowy USA, nie tylko banki. ETF-y z istotnym udziałem emitentów EM "
      "(np. URA) są wyłączone z zakresu.*")
    w("")
