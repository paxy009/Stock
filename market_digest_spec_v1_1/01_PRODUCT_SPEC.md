# Market Digest — pełna specyfikacja produktu (PRD + wymagania techniczne)

**Wersja:** 1.1 (skonsolidowanie koncepcji v1–v4 + doprecyzowanie rynków rozwiniętych).  
**Status:** do implementacji, **repozytorium i kod jeszcze nie istnieją**.  
**Data:** 2026-11-22.  
**Właściciel produktu:** prywatny inwestor, programista; rynki rozwinięte globalnie, bez Polski i emerging markets.

---

## 1. Wizja i miara sukcesu

Market Digest ma codziennie generować i dostarczać po polsku **jeden rzetelny, zwięzły raport Markdown**, który pozwala inwestorowi o podstawowej/średniozaawansowanej wiedzy:

1. Zrozumieć **co zmieniło się** od ostatniego raportu i co jest naprawdę ważne.
2. Oddzielić zmianę kursu od zmiany wartości ekonomicznej biznesu, jakości zysków i prognoz.
3. Zrozumieć kontekst stóp procentowych USA i banków centralnych innych rynków rozwiniętych, inflacji, rentowności obligacji i ryzyka recesji.
4. Ocenić scenariusze wzrostowy, neutralny i spadkowy bez fałszywej pewności.
5. Wykryć wiadomości korporacyjne, które zmieniają profil ryzyka spółki.
6. Zweryfikować sensacyjne tezy i prognozy znalezione w internecie, zamiast powielać je jako fakty.
7. Szybko dotrzeć do **oryginalnych źródeł** i sprawdzić, które dane są niepełne.

**Kryterium sukcesu biznesowego:** użytkownik otrzymuje każdego dnia prawidłowo datowany `.md` o stałej strukturze i w ciągu kilku minut rozumie stan rynku, ważne zmiany, ryzyka i obserwowane wydarzenia. Raport powinien być wartościowy nawet wtedy, gdy większość rynku była spokojna.

**Nie jest celem:** automatyczny trading, magiczna prognoza cen, ranking „kup teraz”, śledzenie każdej wypowiedzi w social mediach ani płatna produkcyjna platforma dla wielu klientów.

## 2. Główny produkt — codzienny plik Markdown

| Właściwość | Wymaganie |
|---|---|
| Format | UTF-8 Markdown `.md`, czytelny także bez renderera |
| Nazwa | `reports/YYYY-MM-DD.md` w lokalnej dacie `Europe/Warsaw` |
| Powtarzalność | Jeden logiczny raport dzienny; ponowne uruchomienie aktualizuje lub wersjonuje świadomie, nie wysyła przypadkowych duplikatów |
| Język | Polski, proste wyjaśnienia terminów, liczby z jednostkami |
| Częstotliwość | 7 dni w tygodniu; w dni bez sesji raport „dzień bez sesji / aktualizacja informacji” |
| Godzina docelowa | 23:30 Europe/Warsaw; nie jest to gwarantowana godzina wysyłki przy zawodnym schedulerze |
| Długość | Cel 900–1500 słów w dni sesyjne, krócej gdy brak istotnych wydarzeń; sekcje techniczne i źródła poza głównym streszczeniem |
| Główne obserwacje | 3–5 punktów podsumowania, maksymalnie 5 wydarzeń wyróżnionych jako najważniejsze |
| Linki | Każde istotne twierdzenie ma referencję do źródła i datę informacji |
| Dostarczenie | Pierwszeństwo: e-mail z plikiem `.md` jako załącznikiem; archiwum niezależne od e-maila |
| Braki | Jawne `brak danych`, `dane wstępne`, `niezweryfikowane`; nigdy nie podstawiać zera |
| Wersja | Nagłówek z datą raportu, datami ostatnich ukończonych sesji regionalnych, wersją generatora i `run_id` |

**Weekend i święta:** nie oznaczaj braku handlu jako „0,00% dzisiaj”. Pokaż ostatnie dostępne zamknięcie z datą dla **każdego rynku** (dni wolne mogą się różnić), nowe wiadomości i nadchodzące wydarzenia. W niedzielę dodaj skrót tygodniowy i kalendarz następnego tygodnia.

## 3. Zakres aktywów i obserwacji

