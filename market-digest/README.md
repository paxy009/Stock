# Market Digest

Prywatny generator codziennego raportu rynkowego po polsku (`reports/YYYY-MM-DD.md`) dla
**globalnych rynków rozwiniętych** (MSCI Developed Markets jako punkt odniesienia), **bez Polski
i rynków wschodzących**. Nie jest systemem transakcyjnym ani rekomendacją inwestycyjną.

## Status: Etap 1 (MVP, uruchamianie ręczne)

| Jest | Nie ma jeszcze (kolejne etapy) |
|---|---|
| Ceny z yfinance → SQLite; metryki 1D/5D/21D/YTD, spadek od szczytu 52 tyg., wynik względem benchmarku, 21 sesji w PLN | Wysyłka e-mail, harmonogram GitHub Actions, trwały storage (Etap 2) |
| Osobne kalendarze sesji (USA, Xetra, Tokio, Toronto, Sydney) przez `exchange_calendars` | LLM (Copilot SDK / API) — na razie wyłącznie `TemplateProvider` |
| Filtr geograficzny (kraj emitenta / ekspozycja ETF; PL i EM wykluczone; SMH tylko benchmark) | SEC, FRED, banki centralne, wyniki spółek (Etap 3) |
| RSS (Fed, SEC, ECB, BoE, BoJ): dedup, grupowanie, ranking, ochrona przed prompt injection | Sekcje 2 i 4–10 raportu: „Moduł niedostępny w tej wersji” |
| QA raportu (brak placeholderów, URL tylko ze snapshotu), zapis atomowy, idempotencja | |

## Instalacja

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Użycie

```bash
market-digest doctor          # konfiguracja, kwalifikacja, dostępność symboli u dostawcy
market-digest run             # fetch + raport -> reports/YYYY-MM-DD.md
market-digest fetch           # tylko pobranie danych
market-digest report          # raport z danych w SQLite (offline)
market-digest run --at 2026-11-23T23:30+01:00   # odtworzenie dla wskazanego momentu
market-digest report --force  # nowa wersja raportu mimo braku zmian danych
```

Powtórny `run` z identycznymi danymi nie tworzy nowej wersji (porównanie fingerprintu wejścia).

### Lokalne indeksy

`^GSPC`, `^STOXX`, `^N225`, `^GSPTSE`, `^AXJO` mają w `config.yaml` ustawione `verified: false` i są
pomijane (raport wymienia je w sekcji ograniczeń). Uruchom `market-digest doctor`, sprawdź, czy
symbol zwraca właściwy instrument, i dopiero wtedy ustaw `verified: true`. Do tego czasu regiony
reprezentują oznaczone ETF-y proxy notowane w USA (VGK, EWJ, EWC, EWA).

## Testy

```bash
ruff check . && mypy && pytest
```

Testy działają offline (stałe dane wejściowe). Obejmują m.in. porównanie poniedziałku z piątkiem,
split bez fałszywego drawdownu, brak tickera, duplikaty newsów, fallback LLM, wymyślone URL-e,
święta w USA i Japonii, przejście na czas letni, filtr PL/EM i przeliczenie stopy zwrotu na PLN.
CI: `.github/workflows/ci.yml`.

## Ograniczenia i licencje

- **yfinance / Yahoo Finance**: nieoficjalne API, wyłącznie do użytku osobistego/research; dane
  mogą być opóźnione lub korygowane. Dostawca jest wymienny (`PriceProvider`).
- RSS: zapisywane są tylko tytuł, link i krótki lead; treść traktowana jako niezaufana.
- Lista krajów DM w `config.yaml` wymaga potwierdzenia z aktualną klasyfikacją MSCI
  (`classification_as_of`).
- Kalendarz STOXX Europe 600 jest przybliżony kalendarzem Xetra.

## Plan Etapu 2 (docelowo GitHub Actions)

Workflow z harmonogramem 23:30 `Europe/Warsaw` i `workflow_dispatch`, stan (`market.db`,
`reports/`) w gałęzi `data`, blokada przez `concurrency`, SMTP z kluczem idempotencji, sekrety
w GitHub Secrets oraz alert, jeśli raport nie dotrze.
