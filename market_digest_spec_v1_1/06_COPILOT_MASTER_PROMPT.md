# Master prompt do GitHub Copilot — najpierw PLAN, później implementacja

Skopiuj poniższy blok do GitHub Copilot w **trybie Plan** i dołącz pozostałe pliki dokumentacji jako kontekst.

---

Jesteś senior Python engineer, system architect, data engineer i reviewer poprawności obliczeń finansowych.

Chcę zbudować **Market Digest**, prywatny system, który każdego dnia automatycznie generuje i dostarcza mi **jeden raport rynkowy w formacie Markdown (`.md`) po polsku**. Mam wiedzę inwestycyjną na poziomie podstawowym/średniozaawansowanym. Jestem programistą, więc oczekuję dobrych praktyk projektowych, testów i rozsądnej architektury, ale bez niepotrzebnego nadmiernego komplikowania projektu.

**Ważne: na razie nie istnieje repozytorium ani żaden kod. Nie twórz kodu bezpośrednio po otrzymaniu tego promptu. Najpierw przygotuj plan i architekturę.**

W załączonym pakiecie znajdują się:

- `00_START_HERE.md` — cel i instrukcja wykorzystania dokumentacji;
- `01_PRODUCT_SPEC.md` — pełne wymagania produktu;
- `02_REPORT_TEMPLATE.md` — wymagany kontrakt codziennego raportu Markdown;
- `03_DATA_AND_EVIDENCE_POLICY.md` — poprawność finansowa, źródła i ocena wiarygodności;
- `04_AUTOMATION_AND_DELIVERY.md` — generowanie, archiwum, e-mail, scheduler;
- `05_IMPLEMENTATION_PLAN.md` — kolejność faz i kryteria akceptacji;
- `config.example.yaml` — wstępny kontrakt konfiguracji, nie kod produkcyjny;
- `08_GEOGRAPHY_AND_COVERAGE.md` — szczegółowe reguły kwalifikacji geograficznej i regionalny zakres raportów.

**Nadrzędny priorytet:** codzienny, wiarygodny, czytelny i dostarczony `.md`. Wszystkie moduły służą temu celowi. Nie buduj automatycznego systemu transakcyjnego.

**Wiążący zakres geograficzny:** globalne **rynki rozwinięte** (klasyfikacja MSCI Developed Markets jako punkt odniesienia), **bez Polski i rynków wschodzących**. USA jest najważniejszym, ale nie jedynym rynkiem. W raporcie uwzględniaj Europę rozwiniętą, Japonię i pozostałą Azję rozwiniętą, Kanadę oraz Australię. Wydarzenia z rynków EM można podawać **tylko jako kontekst** ich wpływu na rynki rozwinięte. ADR emitenta z EM nie kwalifikuje się tylko dlatego, że jest notowany w USA; ETF notowany w USA może reprezentować Europę/Japonię, jeśli skład/indeks bazowy spełnia filtr. Przed projektowaniem przeczytaj `08_GEOGRAPHY_AND_COVERAGE.md`.

### Wymagania technologiczne

