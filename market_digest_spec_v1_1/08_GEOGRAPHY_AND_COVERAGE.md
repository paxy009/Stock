# Market Digest — zasady geograficzne i pokrycie rynków (v1.1)

## 1. Cel i twarde ograniczenia

System raportuje **globalne rynki rozwinięte**, z największym naciskiem na USA. **Wykluczamy polskie instrumenty rynku kapitałowego oraz instrumenty i rynki emerging/frontier markets** z podstawowych porównań, watchlisty i automatycznych analiz inwestycyjnych. Klasyfikacja referencyjna: **MSCI Developed Markets**, z zapisaną nazwą dostawcy, wersją/dniem obowiązywania i mechanizmem aktualizacji. Ponadto Polska jest wykluczona **niezależnie od klasyfikacji dostawcy**.

Wykluczenie EM nie oznacza ignorowania ich wpływu na świat: dane dotyczące Chin, Indii, Tajwanu, Brazylii czy geopolityki mogą się pojawiać wyłącznie jako **istotny kontekst oddziaływania na aktywa z rynków rozwiniętych**. Dane FX/PLN są dopuszczone tylko dla wyceny inwestora z Polski; to nie jest analiza GPW.

## 2. Regiony objęte raportem

| Region raportu | Przykłady rynków kwalifikujących się | Przykładowe benchmarki | Miejsce w raporcie |
|---|---|---|---|
| USA | Stany Zjednoczone | S&P 500, Nasdaq-100, Russell 2000 | Najwyższy priorytet, tech/AI oraz makro Fed |
| Europa rozwinięta | Niemcy, Francja, Wielka Brytania, Holandia, Szwajcaria, Szwecja, Dania, Norwegia, Finlandia i pozostałe rozwinięte w klasyfikacji | STOXX Europe 600, DAX, CAC 40, FTSE 100, SMI | Region i najważniejsze spółki, makro ECB/BoE/SNB |
| Azja rozwinięta | Japonia, Singapur, Hongkong (z weryfikacją emitenta i bazowej ekspozycji) | Nikkei 225, TOPIX, STI i właściwe indeksy Hongkongu | Japonia obowiązkowo; pozostałe według ważności i dostępności |
| Pozostałe rozwinięte | Kanada, Australia, Nowa Zelandia | S&P/TSX Composite, S&P/ASX 200 | Zwięźle, ze szczególną uwagą na surowce, banki i wydarzenia |

**Uwaga graniczna:** Korea Południowa i Tajwan są traktowane jako emerging markets przy przyjętym punkcie odniesienia MSCI; nie kwalifikują się automatycznie. Różne firmy indeksowe stosują odmienne klasyfikacje, dlatego każda zmiana metody musi być udokumentowana. Hongkong jako rynek może być zakwalifikowany do developed, ale wiele notowanych tam podmiotów jest emitentami z Chin kontynentalnych — sprawdzaj **kraj emitenta i rzeczywistą ekspozycję** zamiast dodawać wszystkie lokalne tickery.

## 3. Reguły doboru instrumentów

1. **Akcje/ADR:** wymagaj `issuer_country` oraz przyporządkowania do klasyfikacji rynkowej. Kraj notowania, waluta i ticker nie wystarczają do dopuszczenia. Przykładowo `ASML` może kwalifikować się jako spółka holenderska mimo notowania w USA; `TSM` nie kwalifikuje się do podstawowej watchlisty przy klasyfikacji MSCI, mimo notowania ADR w USA.
2. **ETF/fundusze:** sprawdzaj `underlying_index`, metodologię indeksu, zakres geograficzny, skład i profil ryzyka. ETF notowany w USA z ekspozycją wyłącznie na rynki rozwinięte może kwalifikować się (np. regionalne proxy `VGK`, `EWJ`, `EWC`, `EWA`, `EFA`). ETF „all-world” z istotnym udziałem EM **nie kwalifikuje się automatycznie**. Nie obiecuj zerowej ekspozycji pośredniej na EM (np. przez przychody globalnych przedsiębiorstw); filtr dotyczy kraju emitenta/mandatu inwestycyjnego, nie każdej sprzedaży spółki.
3. **ETF-y sektorowe:** koszyki tematyczne (np. surowce, uranium) mogą posiadać spółki EM. Sprawdź skład i oznacz `eligible`, `excluded` albo `requires_review`. Jeśli nie są zgodne z zakresem, zastąp je benchmarkiem globalnej ceny surowca lub podzbiorem kwalifikujących się emitentów.
4. **Indeksy:** przechowuj identyfikator kanoniczny, dostawcę i jego symbol. Potwierdź skład/definicję i datę dostępności; nie zgaduj symbolu indeksu na Yahoo Finance. Jeżeli jest niedostępny, zgłoś ograniczenie i użyj jawnie opisanego proxy.
5. **Surowce/futures/metale:** dopuszczaj globalne ceny jako wskaźnik rynkowy, nawet jeśli podaż/popyt obejmują EM. Nie wyciągaj z tego wniosku o kwalifikacji producenta z EM do watchlisty.
6. **Waluty:** `USD/PLN`, `EUR/PLN`, `JPY/PLN`, `GBP/PLN`, `CAD/PLN`, `AUD/PLN` są tylko elementem przeliczeń i ryzyka walutowego. Nie oznaczają dopuszczenia Polski do raportowania akcji.
7. **Brak pewności:** w razie niejednoznaczności kraju/składu nadaj `requires_review`; nie umieszczaj aktywa po cichu w części inwestycyjnej raportu.

