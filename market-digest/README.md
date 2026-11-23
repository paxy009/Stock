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

## Sekcja 6: AI i infrastruktura

Dane z faktów XBRL w SEC, które są już w cache:
- **CapEx hyperscalerów** (MSFT, GOOGL, AMZN, META): kwartał i jego zmiana r/r, suma 4 kwartałów
  i jej zmiana r/r, CapEx jako % przychodów oraz łączna suma.
- **Przychody dostawców** (NVDA, AVGO, AMD): kwartał i 4 kwartały, każde ze zmianą r/r.
- **Wyliczanie kwartałów:** w 10-Q przepływy pieniężne są narastające od początku roku (YTD),
  więc kwartał to różnica YTD; Q4 = rok − 9 miesięcy. Suma 4 kwartałów (TTM) powstaje tylko
  wtedy, gdy są wszystkie 4 kwartały.
- **Zastrzeżenia w stopce:** CapEx to wszystkie nakłady, nie tylko AI; przychody to całe
  przychody spółki, nie segment; zbieżność w czasie nie dowodzi rentowności AI.
- **Konfiguracja:** listy spółek w `ai.hyperscalers` i `ai.suppliers`.

## Sekcja 8: scenariusze

Każdy scenariusz (wzrostowy, neutralny, spadkowy) to zestaw obserwowalnych warunków liczonych
z danych, które już są w raporcie:
- S&P 500 względem średniej 50 sesji;
- spadek od szczytu 52 tygodni;
- zmiana z 21 sesji;
- VIX;
- spread rentowności 10Y − 2Y;
- szerokość rynku, czyli ile regionów ma dodatni wynik z 5 sesji.

Raport pokazuje, które warunki są dziś spełnione, a które nie. Brak danych nie liczy się ani
jako spełnienie, ani jako niespełnienie. Progi są umowne (VIX 20/25, korekta −10%, ±3%) i
opisane w stopce. Raport nie podaje **żadnych prawdopodobieństw** ani rekomendacji. Logika jest
w `scenarios.py`.

## Sekcja 7: sektory (surowce, energia, banki, uran)

Instrumenty z polem `sector` w `config.yaml` (symbole sprawdzone w Yahoo 2026-11-23):
- **Surowce:** ropa WTI i Brent, gaz, złoto, srebro, miedź (kontrakty ciągłe `=F`) oraz GLD.
- **Energia:** XLE (benchmark).
- **Banki:** XLF, EUFN (benchmarki), JPM, RY.
- **Uran:** CCJ, UUUU, NXE. URA nie jest dodany, bo ma duży udział emitentów spoza rynków
  rozwiniętych.

Tabela pokazuje zmianę z 1 i 5 sesji, 21 sesji oraz YTD. Raport wyróżnia ruchy ≥ ±2% w 1 sesji
lub ≥ ±5% w 5 sesjach, bez przypisywania przyczyn. Instrumenty sektorowe nie trafiają do
tabeli w sekcji 1 ani do TL;DR i nie wpływają na status `complete`/`partial`.

## Sekcja 10: kalendarz wydarzeń

- **Posiedzenia Fed (FOMC) i EBC:** daty z oficjalnych stron. Raport podaje dzień decyzji, czyli
  ostatni dzień posiedzenia. Jeśli strona zmieni układ i parser nie znajdzie dat, źródło trafia
  do sekcji 11; błąd nie przechodzi po cichu.
- **Daty wyników spółek:** z Yahoo Finance (`Ticker.calendar`), zawsze oznaczone jako
  **szacunkowe**.
- **Dni bez sesji** (święta) na NYSE, Xetra, LSE, Tokio, Toronto i ASX: z `exchange_calendars`.
- **Horyzont:** 7 dni (`upcoming.horizon_days`). Najbliższe wydarzenie trafia też do linii „Na co
  zwrócić uwagę” pod TL;DR. Dane są w cache przez 20 h; przy awarii źródła raport używa
  ostatnich zapisanych danych.

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
