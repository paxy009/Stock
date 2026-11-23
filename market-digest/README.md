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

`^GSPC`, `^STOXX`, `^N225`, `^GSPTSE`, `^AXJO` zostały potwierdzone przez `market-digest doctor`
(2026-11-22) i są aktywne obok oznaczonych ETF-ów proxy (VGK, EWJ, EWC, EWA). Nowy symbol dodawaj
z `verified: false`, sprawdź go przez `doctor` i dopiero wtedy włącz.

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

## Sekcja 2: zmiany od poprzedniego raportu

Raport porównuje swój pakiet dowodów z najnowszą wersją raportu z wcześniejszej daty (archiwum w
SQLite, gałąź `data`). Pokazuje:
- **ruch kursu benchmarków między raportami**, liczony od ceny z dnia sesji poprzedniego raportu
  według aktualnych danych dostawcy, więc split nie tworzy fałszywego spadku;
- **instrumenty bez nowej sesji** (weekend, święto), opisane wprost zamiast jako ruch „0%”;
- **nowe obserwacje makro i nowe raporty okresowe SEC**;
- **nowe wydarzenia oraz nowe źródła w sprawach już opisanych**;
- **nowe 8-K**;
- **sprostowania**: zmiana historycznego kursu u dostawcy, rewizja serii FRED, korekta
  przychodów.

## Etap 3: SEC EDGAR + FRED

- **Sekcja 4 (wyniki):** dla spółek z USA składających 10-Q/10-K, czyli NVDA, MSFT, GOOGL, AMZN,
  META, AMD, AVGO i JPM. Raport pokazuje przychody i ich zmianę r/r, zysk netto, marżę, EPS
  rozwodniony, FCF (CFO − CapEx za ten sam okres) i P/E TTM; przy EPS ≤ 0 P/E nie jest podawane.
  Źródło to XBRL `companyfacts`; przy korekcie danych liczy się najnowsze zgłoszenie. Sekcja
  pokazuje też nowe 8-K z ostatnich 7 dni wraz z opisem pozycji. ADR-y spółek zagranicznych
  (ASML, SAP, TM, BHP) raportują w 20-F/IFRS i nie są objęte tym modułem.
- **Sekcja 5 (makro):** serie FRED zdefiniowane w `config.yaml`: Fed funds, 2Y, 10Y, CPI i PCE
  r/r, bezrobocie, VIX oraz stopa depozytowa ECB. Każda wartość ma okres danych, poprzednią
  obserwację i zmianę.
- **SEC fair access:** wymagany jest `SEC_USER_AGENT` z adresem e-mail. W workflow ustawiany jest
  automatycznie z sekretu `SMTP_USERNAME`. Zapytania są ograniczone do ≤ 5 na sekundę, a dane
  trzymane w cache (`official_cache`) przez 20 h.
- **Awaria źródła:** raport używa ostatnich danych z cache i wymienia źródło w sekcji 11. Brak
  danych SEC/FRED nie zmienia statusu `complete`/`partial`, bo ten zależy od pokrycia cen.
- **Do dodania później:** sprawozdania emitentów spoza USA (EDINET, SEDAR+, ASX, IR) oraz serie
  BoE, BoJ, BoC i RBA, po zweryfikowaniu źródeł i licencji.

## Etap 2: automatyzacja (GitHub Actions)

| Workflow | Kiedy | Co robi |
|---|---|---|
| `daily.yml` | codziennie 23:30 `Europe/Warsaw` + ręcznie | odtwarza stan z gałęzi `data` → `run --scheduled` → `deliver` → zapis stanu do `data` |
| `heartbeat.yml` | codziennie 02:30 `Europe/Warsaw` | błąd (i powiadomienie GitHub), jeśli brak udanej wysyłki w ostatnich 12 h |
| `report.yml` | ręcznie | podgląd raportu jako artefakt, bez wysyłki i zapisu stanu |
| `ci.yml` | push / PR | ruff, mypy, pytest |

- **Sekrety** (Settings → Secrets → Actions): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
  `SMTP_PASSWORD` (Gmail: hasło aplikacji), `DIGEST_RECIPIENT_EMAIL`. Nie trafiają do kodu ani logów.
- **Stan**: `market.db` i `reports/` w osobnej gałęzi `data`; `concurrency` blokuje równoległe zapisy.
- **Bez duplikatów**: klucz `data_raportu:email:sha_treści`; ponowny run tych samych danych nie
  wysyła drugiego maila. Zmieniona treść = nowa wersja = nowy mail.
- **Ponowienie samej wysyłki**: Actions → Daily report → Run workflow → `mode = deliver`.
- **Opóźniony harmonogram**: start po północy nadal tworzy raport z datą poprzedniego dnia
  (`--scheduled`). GitHub nie gwarantuje punktualności.
- Lokalnie: `market-digest run --send`, `market-digest deliver --date 2026-11-23`,
  `market-digest heartbeat` (zmienne SMTP w środowisku).
