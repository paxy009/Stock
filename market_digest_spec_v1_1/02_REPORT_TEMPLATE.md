# Market Digest — wzorzec raportu Markdown

**To jest SZABLON, a nie prawdziwy raport giełdowy.** Wszystkie oznaczenia w nawiasach `{{...}}` są polami do uzupełnienia **wyłącznie z rzeczywistych, zweryfikowanych danych**. Jeśli ich brakuje, użyj „Brak danych” i wskaż powód.

---

# Market Digest — {{report_date_local}} ({{day_of_week_pl}})

> **Stan na:** {{generated_at_local}} Europe/Warsaw  
> **Ostatnie zakończone sesje (wg rynku):** USA: {{last_us_market_session_date}} · Europa: {{last_europe_session_date}} · Japonia: {{last_japan_session_date}} · Kanada/Australia: {{last_other_developed_session_dates}}  
> **Rodzaj dnia dla regionów:** {{regional_session_statuses}}  
> **Status raportu:** {{complete|partial|template_fallback}}  
> **Źródła aktualizowane do:** {{latest_source_timestamp_utc}}  
> **Wersja danych / run:** {{snapshot_id}} / {{run_id}}

## TL;DR — najważniejsze w 60 sekund

1. **{{observation_1}}** — {{why_it_matters_1}} [źródło](https://example.org/replace-with-real-url)
2. **{{observation_2}}** — {{why_it_matters_2}} [źródło](https://example.org/replace-with-real-url)
3. **{{observation_3}}** — {{why_it_matters_3}} [źródło](https://example.org/replace-with-real-url)

**Obraz rynku:** {{neutral_summary_2_3_sentences}}.

**Na co zwrócić uwagę jutro / w kolejnym dniu sesyjnym:** {{one_or_two_concrete_items_with_dates}}.

## 1. Rynek w liczbach — globalne rynki rozwinięte

**Kontekst:** USA {{us_snapshot_status}}, Europa {{europe_snapshot_status}}, Azja rozwinięta {{asia_snapshot_status}}, Kanada/Australia {{other_snapshot_status}}. Każdy wiersz ma własną datę sesji i walutę; podane ETF-y notowane w USA są **proxy ekspozycji na region**, a nie lokalną sesją giełdową.

| Region / instrument | Waluta / baza | Ostatni kurs | Zmiana 1 sesja | 5 sesji | 1 miesiąc / 21 sesji | Od szczytu 52 tyg. | Dane z |
|---|---|---:|---:|---:|---:|---:|---|
| USA — S&P 500 / SPY | {{USD/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| USA — Nasdaq-100 / QQQ | {{USD/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| Europa — STOXX Europe 600 / lokalny indeks (jeśli dostępny) | {{currency/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| Europa — VGK (ETF proxy, sesja USA) | {{USD/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| Japonia — Nikkei 225 / lokalny indeks (jeśli dostępny) | {{JPY/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| Japonia — EWJ (ETF proxy, sesja USA) | {{USD/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| Kanada — S&P/TSX / lokalny indeks (jeśli dostępny) | {{CAD/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| Australia — S&P/ASX 200 / lokalny indeks (jeśli dostępny) | {{AUD/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |
| Złoto / odpowiedni instrument | {{USD/price_basis}} | {{}} | {{}} | {{}} | {{}} | {{}} | {{date}} |

*Uwaga metodologiczna: „1 sesja” porównuje dwa ostatnie zakończone dni notowań właściwej giełdy; dla braku sesji nie tworzymy fikcyjnego ruchu dziennego. Wiersze z różnymi strefami i bazami walutowymi nie są bezpośrednio porównywalne bez normalizacji. ETF-y notowane w USA śledzące inne regiony są osobno oznaczone. Futures i ETF-y mają różne definicje ceny i ekspozycji.*

### Największe ruchy

- **{{ticker}}:** {{change_1d}}; ruch względem benchmarku: {{relative_return}}. **Potwierdzone fakty:** {{known_events}}. **Przyczyna ruchu:** {{verified|not_confirmed}}. [Źródło](https://example.org/replace-with-real-url)
- **{{ticker}}:** ...

## 2. Co zmieniło się od poprzedniego raportu?

| Obszar | Poprzednio | Teraz | Znaczenie |
|---|---|---|---|
| {{NVDA/AI/Fed/...}} | {{prior_value_or_assessment}} | {{new_value_or_assessment}} | {{impact_and_limitations}} |

- **Nowe potwierdzone wydarzenia:** {{...}}
- **Nowe informacje w istniejących sprawach:** {{...}}
- **Sprostowania / zmiany oceny:** {{...}}

## 3. Najważniejsze wiadomości i zdarzenia korporacyjne

### {{Event title}}

- **Co wiadomo:** {{fact_summary}}.
- **Status:** {{official_filing|official_statement|credible_media_report|unverified_claim}}.
- **Czas zdarzenia / publikacji:** {{event_at}} / {{published_at}}.
- **Dlaczego ważne:** {{effect_on_business_or_risk}}.
- **Czego jeszcze nie wiadomo:** {{explicit_uncertainty}}.
- **Źródła:** [{{source_name}}]({{source_url}}) ({{published_date}}).

*Nie dodawaj więcej niż 5 wyróżnionych wydarzeń. Pozostałe umieść w sekcji „Pozostałe wiadomości” lub pomiń.*

## 4. Wyniki finansowe, wyceny i jakość biznesu

| Spółka | Przychody YoY (ostatni opublikowany okres) | EPS / zysk | Marża / FCF | Wycena | Najważniejsze zastrzeżenie |
|---|---:|---:|---:|---:|---|
| {{TICKER}} | {{}} | {{}} | {{}} | {{P/E|N/A}} | {{...}} |

**Analiza:** {{Czego dowodzą dane, co jest prognozą, czy zmienił się guidance, czy kurs reagował na zysk, czy na mnożnik wyceny}}.

**Jakość danych:** {{data_recency_and_coverage}}.

*Jeżeli w danym dniu nie ma nowych wyników, podaj „Brak nowych raportów” i najwyżej 1–2 ważne zmiany względem poprzedniej analizy.*

## 5. Makro — USA i pozostałe rynki rozwinięte

| Wskaźnik | Ostatnia wartość | Okres danych | Data publikacji | Zmiana / kontekst |
|---|---:|---|---|---|
| Stopa Fed | {{}} | {{}} | {{}} | {{}} |
| US Treasury 2Y | {{}} | {{}} | {{}} | {{}} |
| US Treasury 10Y | {{}} | {{}} | {{}} | {{}} |
| CPI / PCE | {{}} | {{}} | {{}} | {{}} |
| Bezrobocie | {{}} | {{}} | {{}} | {{}} |
| VIX | {{}} | {{}} | {{}} | {{}} |

**Interpretacja:** {{two_or_three_sentences}}.  
**Ważne:** oczekiwania dotyczące przyszłych stóp procentowych ≠ bieżąca decyzja banku centralnego.

**Pozostałe rozwinięte regiony (gdy dane dostępne i istotne):**

| Region | Bank centralny / wskaźnik | Wartość | Publikacja | Znaczenie |
|---|---|---:|---|---|
| Strefa euro | ECB / {{series}} | {{}} | {{date}} | {{...}} |
| Wielka Brytania | BoE / {{series}} | {{}} | {{date}} | {{...}} |
| Japonia | BoJ / {{series}} | {{}} | {{date}} | {{...}} |
| Kanada / Australia | BoC / RBA / {{series}} | {{}} | {{date}} | {{...}} |

Nie dopisuj pustych wierszy, jeśli dane nie są dostępne. Nie traktuj decyzji Fed jako jedynego czynnika makro poza USA.

## 6. AI, infrastruktura i przewaga konkurencyjna

**Co rzeczywiście się zmieniło:** {{changes_in_capex_revenues_guidance_cash_flow}}.  
**Co wspiera dalszy rozwój:** {{evidence}}.  
**Co może go ograniczać:** {{evidence}}.  
**Powiązania finansowe / circular financing:** {{verified_relationships_or_no_new_evidence}}.  
**Konkurencja i substytuty:** {{GPU/ASIC/open_source_with_sources}}.

*Nie opisuj sztucznego popytu ani oszustwa jako faktów bez odpowiednich dowodów.*

## 7. Sektory dodatkowe: uran, energia, banki, surowce

- **Uran i energetyka jądrowa:** {{only_if_new_relevant_data; separate uranium prices from miners' profit}}.
- **Banki / kredyt:** {{only_if_new_relevant_data}}.
- **Złoto, srebro, ropa, miedź:** {{only_if_significant_movement_or_relevant_news}}.

*Jeśli brak istotnych zmian, użyj jednego zdania zamiast pustych tabel.*

## 8. Główne scenariusze: wzrostowy, neutralny, spadkowy

| Scenariusz | Fakty i warunki, które by go wspierały | Co mogłoby go podważyć |
|---|---|---|
| Wzrostowy | {{observable_conditions}} | {{counter_evidence}} |
| Neutralny | {{observable_conditions}} | {{counter_evidence}} |
| Spadkowy | {{observable_conditions}} | {{counter_evidence}} |

*To warunki do monitorowania, nie wyliczone prawdopodobieństwa ani polecenia inwestycyjne.*

## 9. Opinie z internetu — fact-check (gdy występują istotne tezy)

| Teza | Status weryfikacji | Uzasadnienie | Źródło |
|---|---|---|---|
| „{{claim}}” | {{supported/contradicted/partial/insufficient/pending}} | {{brief_reason}} | [{{source}}]({{url}}) |

**Przykład problemu metodologicznego:** podawanie zysku „od ceny IPO” i zysku „od otwarcia handlu” jako tej samej stopy zwrotu jest błędne — oba punkty odniesienia muszą być opisane.

## 10. Co warto obserwować dalej?

1. **{{event_with_exact_date}}** — {{why_and_what_data_will_change}}.
2. **{{event_with_exact_date}}** — {{why_and_what_data_will_change}}.
3. **{{indicator_or_earnings}}** — {{what_to_verify}}.

## 11. Jakość danych i ograniczenia

- **Pokrycie watchlisty:** {{received}}/{{requested}} instrumentów; osobno: USA {{us_coverage}}, Europa {{europe_coverage}}, Azja rozwinięta {{asia_coverage}}, pozostałe rozwinięte {{other_coverage}}.
- **Filtr geograficzny:** {{developed_markets_classification_version}}; wykluczone: {{excluded_or_flagged_instruments}}.
- **Nieaktualne serie:** {{list_with_last_date_or_none}}.
- **Niedostępne źródła:** {{list_or_none}}.
- **Niepotwierdzone zależności przyczynowe:** {{list_or_none}}.
- **Dane wymagające licencji:** {{list_or_none}}.
- **Tryb awaryjny:** {{yes_no_and_reason}}.

## 12. Źródła i metodologia

1. [{{source_1_title}}]({{source_1_url}}), opublikowano: {{date}}, pobrano: {{date}}.
2. [{{source_2_title}}]({{source_2_url}}), opublikowano: {{date}}, pobrano: {{date}}.

Metryki liczone z {{price_basis}}; okresy odnoszą się do {{trading_sessions/calendar_days}}, godziny {{timezone}}; pozostałe definicje: {{methodology_link}}.

---

*Raport informacyjny, nie stanowi indywidualnej rekomendacji inwestycyjnej. Decyzje wymagają samodzielnej oceny ryzyka.*

## Zasady redakcyjne (kontrakt)

- W sekcji TL;DR unikaj zdań typu „rynek spadł, ponieważ X”, jeśli brak potwierdzenia. Używaj: „w tym samym czasie”, „możliwe wyjaśnienie”, „nie znaleziono jednoznacznego dowodu”.
- Tytuły nie mogą być clickbaitem.
- Powtarzające się fakty grupuj; wykazuj tylko **zmiany** względem poprzedniego raportu.
- Gdy brak nowego raportu wyników, nie recytuj w pełni historycznych wyników każdej spółki.
- Podawaj oryginalne waluty i jednostki; jeśli zestawiasz stopy zwrotu między regionami, użyj konsekwentnie przeliczenia do wspólnej waluty, z datami i źródłem FX. Oddzielaj ruch ceny od total return.
- Sekcja światowa ma być krótka i selektywna; nie wymuszaj jednakowej liczby wiadomości lub identycznych tabel dla każdego regionu.
- Poprawność i źródła ważniejsze niż pełna objętość. Krótszy raport z dobrymi danymi wygrywa z długim raportem pełnym spekulacji.
- Każdy link w finalnym raporcie musi rzeczywiście pochodzić ze snapshotu wejściowego; adresy `example.org` powyżej są wyłącznie demonstracyjne i **nie mogą** trafić do wysyłanego raportu.
