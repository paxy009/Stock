# Market Digest — etapy implementacji i kryteria odbioru

**Najważniejsze:** nie implementować wszystkich pomysłów na raz. Najpierw wiarygodny raport MD + dostarczenie, potem coraz lepsza analiza.

## Etap 0 — decyzje i plan (bez kodu aplikacyjnego)

**Rezultat:** architektura, ADR-y, backlog, model danych, kolejność prac i ryzyka.

- [ ] Zweryfikować zakres watchlisty i dostępność tickerów.
- [ ] Zatwierdzić regułę MSCI Developed Markets + wyłączenie Polski i emerging markets; sprawdzić kraje emitentów, ETF-y z ekspozycją zagraniczną oraz instrumenty graniczne.
- [ ] Uzgodnić benchmarki dla USA, Europy, Japonii, Kanady i Australii, rozróżniając lokalne indeksy od ETF-ów proxy notowanych w USA.
- [ ] Ustalić definicje wskaźników (sesje, ceny skorygowane, jednostki).
- [ ] Określić środowisko uruchomienia: lokalnie -> docelowy cloud/VPS.
- [ ] Wybrać kanał odbioru (domyślnie e-mail `.md` jako załącznik).
- [ ] Przetestować możliwość headless auth, zużycie i limity Copilot SDK.
- [ ] Ustalić poziomy danych obowiązkowych i akceptowane degradacje raportu.

**Akceptacja:** Copilot przedstawia klarowny plan bez generowania setek plików; brak ukrytych założeń o uprawnieniach API lub darmowej automatyzacji.

## Etap 1 — MVP: ceny, RSS, Markdown

**Cel:** raport może zostać wygenerowany **lokalnie** ze źródłami i poprawnymi metrykami.

- [ ] Projekt Python 3.11+, pyproject, config YAML, schema validation.
- [ ] Adapter yfinance, cache OHLCV, SQLite, zapis próbek z datami i **regionalnymi kalendarzami/strefami**.
- [ ] Filtr krajów i kwalifikowalności: USA, Europa rozwinięta, Japonia, Kanada, Australia; odrzucanie Polski i emerging markets, z wyjaśnieniem przyczyny.
- [ ] Co najmniej po jednym reprezentatywnym benchmarku/proxy z USA, Europy i Japonii; dla Kanady/Australii wsparcie konfiguracji już w MVP, jeśli dostępny jest wiarygodny ticker.
- [ ] Metryki: 1D, 5D, 21D, YTD, 52-week drawdown i relatywna zmiana do benchmarku.
- [ ] RSS: fetch, URL normalization, dedup, event grouping podstawowy.
- [ ] Prosty deterministyczny ranking 3–5 najistotniejszych zdarzeń.
- [ ] Budowa `evidence_package.json` z podaniem źródeł.
- [ ] `TemplateProvider` i opcjonalny LLM adapter.
- [ ] Render raportu `.md` dokładnie według kontraktu.
- [ ] CLI: `fetch`, `analyze`, `report`, `run`, `doctor`.
- [ ] Unit testy offline i `README` z uruchamianiem ręcznym.

**Akceptacja (przykłady testów):**

- [ ] Poniedziałkowy „1D” porównuje piątek z poniedziałkiem, bez weekendowych zer.
- [ ] Split akcji nie generuje sztucznego -50% drawdownu.
- [ ] Brak 1 tickera nie przerywa całego raportu.
- [ ] Dwie kopie tego samego newsa nie zajmują dwóch miejsc w TL;DR.
- [ ] Brak potwierdzonej przyczyny spadku → raport mówi „niepotwierdzona”.
- [ ] W raporcie nie ma URL-i wygenerowanych przez model ani placeholderów.
- [ ] Ten sam snapshot i ustawienia renderera → powtarzalna sekcja metryk.
- [ ] Brak dostępnego LLM → kompletny raport szablonowy z flagą fallback.

## Etap 2 — rzeczywista automatyzacja i dostarczenie

**Cel:** użytkownik otrzymuje plik `.md` codziennie, bez ręcznych czynności.

- [ ] Provider e-mail z załącznikiem i idempotencją.
- [ ] Archiwum, statusy raportów i doręczeń.
- [ ] Scheduler i obsługa dat/świąt/DST.
- [ ] Niepowodzenie doręczenia -> retry / wykrywalny alert.
- [ ] Wybór środowiska trwałego: VPS albo GitHub Actions + trwały storage.
- [ ] Backup stanu i test przywracania po uszkodzeniu.
- [ ] Test automatyczny na piątku, sobocie, niedzieli, święcie USA, europejskim i japońskim, zmianie czasu oraz rozbieżnych datach sesji.
- [ ] Test wykluczenia instrumentu z Polski, kraju EM i ADR z USA, którego emitent jest w EM; test dopuszczenia ETF-u notowanego w USA, jeśli bazuje na wyłącznie rozwiniętym regionie.
- [ ] Test przeliczenia 2-datowej stopy zwrotu do PLN i oznaczenia brakujących danych FX.

**Akceptacja:** w co najmniej kilku kolejnych dniach testowych raport jest wysyłany samoczynnie na testową skrzynkę; nie ma duplikatów; awaria operatora daje jasną diagnostykę. Symulacje kalendarzowe obejmują również dni bez notowań.

## Etap 3 — SEC, wyniki spółek i FRED

