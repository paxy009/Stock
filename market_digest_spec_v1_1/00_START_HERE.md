# Market Digest — pakiet specyfikacji 1.1

**Status:** dokumentacja przed rozpoczęciem implementacji; brak kodu i repozytorium.  
**Data opracowania:** 2026-11-22.  
**Cel główny:** każdego dnia automatycznie otrzymać **wiarygodny raport rynkowy po polsku jako plik Markdown (`.md`)**.
**Zakres inwestycyjny:** globalne rynki **rozwinięte (MSCI Developed Markets)**, z priorytetem USA, **bez Polski i bez rynków wschodzących**. Analiza globalnych czynników ryzyka (np. Chin) jest dozwolona jako kontekst, a nie jako rozszerzenie watchlisty inwestycyjnej.


## Co zmieniono w wersji 1.1

- Zakres ograniczony do **globalnych rynków rozwiniętych** według referencji MSCI, bez Polski i emerging markets.
- Rozszerzono przykładową watchlistę o Europę, Japonię, Kanadę i Australię oraz oznaczono regionalne ETF-y jako proxy.
- Dodano filtry kraju emitenta, indeksu bazowego ETF i obsługę przypadków granicznych (ADR, fundusze mieszane, Hongkong).
- Uwzględniono osobne kalendarze sesji, godziny zamknięcia, daty danych i waluty dla poszczególnych regionów.
- Rozszerzono raport Markdown, testy akceptacyjne, prompt dla Copilota oraz politykę wiarygodności danych.

## Jak korzystać z pakietu

1. Przeczytaj `01_PRODUCT_SPEC.md` — główne wymagania i zakres produktu.
2. Zobacz `02_REPORT_TEMPLATE.md` — dokładny format codziennego raportu.
3. Sprawdź `03_DATA_AND_EVIDENCE_POLICY.md` — zasady danych, źródeł i oceny komentarzy.
   Przeczytaj `08_GEOGRAPHY_AND_COVERAGE.md` — wiążące zasady doboru rynków, emitentów, ETF-ów i regionalnych benchmarków.
4. Zobacz `04_AUTOMATION_AND_DELIVERY.md` — uruchamianie, archiwizacja i **dostarczenie** raportu.
5. Przeczytaj `05_IMPLEMENTATION_PLAN.md` — fazy, priorytety, testy i definicja „gotowe”.
6. Wklej treść `06_COPILOT_MASTER_PROMPT.md` do GitHub Copilot **Plan mode**, dołączając pliki z pakietu jako kontekst.
7. `config.example.yaml` to **propozycja kontraktu konfiguracyjnego**, a nie już działający plik konfiguracyjny aplikacji.

## Ustalony produkt końcowy

- **Wejście:** ceny i wolumeny, oficjalne raporty finansowe, dane makro, wiadomości i opcjonalne źródła tematyczne.
- **Przetwarzanie:** Python liczy metryki; moduł walidacji rozróżnia fakty, hipotezy i brak danych; LLM pisze klarowne podsumowanie na podstawie przygotowanego pakietu faktów.
- **Wyjście:** jeden czytelny plik `reports/YYYY-MM-DD.md`, wersjonowany/archiwizowany, oraz kopia przesłana jako **załącznik e-mail** (kanał dostarczania docelowy; adres i operator nie są jeszcze wybrane).
- **Godzina:** domyślnie **23:30 Europe/Warsaw**, codziennie. Dni bez sesji: raport informacyjny, bez udawania nowych zmian cen.
- **Tryb rozszerzony:** tygodniowe podsumowanie w niedzielę; analizy pojedynczych spółek i tez *na żądanie* w późniejszym etapie.
- **Język:** polski; źródła i tickery zachowują oryginalne nazwy.
- **Regiony:** USA, Europa rozwinięta, Azja rozwinięta, Kanada, Australia i pozostałe rynki rozwinięte; wykluczamy polskie aktywa i instrumenty nastawione na emerging markets.
- **Kalendarze:** sesje i daty cen ustalaj oddzielnie dla każdego rynku; strefa `Europe/Warsaw` dotyczy harmonogramu raportu, a nie czasu giełdowego.
- **Ograniczenie:** system nie kupuje/sprzedaje instrumentów, nie udaje pewności prognoz i nie wymyśla źródeł.

## Najważniejsza decyzja projektowa

Nie buduj na początku autonomicznego wieloagentowego „tradera”. Buduj **niezawodny proces generowania raportu** z możliwością podmiany źródeł i modelu AI. Celem MVP jest działający raport dostarczany codziennie, a nie maksymalna liczba wskaźników.

## Dokumenty a kod

Ten pakiet nie zawiera implementacji Pythona, skonfigurowanego GitHub Actions ani gotowych połączeń API. Kod ma powstać dopiero po zatwierdzeniu planu przez Copilota i implementacji etapami.

## Weryfikowane punkty odniesienia (oficjalne dokumentacje)

- SEC EDGAR API: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- FRED / ALFRED: https://fred.stlouisfed.org/docs/api/fred/
- GitHub Actions schedule: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Actions opóźnienia: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- GitHub Copilot SDK quickstart: https://docs.github.com/en/copilot/get-started/sdk-quickstart
- GitHub Copilot SDK uwierzytelnienie: https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth
- yfinance (ograniczenia): https://ranaroussi.github.io/yfinance/

**Uwaga:** warunki API, licencje, limity i ceny mogą się zmieniać; należy je sprawdzić ponownie przed implementacją i uruchomieniem automatycznym.