**Geografia (obowiązkowy filtr): globalne rynki rozwinięte, bez Polski i rynków wschodzących.** Przyjmij klasyfikację **MSCI Developed Markets** jako punkt odniesienia (z wersją i datą klasyfikacji); na dodatek jawnie wyklucz Polskę. Rynki wschodzące nie mogą trafiać do głównej watchlisty nawet przez ADR notowane w USA. Reguły graniczne opisuje `08_GEOGRAPHY_AND_COVERAGE.md`.

**Regionalny zakres głównego raportu:**

- **USA — największy priorytet:** S&P 500, Nasdaq-100, ważne spółki tech/AI i sektor bankowy.
- **Europa rozwinięta:** m.in. Niemcy, Francja, Wielka Brytania, Holandia, Szwajcaria oraz rynki nordyckie; benchmarki STOXX Europe 600, DAX, CAC 40, FTSE 100 i SMI.
- **Azja rozwinięta:** Japonia (Nikkei 225, TOPIX), Singapur oraz Hongkong z kontrolą kraju emitenta i udziału ekspozycji na Chiny; nie dodawaj automatycznie firm z Chin.
- **Pozostałe rozwinięte:** Kanada, Australia i Nowa Zelandia; benchmarki S&P/TSX i S&P/ASX 200.

**Początkowa watchlista — konfigurowalna, nie jest rekomendacją zakupu:**

- USA: SPY, QQQ, RSP, SMH, VTI, GLD, SGOV, NVDA, MSFT, GOOGL, AMZN, META, AMD, AVGO, JPM, BAC, XLF.
- Europa: regionalne ETF-y `VGK` i `FEZ`, przykładowe spółki `ASML` (Holandia) i `SAP` (Niemcy); lokalne indeksy jako odrębne benchmarki, gdy zweryfikowano symbole dostawcy.
- Japonia i rynki Azji rozwiniętej: `EWJ` oraz przykładowo `TM` (Japonia); indeksy Nikkei 225 i TOPIX po mapowaniu do danych źródłowych.
- Kanada, Australia i inne: `EWC`, `EWA`, przykładowo `RY` (Kanada) i `BHP` (Australia).
- Benchmark globalny rynków rozwiniętych **poza USA**: np. `EFA` (ETF z ekspozycją na rynki rozwinięte; zweryfikuj indeks i skład przed użyciem).
- Uran/energia: CCJ (Kanada), UUUU (USA), URA/URNM **tylko po weryfikacji składu i kwalifikowalności** funduszu względem wyłączenia emerging markets; cena uranu z oddzielnego źródła.
- Surowce/futures: `GC=F` (złoto), `SI=F` (srebro), `CL=F` (ropa), `HG=F` (miedź); porównania globalnych cen surowców nie oznaczają inwestowania w dany kraj.
- Waluty: kursy potrzebne do porównań (np. USD/PLN, EUR/PLN, JPY/PLN, GBP/PLN) oraz DXY, jeśli dane dostępne. PLN służy wyłącznie do przeliczenia wyników, **nie włącza Polski do analizowanych rynków akcji**.

**Kryterium kwalifikacji:** o głównej ekspozycji decyduje **kraj emitenta lub indeks bazowy**, nie samo miejsce notowania instrumentu. ETF notowany w USA może śledzić rynki rozwinięte Europy; ADR z emitentem z emerging markets pozostaje wykluczone. Globalne ETF-y zawierające EM wymagają sprawdzenia składu i nie przechodzą automatycznie filtra. Przykład: `TSM` (emitent tajwański) nie trafia na podstawową listę przy klasyfikacji MSCI. Dane o Chinach, Indiach czy Brazylii można uwzględnić jako **kontekst makro/geopolityczny wpływający na rozwinięte rynki**, nie jako instrumenty rekomendowane do obserwacji inwestycyjnej.

Niektóre aktywa i firmy mogą być dołączane później; status notowań, tickerów, klasyfikacje i uprawnienia źródeł należy **weryfikować w dniu dodania**. Instrumenty z różnych klas nie mogą być analizowane identycznymi metrykami.

## 4. Wymagania funkcjonalne

### FR-01. Konfiguracja