**Cel:** raport pokazuje *dlaczego ocena spółki i rynku mogła się zmienić*, a nie tylko zmianę kursu.

- [ ] Rozszerzyć źródła fundamentalne poza SEC: właściwe raporty emitentów, giełd/regulatorów Europy, Japonii, Kanady i Australii; zaczynać od oficjalnych IR, nie zakładać jednego wspólnego API.
- [ ] Makro zagraniczne: ECB/BoE/BoJ/BoC/RBA/SNB, gdy wpływa na monitorowane regiony.

- [ ] SEC: mapowanie ticker -> CIK, 10-Q/10-K/8-K, poprawne XBRL/okresy.
- [ ] Earnings: revenue, EPS, FCF, marże, CapEx, cash/debt, guidance (gdy wiarygodne).
- [ ] Makro: stopy Fed, 2Y/10Y, CPI/PCE, bezrobocie, VIX.
- [ ] Kalendarz wydarzeń makro i publikacji wyników.
- [ ] Sekcje wyników/makro, zmiana od poprzedniego raportu.

**Akceptacja:** każdy wskaźnik ma okres, jednostkę i źródło; dla EPS <= 0 raport nie udaje poprawnego P/E; 8-K jest wydarzeniem z własną datą, a nie automatycznym werdyktem o jakości firmy.

## Etap 4 — jakość zysków, AI, governance, konkurencja

**Cel:** rozumieć fundamentalną jakość biznesu i istotne ryzyka.

- [ ] Earnings vs OCF/FCF, należności, DSO, SBC, restatements.
- [ ] CapEx hyperscalerów, monetyzacja AI, koncentracja klientów.
- [ ] Powiązania dostawca/odbiorca/inwestor i ryzyka circular financing.
- [ ] Zdarzenia CEO/CFO, audytor, SEC/DOJ, ryzyka governance.
- [ ] Moat, konkurencja, open source, ASIC i ryzyko erozji marż.
- [ ] Dodatkowe analizy uranu i banków tylko tam, gdzie dane mają odpowiednią jakość.

**Akceptacja:** analiza podaje źródła pierwotne; nie utożsamia relacji finansowych z oszustwem ani śledztwa z winą.

## Etap 5 — weryfikacja komentarzy i historia tez

**Cel:** komentarze z social mediów stają się *pytaniami badawczymi*, nie wyrocznią.

- [ ] CLI `verify-claim "..."` z rozbiciem tez i statusami.
- [ ] Historia zmian statusu tezy i warunki weryfikacji prognozy.
- [ ] Rzetelne liczenie wyników IPO: offer/open/first trade/close.
- [ ] Dekompozycja EPS vs P/E (gdy matematycznie prawidłowa).
- [ ] Event study i backtesting bez look-ahead bias i survivorship bias.
- [ ] Opcjonalne opinie z YouTube/X, tylko gdy sposób pobierania jest zgodny z zasadami.

**Akceptacja:** brak automatycznych ocen typu „prawdopodobieństwo wzrostu 78%” bez modelu i walidacji; historyczny test ma liczebność próby, benchmark oraz ograniczenia.

## Etap 6 — opcjonalna przyszłość

- Dashboard z archiwum i przeglądarką źródeł.
- Deep Research dla pojedynczej firmy.
- Powiadomienia o ważnych zdarzeniach między raportami (po wyraźnym włączeniu).
- Porównania scenariuszowe dla **hipotetycznego** portfela; bez handlu.

## Nie robić w MVP

- Autonomicznego tradingu i integracji z brokerem.
- Modelu „prognozującego cenę NVDA jutro” bez rygorystycznego backtestu.
- Wielu agentów dyskutujących bez danych i ścieżki audytu.
- Bezrefleksyjnego scrapingu X i wszystkich transkrypcji YouTube.
- 30 tabel codziennie, jeśli nie ma nowych informacji.
- Płatnych feedów, zanim podstawowy raport okaże się przydatny.

## Techniczny Definition of Done dla każdego zadania

1. Kod typed, lint przechodzi, testy offline.
2. Zdefiniowane format wejścia/wyjścia i semantyka braków.
3. Błąd pojedynczego dostawcy nie powoduje cichego zafałszowania wyników.
4. Wynik możliwy do weryfikacji z fixture'u lub snapshotu.
5. Dokumentacja aktualizowana wraz z implementacją.
6. Bez sekretów w kodzie i logach.

## Minimalna checklista po pierwszych 14 dniach działania

- [ ] 14 logicznych raportów w archiwum (wliczając weekendy).
- [ ] 14 statusów wysyłki, bez niezamierzonych duplikatów.
- [ ] Jasna data danych dla każdego użytego wskaźnika, z osobnymi datami zakończonych sesji regionalnych.
- [ ] Wszystkie wiersze giełdowe kwalifikują się do MSCI Developed Markets i nie dotyczą rynku polskiego ani emerging markets, chyba że występują **wyłącznie jako udokumentowany kontekst gospodarczy**.
- [ ] Możliwe ponowne wygenerowanie co najmniej jednego starszego raportu offline.
- [ ] Znane koszty użycia modelu i źródeł.
- [ ] Wiadomo, co się stanie, gdy źródło lub mailer nie działa.

**Propozycja podziału prac dla Copilota:** najpierw jedno małe zadanie z testami, merge dopiero po walidacji, następnie kolejne. Unikaj generowania wszystkich modułów w jednej odpowiedzi.
