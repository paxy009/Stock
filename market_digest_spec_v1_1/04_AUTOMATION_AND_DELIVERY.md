# Market Digest — automatyzacja, dostarczenie raportów i eksploatacja

## 1. Cel operacyjny

Użytkownik **otrzymuje codziennie plik `.md`**, nie tylko obserwuje nowy plik w folderze. Raport musi powstawać bez ręcznego otwierania VS Code i bez asystenta w trybie interaktywnym.

Trzy osobne obowiązki:

1. **Generowanie:** przygotuj i zatwierdź raport.
2. **Archiwizacja:** zachowaj raport i dane potrzebne do odtworzenia.
3. **Dostarczenie:** wyślij plik na ustalony kanał, zachowaj status wysyłki i obsłuż błędy.

Nie uznawaj zadania za ukończone tylko dlatego, że proces Pythona zwrócił kod 0.

## 2. Harmonogram — domyślne decyzje

- `timezone: Europe/Warsaw`.
- `daily_at: '23:30'` — każdego dnia, również w weekendy.
- **Po sesji USA:** raport obejmuje również ostatnie dostępne zamknięcia Europy, Japonii, Kanady i Australii; przed wygenerowaniem sprawdź dostępność danych **oddzielnie w każdym regionie**.
- **Dzień częściowo sesyjny:** jeden region może mieć święto, gdy drugi normalnie handluje. Nie uogólniaj statusu „brak sesji” z USA na cały świat.
- **Dzień bez sesji / święto:** raport krótszy, ze wskazaniem daty ostatniej sesji; brak fikcyjnych ruchów „dziś”.
- **Niedziela:** raport dzienny zawiera dodatkowo podsumowanie tygodnia i nadchodzący kalendarz.
- Wcześniejsze zamknięcia sesji i różnice w DST: użyj **właściwego kalendarza giełdowego dla każdego instrumentu**; godzina wywołania nie jest dowodem, że wszystkie dane są już końcowe.
- Dostawcy mogą publikować indeksy regionalne z opóźnieniem. W razie opóźnienia raport może użyć starszej wartości **z jawną datą i statusem**, zamiast mylić ją z bieżącą sesją. ETF regionalny notowany w USA nie zastępuje bez komentarza lokalnego indeksu.
- Jeśli dane cenowe są wstępne/niedostępne: krótki retry, a następnie częściowy raport lub alert — nie dopisuj cen z wyobraźni.

## 3. Rekomendowany kanał dostarczenia: e-mail

**Domyślny projekt** (dostawca i adres do uzupełnienia):

- Temat: `Market Digest | {{YYYY-MM-DD}} | {{Complete/Partial}}`.
- Treść maila: regionalne daty ostatnich sesji lub link do tej sekcji raportu + 3 kluczowe wnioski + status kompletności + informacja o załączniku.
- Załącznik: `YYYY-MM-DD.md` (UTF-8, `text/markdown` lub `text/plain` zależnie od wsparcia dostawcy).
- Nie wysyłaj wiadomości bez działającego pliku ani linków na podstawie niezweryfikowanych wpisów.
- Klucz deduplikacji: `report_date + delivery_channel + report_version`.
- W bazie zapisuj `pending`, `sent`, `failed`, `delivery_id`, `last_attempt_at`, `error_category`.
- Jeżeli raport powstał, ale mail nie dotarł, ponawiaj **tylko dostarczenie**; nie uruchamiaj ponownie LLM bez potrzeby.

**Alternatywy później:** wiadomość Telegram/Discord z załącznikiem, GitHub Release, prywatna strona z archiwum. To opcje, nie wymagania MVP.

## 4. Wybór środowiska uruchomieniowego

| Wariant | Zalety | Ograniczenia | Wniosek |
|---|---|---|---|
| Windows Task Scheduler + lokalny SQLite | Najprostsze testy i pierwsza wersja, brak kosztu hostingu | Komputer musi być włączony i mieć internet; brak globalnej dostępności | Dobry prototyp |
| VPS / mały serwer + cron/systemd + SQLite | Stały dysk, stabilne zadania, łatwy stan i kopie zapasowe | Koszt i administracja, aktualizacje bezpieczeństwa | Dobry wariant docelowy dla prywatnego systemu |
| GitHub Actions + trwały magazyn | Brak własnego serwera, harmonogram repozytorium | Runner jest efemeryczny; wymaga trwałego storage i konfiguracji sekretów; harmonogram może być opóźniany | Dobry wariant docelowy, jeśli dopracujesz trwałość danych |

**Ważne:** artefakty GitHub Actions nie są jedynym trwałym magazynem historii. Nie zakładaj, że lokalny `data/market.db` przeżyje kolejne uruchomienie runnera. Potrzebny jest zewnętrzny magazyn/synchronizacja, odpowiedni dla SQLite i jednego procesu piszącego, albo trwała zewnętrzna baza danych. Nie commituj sekretów ani prywatnych danych do repozytorium.

## 5. GitHub Actions — wymagania do przyszłej implementacji

Z dokumentacji GitHub wynika, że `on.schedule` obsługuje `timezone` IANA. Docelowy workflow powinien uruchamiać się według strefy `Europe/Warsaw`, np. o 23:30. **Ten pakiet nie zawiera gotowego workflow — implementacja dopiero po wyborze środowiska i źródła trwałego storage.**