- YAML z kategoriami aktywów, tickerami, benchmarkami, klasyfikacją kraju emitenta/ekspozycji ETF, flagami kwalifikowalności rynków rozwiniętych, strefami czasowymi, źródłami i limitami kosztów.
- Walidacja schematu na starcie, sensowne wartości domyślne, czytelne błędy.
- Sekrety tylko w zmiennych środowiskowych/menedżerze sekretów; przykładowy `.env.example` bez wartości.
- Oddzielne przełączniki dla sekcji opcjonalnych; nieobsługiwane opcje nie mogą być ignorowane po cichu.

### FR-02. Dane rynkowe

- W MVP `yfinance` jako adapter, z możliwością podmiany dostawcy w przyszłości.
- Zachowuj OHLCV i daty ostatnich sesji, pobieraj historię przyrostowo.
- Wskaźniki: 1 sesja, 5 i 21 sesji, 3/6/12M, YTD, dystans od szczytu 52 tygodni, SMA50, SMA200, zmienność 20/60 sesji, relatywna siła do benchmarku.
- Historia: początkowo 3–5 lat spółek i do 10–20 lat benchmarków, **tylko gdy dostawca zapewnia porównywalne dane**.
- Wyraźnie rozróżniaj cenę skorygowaną, total return ETF-ów, walutę, splity i dywidendy.
- Zmiany „1D” liczone między **dwoma zakończonymi sesjami właściwej giełdy**, nie między datami kalendarzowymi. Każdy instrument musi mieć `exchange_timezone`, kalendarz sesyjny i datę ostatniej obserwacji; giełdy europejskie i azjatyckie mają inne święta i godziny niż USA.
- Dla porównań między rynkami: określ wspólny dzień odniesienia, sposób synchronizacji czasu, bazę cenową i walutę; nie zestawiaj zamknięcia ETF-u w USA z lokalnym indeksem azjatyckim jako notowań z tej samej chwili.
- Porównania w PLN: przeliczaj stopy zwrotu z kursami FX odpowiadającymi datom obserwacji, jawnie pokazuj efekt walutowy i dostępność danych FX.
- W przypadku brakującego instrumentu raport jest częściowy, a brak odnotowany.

### FR-03. Newsy i deduplikacja

- Zbieraj oficjalne komunikaty, RSS i krótkie opisy; zachowuj oryginalny URL i czas publikacji UTC.
- Normalizacja linku, hashowanie, deduplikacja podobnych nagłówków oraz grupowanie wielu publikacji o tym samym zdarzeniu.
- Przechowuj oryginalne metadane i ucięty fragment do LLM; nie zakładaj, że streszczenie RSS = pełny artykuł.
- Klasyfikacja: fakt / opinia / prognoza / niezweryfikowany zarzut / reakcja rynkowa / działanie regulatora.
- 3–7 najważniejszych tematów w raporcie, nie „lista 60 nagłówków”.

### FR-04. Wyniki finansowe i wyceny

- W etapie 2: raporty 10-K/10-Q/8-K oraz dane XBRL SEC EDGAR (API), a także oficjalne Investor Relations.
- Przychody, EPS, zysk netto, marże, OCF, FCF, CapEx, zadłużenie, saldo gotówki, liczba akcji, ROE/ROIC; dla banków osobne mierniki (NIM, CET1, rezerwy, jakość kredytów).
- Trend 4–8 kwartałów, YoY/TTM, guidance i jego zmiany.
- P/E, forward P/E, P/S, P/FCF itp. **tylko gdy dane definicyjnie poprawne i dostępne**; prognozy analityków wymagają uprawnionego źródła.
- Kontrola: EPS <= 0 oznacza, że klasyczne P/E nie ma sensu; brak danych = `N/A`.
- Nie mieszaj GAAP z non-GAAP, kwartalnych z rocznymi, USD z innymi walutami ani okresów publikacji z datami ich dostępności.

### FR-05. Makro USA i innych rynków rozwiniętych

- Priorytet USA: stopy Fed, rentowności US Treasury 2Y/10Y, różnica 10Y–2Y, CPI/PCE, bezrobocie, wskaźniki aktywności, VIX i spready kredytowe.
- Rozszerzenie globalne: stopy i decyzje ECB, BoE, BoJ, SNB, BoC, RBA oraz istotne dane o inflacji, wzroście i zatrudnieniu w rozwiniętych regionach; dane tylko z uprawnionych, aktualnych źródeł.
- Źródła: FRED/Fed/Treasury dla USA, a dla innych regionów właściwe banki centralne, urzędy statystyczne i oficjalne serwisy; dostępność API nie jest zakładana bez weryfikacji.
- Kalendarz publikacji: „co w kolejnym tygodniu może istotnie wpłynąć na rynki”.
- Oczekiwania wobec przyszłej polityki Fed oddzielnie od bieżącej stopy; jeśli brak wiarygodnych danych rynkowych — nie podawaj liczb.
- Przy backtestach stosuj daty dostępności/vintage ALFRED, nie współczesne zrewidowane wartości.

