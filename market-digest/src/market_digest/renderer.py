"""Markdown renderer following 02_REPORT_TEMPLATE. No network access, deterministic output."""

from __future__ import annotations

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
    latest = max((e.published_at_utc for e in ev.events if e.published_at_utc), default=None)
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
    for title in ("4. Wyniki finansowe, wyceny i jakość biznesu",
                  "5. Makro — USA i pozostałe rynki rozwinięte",
                  "6. AI, infrastruktura i przewaga konkurencyjna",
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
