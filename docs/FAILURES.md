# Разбор сбоев simple_reconcile (измерено)

`simple_reconcile` — честный скриптовый аудитор: видит только то, что вернули инструменты.
Ниже — замер на 250 эпизодах (100 `dev-mixed`, 100 `interaction-heavy`, 50 `clean-only`,
seed 5000–5099 / 5000–5049), режим `train`, коды причин из журнала оценщика
(`grader/matcher.py::miss_reason`). Воспроизвести: табло `make check` содержит тот же разбор
на 20 эпизодах self‑check (`reports/selfcheck.md`, раздел «Разбор сбоев»).

## Полнота по типам и вариантам (раунд 2, все открытые конфиги)

<!--generated:variants-->
Замер: 300 эпизодов (`python -m auditenv analyze --n 300 --docs`), режим train.

| Тип / вариант | Встречается | Найдено simple_reconcile | Recall |
|---|---|---|---|
| duplicate_invoice / copy | 84 | 84 | 100% |
| duplicate_invoice / copy_as_posted | 57 | 57 | 100% |
| duplicate_invoice / paid_twice | 13 | 13 | 100% |
| fx_rate / adjacent_day | 119 | 63 | 53% |
| fx_rate / due_date | 11 | 8 | 73% |
| fx_rate / historical_rate | 12 | 4 | 33% |
| fx_rate / inverted | 11 | 11 | 100% |
| fx_rate / utc_date | 32 | 31 | 97% |
| fx_rate / wrong_pair | 23 | 13 | 57% |
| payment_allocation / partial | 115 | 115 | 100% |
| payment_allocation / unallocated | 43 | 43 | 100% |
| payment_allocation / wrong_invoice | 5 | 0 | 0% |
| period_cutoff / backdated_posting | 8 | 8 | 100% |
| period_cutoff / prior_period | 40 | 40 | 100% |
| period_cutoff / utc_trap | 31 | 31 | 100% |
| **итого** | **604** | **521** | **86%** |
<!--/generated-->

## Полнота по типам и вариантам (раунд 1, архив)

| Тип / вариант | Найдено | Почему |
|---|---|---|
| duplicate_invoice / copy | 60 / 60 (100 %) | |
| duplicate_invoice / copy_as_posted (сценарий duplicate_fx) | 100 / 100 (100 %) | |
| payment_allocation / partial | 103 / 103 (100 %) | |
| payment_allocation / unallocated | 28 / 28 (100 %) | |
| period_cutoff (UTC‑ловушка) | 70 / 70 (100 %) | переводит время в местный пояс |
| fx_rate / adjacent_day, рабочий день | 110 / 110 (100 %) | |
| fx_rate / utc_date, рабочий день | 40 / 40 (100 %) | |
| fx_rate / inverted, рабочий день | 15 / 15 (100 %) | |
| **fx_rate / любой вариант, документ в выходной** | **0 / 71 (0 %)** | нет правила `previous_business_day`: нет курса на дату — документ пропускается |

## Ложные выводы (217 на 250 эпизодов)

| Код причины | Кол‑во | Источник |
|---|---|---|
| `unmatched` (duplicate_invoice) | 83 | перевыставленный после credit note счёт принят за дубль: политика игнорирует ссылку `Credit note for <invoice_id>` в строках credit note |
| `ids_mismatch` (duplicate_invoice) | 62 | то же, но в эпизоде есть настоящий дубль с другим ID |
| `wrong_type` (fx_rate) | 72 | в `duplicate_fx` дубль скопирован по неверному курсу; политика не исключает дубли из проверки курса и докладывает fx_rate по ID дубля |

## Итоговая награда simple_reconcile

| Набор | Средняя награда |
|---|---|
| dev-mixed (100) | 0.497 |
| interaction-heavy (100) | 0.566 |
| clean-only (50) | −0.881 (почти всегда 1 FP из‑за credit note) |

## Что это говорит о среде

* Все четыре типа решаемы по открытым данным (oracle 1.0, независимый решатель сходится с
  truth на 1 000 эпизодах), но **не тривиальны**: три простые эвристики (без previous business
  day, без credit note, без исключения дублей) стоят 30–100 % награды.
* Чистые книги действительно штрафуют самоуверенную политику: одна ложная находка на чистой
  книге даёт −1.
* Отвлекающие случаи «аренда с одинаковой суммой», «оплата частями», «платёж на несколько
  счетов», «остаток округления 1 ед.», «операции в 23:50/00:05», «неопознанный платёж на 2400»
  simple_reconcile не обманули — ложных выводов от них 0.