## 4. Kalendarz, ceny i waluty

- Każdy instrument ma identyfikator giełdy, lokalną strefę czasu, osobny kalendarz i datę ostatniej **ukończonej** sesji.
- Raport jest generowany o 23:30 czasu `Europe/Warsaw` (cel), ale lokalne giełdy zamykają się w różnych momentach. „Stan na” i „ostatnia sesja” to nie jeden wspólny znacznik dla całego świata.
- „1D” to ostatnia zmiana między dwiema sesjami **tego instrumentu**. Lokalny indeks w Japonii i ETF `EWJ` notowany w USA nie mają tego samego zegara ani waluty; ETF jest proxy ekspozycji, nie bezpośrednim zamknięciem Nikkei.
- Porównania regionalne wymagają spójnej waluty i jasno zdefiniowanego okna; domyślnie pokazuj zmiany lokalne, opcjonalnie również przeliczenie do PLN. Gdy kurs FX jest niedostępny, `PLN return = N/A`.
- Przeliczenia stopy zwrotu: używaj odpowiedniego kursu FX w obu datach; nie dodawaj intuicyjnie procentów zmiany aktywa i waluty.
- Stosuj lokalne kalendarze dla Tokio, Londynu, Frankfurtu, Zurychu, Toronto, Sydney i USA; święto w USA nie powoduje automatycznie oznaczenia całego świata jako nieczynnego.

## 5. Źródła danych i rozbudowa

- **MVP:** adapter cen (`yfinance`) i RSS, regionalne ETF-y jako pomocnicze proxy, lokalne indeksy tylko po zweryfikowaniu symboli i spójności danych. Ceny każdorazowo z datą obserwacji.
- **Fundamenty USA:** SEC EDGAR i oficjalne komunikaty emitentów.
- **Fundamenty poza USA:** Investor Relations, regulatorzy/serwisy giełdowe właściwe dla państwa (np. europejskie raporty emitentów, japońskie EDINET, kanadyjskie SEDAR+, australijskie komunikaty ASX). Nie zakładaj, że każdy portal udostępnia darmowe API do automatycznego odczytu — sprawdź regulaminy, zakres i licencje.
- **Makro:** FRED/Fed dla USA, oficjalne banki centralne i urzędy statystyczne dla Europy, Japonii, Kanady i Australii. Używaj właściwych jednostek, źródeł i harmonogramów publikacji.
- **Globalny kontekst:** wiadomości ze świata mają być selekcjonowane według udokumentowanego wpływu na monitorowane rozwinięte rynki.

## 6. Minimalne wymagania dla generowanego MD

1. TL;DR zawiera przynajmniej jeden faktycznie istotny sygnał spoza USA, jeśli istnieje i jest udokumentowany. Nie wymyślaj sygnału, gdy brak wydarzeń.
2. Sekcja „Rynek w liczbach” ma co najmniej: USA, Europa rozwinięta i Japonia (odpowiedni benchmark lub wyraźnie nazwany proxy); dla Kanady i Australii dodaj dane, jeśli dostępne.
3. Pokaż datę ostatniej ukończonej sesji według regionu i walutę lub opis bazowej waluty benchmarku.
4. Nie mieszaj regionalnych indeksów i amerykańskich ETF-ów śledzących te indeksy w jednym szeregu czasowym bez opisu.
5. Jeśli brakuje danego regionu, użyj `partial`, a nie globalnego `complete`.
6. Nie zamieszczaj polskich indeksów, spółek GPW ani EM jako przedmiotów monitorowania. Dopuszczaj ich wpływ gospodarczy jako kontekst — jawnie oznaczony.
7. Ważne publikacje i wydarzenia banków centralnych innych rozwiniętych krajów mogą wystąpić obok Fed; priorytet zależy od siły informacji, nie wyłącznie kraju.

## 7. Testy akceptacyjne filtra

- Emitent z Polski: `excluded` nawet po notowaniu na giełdzie zagranicznej.
- Emitent z emerging market z ADR na NYSE/Nasdaq: `excluded`.
- Emitent z Holandii notowany w USA: `eligible`, jeśli klasyfikacja i tożsamość są prawidłowe.
- ETF notowany w USA z rzeczywistą ekspozycją na developed Europe: `eligible` po weryfikacji indeksu.
- ETF z mieszanym koszykiem Developed + Emerging: `requires_review` lub `excluded` według deklarowanej polityki (domyślnie `excluded` w rdzeniu raportu).
- Dzień wolny w Japonii, dzień sesyjny w USA: poprawna data cen dla obu regionów, bez sztucznego „0% dzisiaj”.
- Wszystkie źródła cen i FX mają jednostki, waluty oraz daty obserwacji.

## 8. Wskazówki dla Copilota

- Nie zakładaj, że jeden endpoint SEC albo jeden kalendarz giełdowy obejmuje cały świat.
- Nie twórz fikcyjnych symboli Yahoo dla indeksów zagranicznych; weryfikuj mapowanie lub używaj oznaczonego proxy.
- Nie wdrażaj wszystkiego jednocześnie: najpierw mały, regionalnie reprezentatywny raport, potem szersze pokrycie, a dopiero później rozbudowane dane fundamentalne zagranicznych emitentów.