- Python 3.11+, typowanie, YAML, SQLite, CLI, pytest, ruff, mypy.
- W MVP yfinance + RSS + deterministyczne obliczenia + format Markdown. Minimalny globalny przekrój: USA, Europa rozwinięta, Japonia, z obsługą Kanady/Australii. Nie zastępuj analizy „globalnej” samymi tickerami USA.
- W następnych fazach SEC EDGAR (dla odpowiednich amerykańskich emitentów), oficjalne sprawozdania europejskie/azjatyckie/kanadyjskie/australijskie, FRED i pozostałe banki centralne, analiza sektorowa i weryfikacja twierdzeń.
- LLM interpretujący **wyłącznie dostarczone fakty**; adapter dla Copilot SDK oraz alternatywnego API, plus fallback szablonowy bez modelu.
- Treści internetowe jako niezaufane dane; bez wykonywania instrukcji ukrytych w RSS/artykułach.
- Archiwum, **regionalne daty ostatnich sesji**, źródła, ograniczenia danych, brak mylenia weekendów i świąt różnych giełd z nowymi zmianami kursu.
- Dla ETF-ów regionalnych notowanych w USA podawaj walutę i czas notowań; do porównań stosuj spójny punkt odniesienia i opisuj przeliczenie walutowe (opcjonalnie do PLN).
- Uruchomienie każdego dnia domyślnie o 23:30 Europe/Warsaw, także w weekendy (wtedy raport informacyjny).
- **Rzeczywiste dostarczenie raportu** jako załącznik e-mail + trwałe archiwum. Adres i serwer e-mail jako konfigurowalne placeholdery.
- Nie zakładaj, że Copilot Pro w IDE = automatyczny, darmowy dostęp SDK dla nocnego procesu. Zaproponuj test headless auth, limitów i fallback.
- Nie zakładaj, że SQLite przeżyje ponowne uruchomienie efemerycznego środowiska GitHub Actions bez trwałego storage.

### Co masz przygotować TERAZ — bez pisania kodu

1. Krótkie podsumowanie celu systemu i jego granic.
2. Proponowaną architekturę modułową i przepływ danych od źródła do maila z `.md`.
3. Diagram zależności i proponowane kontrakty providerów.
4. Projekt logicznego schematu SQLite z kluczami i identyfikatorami źródeł.
5. Podział funkcjonalności na **MVP**, automatyzację, analizy rozszerzone i opcjonalne funkcje.
6. Backlog małych, testowalnych zadań z kolejnością realizacji i kryteriami akceptacji.
7. Ryzyka: licencje, strefy czasu, daty sesji, jakość danych, limity API, koszty LLM, prompt injection, niedostępny provider, awaria SMTP, duplikaty raportów.
8. Porównanie dwóch wariantów uruchomienia: Windows Task Scheduler + SQLite i GitHub Actions + trwały storage (alternatywnie mały VPS).
9. Konkretną strategię testowania metryk finansowych, danych niepełnych, filtrów Polska/EM, dat bez sesji regionalnych i konwersji walut.
10. Krótką propozycję pierwszych trzech PR-ów/iteracji implementacyjnych.

### Zasady współpracy

- Nie przepisuj wszystkich wymagań w ogromny, nieuporządkowany plan. Przypisz funkcje do etapów i wskaż elementy kluczowe dla codziennego raportu.
- Jeśli wymagania są sprzeczne, jawnie wskaż konflikt i zaproponuj rozstrzygnięcie.
- Nie zakładaj niepotwierdzonych tickerów, cen, wydarzeń lub możliwości API.
- Nie wybieraj modeli i usług na podstawie zmyślonych cen; sprawdź aktualną dokumentację lub oznacz konieczność późniejszej weryfikacji.
- Nie proponuj LangChain/CrewAI, jeśli prosta architektura wystarcza.
- Przygotuj plan, który mogę zatwierdzić przed rozpoczęciem kodowania.
- Po akceptacji: implementuj wyłącznie **Etap 1**, z testami po każdym module.

Na końcu odpowiedzi wskaż dokładnie: **co będę w stanie otrzymywać po Etapie 1 (w tym minimalny przekrój globalnych rynków rozwiniętych) i jakie prace są konieczne, żeby raport docierał automatycznie każdego dnia**, bez uruchamiania VS Code.

---

## Drugi prompt — gdy plan zostanie zaakceptowany

> Plan zaakceptowany. Utwórz repozytorium i implementuj tylko Etap 1 zgodnie z zatwierdzoną architekturą. Najpierw skrypt startowy, walidacja konfiguracji, modele danych i testy metryk, potem adapter cen, RSS, SQLite, renderer Markdown i CLI. Po każdym module uruchom testy i pokaż rzeczywiste wyniki. Nie implementuj automatyzacji ani rozszerzeń z późniejszych etapów bez osobnego zadania. Utrzymuj zgodność z `02_REPORT_TEMPLATE.md` i `03_DATA_AND_EVIDENCE_POLICY.md`.