### FR-06. Stan rynku i kontekst historyczny

- Szerokość rynku, rotacja sektorowa, relatywna siła growth/value oraz equal-weight kontra cap-weight, gdy dostępne dane.
- Porównania regionalne: USA vs Europa rozwinięta vs Japonia/Azja rozwinięta vs Kanada/Australia, z jawnym benchmarkiem i walutą; identyfikuj regiony odstające od ogólnego trendu.
- Historyczne drawdowny, długość korekt, czas odrobienia strat, benchmark w tym samym okresie.
- Porównania z 2000–2002, 2008–2009, 2020, 2022 wyłącznie z właściwymi datami, składem indeksów i ograniczeniami danych.
- Nigdy nie przekształcaj historycznej analogii w gwarantowaną prognozę.

### FR-07. Sektor AI, jakość biznesu i ryzyka

- Trzy role: dostawcy sprzętu/infrastruktury, nabywcy infrastruktury (hyperscalerzy), podmioty monetyzujące AI.
- CapEx, FCF po CapEx, marże, guidance, popyt, finansowanie długiem, koncentracja klientów, deprecjacja, wykorzystanie mocy.
- Competitive moat: switching costs, efekty sieciowe, udziały rynkowe, presja konkurencji, open source/ASIC/alternatywne architektury.
- Jakość finansowa: przychody kontra przepływy pieniężne, należności, DSO, share-based compensation, restatements, zmiany audytora.
- Powiązania finansowe („circular financing”): udokumentowane inwestycje w klientów, gwarancje, kredyty, leasing. Powiązania nie stanowią dowodu nadużyć.
- Zdarzenia: zmiany CEO/CFO, dochodzenia regulatorów, komunikaty SEC/DOJ. Rozdzielaj **informację o postępowaniu** od potwierdzenia winy.

### FR-08. Uran, energia, banki i inne sektory

- Moduły opcjonalne; nie muszą wypełniać codziennego raportu, gdy nic istotnego się nie wydarzyło.
- Uran: odróżnij spot, długoterminową cenę kontraktową, produkcję, koszt wydobycia, zapasy i harmonogram reaktorów.
- Banki: NIM, CET1, koszt depozytów, straty kredytowe, ekspozycje; nie stosuj mechanicznie P/FCF.
- Space/rynkowe monopole: dane rynkowe, konkurenci, bariery wejścia, udział, ryzyka regulacyjne; nie zakładaj monopolu tylko dlatego, że firma jest liderem.

### FR-09. Wiarygodność twierdzeń i mediów

- Rozbijaj komentarze na pojedyncze twierdzenia: mierzalne fakty, interpretacje, prognozy, rekomendacje, plotki.
- Status: `supported`, `contradicted`, `partially_supported`, `insufficient_evidence`, `prediction_pending`.
- Do każdego statusu źródło, data i uzasadnienie. LLM nie może cytować URL, którego nie dostał w danych wejściowych.
- Przykład: „ROE 117% gwarantuje odbicie akcji” → oddziel weryfikację ROE od niepoprawnej interpretacji tego wskaźnika.
- Szczególnie: zarzuty księgowe, odejścia menedżerów, debiuty IPO, margin calls i dane z X/YouTube wymagają niezależnego potwierdzenia.
- Śledź prognozy z datą utworzenia, warunkiem testu i terminem oceny; nie oceniaj przyszłości przed czasem.

### FR-10. LLM i redakcja raportu