- `workflow_dispatch` do ręcznego uruchomienia i ponownego przesłania wskazanego raportu.
- `concurrency`/blokada, aby dwa joby nie zapisywały równocześnie tego samego stanu.
- Najmniejsze wymagane `permissions`.
- Sekrety (SMTP/API/FRED/LLM) w GitHub Secrets albo innym tajnym magazynie.
- Weryfikacja danych przed wysyłką, brak publicznych logów z sekretami.
- Kontrola statusu generowania i dostarczenia.
- Test end-to-end na fikcyjnych danych przed pierwszą realną wysyłką.
- **Opóźnienie lub utrata uruchomienia schedule są możliwe**; zaprojektuj zewnętrzny heartbeat/alert albo nadzór oraz manualne wznowienie. Nie obiecuj dostarczenia „dokładnie o 23:30”.

Źródła: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax oraz https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows.

## 6. Provider LLM i praca bez nadzoru

GitHub Copilot Pro można wykorzystać jako **narzędzie do stworzenia kodu**. Oddzielną decyzją jest, czy Copilot SDK będzie dostawcą LLM w **nocnym procesie na serwerze**.

- Na etapie projektu nie zakładaj, że aktywna sesja Copilota w IDE działa na GitHub Actions.
- Przeprowadź „spike”: prosty headless run z docelowym sposobem autoryzacji, rozliczaniem, timeoutem i raportowaniem usage.
- SDK wspiera różne tryby autoryzacji (w tym BYOK); sprawdź warunki konkretnego konta i sposobu wdrożenia.
- Trzy adaptery: Copilot SDK, kompatybilne API LLM i renderer bez LLM.
- Jeżeli generowanie przez LLM jest niedostępne, **pipeline nadal może wysłać raport szablonowy**.

Źródła: https://docs.github.com/en/copilot/get-started/sdk-quickstart, https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth oraz https://docs.github.com/en/copilot/how-tos/copilot-sdk/features/usage-and-billing.

## 7. Pipeline uruchomienia i kontrola jakości

```text
[lock] -> [check calendar] -> [fetch/cache] -> [normalize/save]
       -> [calculate/verify] -> [evidence snapshot]
       -> [LLM or fallback] -> [report QA] -> [write atomically]
       -> [archive] -> [send email] -> [record delivery status]
       -> [health/heartbeat]
```

**Publikacja atomowa:** najpierw plik tymczasowy, walidacja, potem rename do docelowej ścieżki. Nie wysyłaj niedokończonego pliku.

**Powtórne uruchomienie:** to samo `report_date` może mieć nową wersję po poprawkach danych; historia zmian pozostaje odtwarzalna, a ponowne wysyłanie wymaga świadomej polityki (`only_if_changed` lub manual).

**Identyfikacja dnia:** data raportu = lokalna data Warsaw. Data ostatniej sesji oraz timezone są **oddzielne dla każdego rynku**, a daty danych należą do poszczególnych obserwacji. Dla „wczoraj” porównuj raporty chronologicznie, nie tylko kursy USA.

## 8. Niepowodzenia i oczekiwane zachowanie

| Sytuacja | Zachowanie |
|---|---|
| Jeden ticker niedostępny | Kontynuuj z flagą braku, nie licz dla niego sztucznego `0` |
| Cały feed cenowy niedostępny | Raport news/makro `partial` albo alert; brak metryk cenowych |
| SEC/FRED chwilowo niedostępne | Użyj ostatniej zweryfikowanej wartości z datą lub oznacz brak |
| Zewnętrzny RSS zwraca niepoprawny XML | Log i pominięcie tego źródła; reszta działa |
| Model AI nie odpowiada / limit | `TemplateProvider`, wyraźny status awaryjny |
| Raport jest gotowy, SMTP nie działa | Zachowaj plik i do ponowienia skieruj tylko dostarczenie |
| Nie przyszło uruchomienie schedulerowe | Monitoring wykrywa brak `heartbeat` i zgłasza alarm |
| Brak danych weekend | Krótki digest informacji oraz ostatnie daty sesji według regionów |
| Święto w USA, normalna sesja w Europie/Japonii | Dane z aktywnych rynków aktualizowane, USA z oznaczoną ostatnią sesją |
| ETF regionalny notowany w USA a lokalny indeks | Pokazuj różnicę kalendarza, waluty i instrumentu bazowego |
| Dane zawierają sprzeczne ceny | Nie wybieraj liczby arbitralnie; status `needs_review` |

## 9. Backup, koszty, retencja

- Zachowuj wszystkie raporty; plan retencji i backupu bazy określony jawnie (minimum kopia co 7 dni i przy migracjach).
- Logi z metrykami operacyjnymi bez danych uwierzytelnienia.
- Ogranicz liczbę newsów przekazywanych do LLM, buforuj statyczne dane i skanuj wyłącznie nowe dokumenty.
- Mierz: koszt/dzienny limit modelu, liczbę wywołań do API, czas realizacji, rozmiar danych, odsetek dostępnych tickerów i dostarczenia.
- Raport kontrolny tygodniowy: ile raportów wygenerowano, ile doręczono i ile danych było nieaktualnych.

## 10. Warunki akceptacji dostarczenia

1. Planowane uruchomienie bez IDE → gotowy plik MD.
2. Plik pojawia się w trwałym archiwum, niezależnym od poczty.
3. Załącznik trafia na testową skrzynkę i jest czytelny jako Markdown.
4. Mail ma status doręczenia lub udanego nadania (nie obiecuj potwierdzenia przeczytania, którego SMTP nie dostarcza).
5. Powtórny run nie wysyła identycznego raportu drugi raz.
6. Gdy SMTP nie działa, użytkownik otrzymuje alert innym kanałem/po jego naprawieniu; brak raportu jest wykrywalny.
7. Dni bez sesji i zmiana czasu (również zróżnicowane święta w Europie, USA, Japonii i Australii) nie powodują niewłaściwego raportu.
8. Raport odróżnia brak danych regionu od zaplanowanego dnia wolnego i oznacza datę ostatniej sesji w każdym regionie.