- Silnik AI otrzymuje **ustrukturyzowany, datowany pakiet dowodów**, nie dowolny internet.
- Obliczenia, sortowanie i walidacja źródeł są deterministyczne w Pythonie.
- LLM robi selekcję najważniejszych faktów, interpretację ograniczoną do dowodów i przystępne wyjaśnienie.
- Wymagana dwustronność: czynniki wspierające i ryzyka; nie zawsze sztuczne „50/50”.
- Streszczenie 3–5 wniosków, nazwy instrumentów, liczby z jednostkami i prawidłowymi datami.
- Wyraźnie rozróżniaj „potwierdzona przyczyna ruchu” od „hipotezy zgodnej w czasie”.
- Wynik pośredni JSON według schematu, potem render Markdown; walidacja przed wysyłką.
- Dostawcy: `CopilotSDKProvider`, `APIProvider`, `TemplateProvider` (fallback). Przed wdrożeniem automatyzacji należy sprawdzić **headless auth** i koszty Copilot SDK na docelowym koncie; sama subskrypcja Copilot Pro nie gwarantuje darmowej, nieograniczonej automatyzacji 24/7.

### FR-11. Wydanie, dostarczenie, archiwum

- Jedno wywołanie `run` pobiera nowe dane, aktualizuje repozytorium danych, analizuje, waliduje i emituje `.md`.
- Raport zapisany w archiwum przed próbą wysyłki.
- Pierwszy kanał docelowy: e-mail z załącznikiem `.md` i krótkim tekstem podglądu; łatwo dodać inne kanały później.
- Ponowne próby doręczenia nie powinny generować nowego raportu ani duplikować udanych wiadomości.
- Gdy LLM zawiedzie: raport szablonowy, oznaczony jako tryb awaryjny, z danymi i źródłami.
- Gdy źródła krytyczne zawiodą: wyraźny raport częściowy albo sygnał „raport niewygenerowany” z alarmem, a nie fikcyjna analiza.
- Archiwum i stan aplikacji mają być trwałe także przy uruchamianiu na krótkotrwałym runnerze CI.

### FR-12. Pamięć i porównanie z wczoraj

- W każdym raporcie sekcja „Co się zmieniło od poprzedniego raportu?”.
- Uwzględnij: nowe informacje, istotne zmiany cen, publikacje wyników, aktualizacje hipotez i sprostowania.
- Rozróżniaj „nowy nagłówek” od „nowych faktów w sprawie już opisanej”.
- Zachowuj historyczne snapshoty, aby dało się odtworzyć, na jakich danych powstał dany raport.

## 5. Niefunkcjonalne wymagania

- **Niezawodność:** retry z backoff, timeouty, limity API, izolacja awarii źródeł, idempotencja, monitoring dostarczenia.
- **Audyt:** `run_id`, logi, wersje źródeł, timestampy UTC, fingerprint wejścia i model/provider; brak danych oznaczony jawnie.
- **Bezpieczeństwo:** prywatne repozytorium, brak sekretów w logach/plikach, minimalne uprawnienia, ochrona przed prompt injection.
- **Koszty:** dzienny limit LLM i API, cache, wysyłanie tylko istotnych treści do modelu; awaryjny raport bez LLM.
- **Testowalność:** pytest z fixture'ami offline, testy metryk i kalendarza giełdowego, walidacji linków i deterministycznej treści.
- **Utrzymywalność:** małe moduły, typowanie, ruff/mypy, migracje SQLite, brak niepotrzebnych frameworków agentowych.
- **Prywatność:** domyślnie tylko publiczne dane rynkowe; prywatne informacje o portfelu dopiero za wyraźną zgodą użytkownika.
- **Licencje:** zapisywanie i przetwarzanie danych zgodnie z warunkami źródła; `yfinance` jest przeznaczone do użytku research/edukacyjnego, a Yahoo Finance wskazuje osobisty użytek danych.

## 6. Proponowana architektura i podział modułów

```text
Scheduler (codziennie 23:30 Europe/Warsaw)
  -> CLI / Orchestrator (uruchomienie i run_id)
      -> Ingestion (price, SEC, FRED, RSS, opcjonalne sektory)
      -> Normalization & Provenance (typy, źródła, czasy, dedup)
      -> Persistent Storage (SQLite + snapshoty)
      -> Deterministic Analytics (metrics, fundamentals, macro, risk)
      -> Event / Claim Verification (statusy i linki)
      -> Evidence Package JSON (ograniczenie, ranking, kontrole)
      -> LLMProvider (synteza) / TemplateProvider (fallback)
      -> Output Validator (daty, liczby, cytowania, brak halucynacji)
      -> Markdown Renderer -> reports/YYYY-MM-DD.md
      -> Archive + Delivery(email)
      -> Delivery receipt / operational alert
```

Przykładowe, **proponowane** (nie istniejące jeszcze) moduły kodu:

```text
src/market_digest/
  config.py         cli.py            main.py
  models.py         calendar.py       storage.py
  providers/        ingestion/        normalize/
  analytics/        evidence/         report/
  delivery/         observability/
tests/
config.yaml
reports/
```

**Dodatkowe moduły etapów rozwojowych:** `financial_quality.py`, `corporate_events.py`, `ai_cycle.py`, `ai_financing.py`, `competitive_moat.py`, `ipo_analysis.py`, `market_liquidity.py`, `claims_validator.py`, `thesis_tracker.py`, `signal_backtester.py`. Nie tworzyć wszystkich jako pustych plików w MVP.

### Kontrakty komponentów

- `MarketDataProvider`: instrument, zakres dat -> uporządkowane OHLCV + źródło i znaczniki czasu.
- `FundamentalsProvider`: CIK/emitent -> zestaw wskaźników z okresem, jednostką, datą publikacji i jakością.
- `MacroProvider`: identyfikator serii + vintage -> obserwacje z datami.
- `NewsProvider`: zakres -> artykuły i metadane.
- `AnalyticsService`: znormalizowane snapshoty -> metryki bez efektów ubocznych.
- `EvidenceBuilder`: dane i newsy -> pakiet możliwy do zacytowania.
- `LLMProvider`: pakiet faktów i instrukcje -> obiekt raportu zgodny ze schematem; ewentualny budżet i usage.
- `ReportRenderer`: obiekt raportu -> Markdown; nie wykonuje zapytań sieciowych.
- `DeliveryProvider`: ścieżka raportu i klucz idempotencji -> status wysyłki i identyfikator doręczenia.

## 7. Model danych (logiczny, nie ostateczna migracja SQL)

`instruments`, `prices`, `corporate_filings`, `fundamental_facts`, `macro_observations`, `news_items`, `news_events`, `company_relationships`, `investment_claims`, `claim_evidence`, `report_runs`, `report_snapshots`, `delivery_attempts`.

Każdy fakt istotny dla raportu powinien mieć co najmniej: `entity_id`, `metric_id`, `value`, `unit`, `currency` (jeśli dotyczy), `period_start/end`, `observed_at`, `published_at`, `retrieved_at`, `source_url`, `provider`, `quality_flags`. Zdarzenia posiadają osobny `event_at` i `status`.

Nie zakładaj, że każda obserwacja ma wszystkie pola: kontrakt rozróżnia opcjonalność i `unavailable`.

## 8. Definition of Done dla całego produktu

Projekt jest „gotowy do codziennego używania” dopiero jeśli:

- da się uruchomić ręcznie oraz automatycznie bez IDE;
- pokazuje osobne regionalne podsumowania USA, Europy i co najmniej jednego rynku Azji rozwiniętej oraz kontroluje wykluczenie Polski/emerging markets;
- poprawnie tworzy datowany raport po polsku nawet w dzień bez sesji;
- dodaje datę ostatniej sesji i źródła dla kluczowych danych;
- realizuje **rzeczywiste dostarczenie** MD na wskazany kanał, zapisując potwierdzenie;
- raport częściowy jest jawnie oznaczony i nie zawiera zmyślonych danych;
- po błędzie uruchomienia użytkownik dostaje sygnał operacyjny;
- system przechowuje archiwum i potrafi wznowić pracę na trwałych danych;
- testy krytycznych wyliczeń i obliczeń na datach przechodzą;
- raport można odtworzyć ze snapshotu wejściowego;
- znany jest przybliżony koszt/dzienny limit oraz źródła ograniczeń licencyjnych.

## 9. Otwarte decyzje konfiguracyjne (nieblokujące planowania)

- Adres do odbierania wiadomości i dostawca e-mail.
- Środowisko docelowe: komputer z Windows stale włączony / VPS / GitHub Actions + trwały magazyn danych.
- Dostawca LLM: Copilot SDK vs alternatywne API, zweryfikowane testem automatycznej autoryzacji i limitami.
- Wielkość watchlisty, limit kosztów, konkretne kanały RSS.
- Progi minimalnego pokrycia danych dla poszczególnych regionów i opcjonalne kraje z listy developed markets.

Dopóki użytkownik nie określi tych parametrów, stosuj **konfigurowalne placeholdery i rozsądne domyślne założenia**, nie wymyślaj e-maila i nie generuj sekretów.
