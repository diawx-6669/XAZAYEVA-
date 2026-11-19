# CLAUDE.md — AuditEnv: RL-среда для ИИ-аудитора

Этот файл — главное ТЗ проекта. Читай его целиком перед любой работой. Официальный текст кейса лежит в `docs/CASE.md`; если что-то здесь противоречит кейсу, прав кейс — сообщи о противоречии.

## 0. Что мы строим (в одном абзаце)

Воспроизводимый симулятор для обучения ИИ-аудитора с подкреплением. По `seed` и `config` генерируется вымышленная компания за один отчётный период: скрытая история событий → открытые документы и проводки → внесённые ошибки с записанной причиной → закрытый эталон. Агент через узкий набор инструментов (не больше 100 шагов) читает записи и отправляет выводы с доказательствами. Оценщик вне процесса агента сопоставляет выводы с эталоном и считает награду. **Баллы жюри дают за корректность среды и оценщика, а не за умного агента.** Обучать модели не нужно. UI не нужен.

Сдача: 22 ноября 2026, 23:59 (Астана). Работаем по этапам (см. раздел 12).

## 1. Жёсткие правила разработки

- Python 3.11. Только stdlib плюс `pytest`, `hypothesis`, `jsonschema`. Версии закреплены точно (`==`) в `requirements.txt`. Никаких numpy/pandas/ML, сети, платных API или GPU.
- **Деньги — только `int` в минимальных единицах.** FX-курсы — строки, считаются через `decimal.Decimal`. `float` для денег и курсов запрещён: это ломает воспроизводимость. Режим округления берётся из `policy.json`.
- **Детерминизм.** Используй только `random.Random(derived_seed)`, никакого глобального `random`, `time.time()`, `uuid4()`, `hash()` строк или итерации по `set` в выходных данных. Под-seed выводится через `hashlib.sha256(f"{seed}:{stream_name}")`. Потоки разделены: `story` (события и ошибки), `naming` (имена, ID, форматы), `order` (порядок строк).
- **Канонический JSON:** `json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`, переводы строк `\n`. В контейнере `TZ=UTC`.
- Агент никогда не видит `truth.json`, `provenance.json`, seed, пути к файлам, трейсбеки или debug-информацию.
- Каждое изменение сопровождается тестом. Перед коммитом: `make quick`. Коммиты маленькие, сообщения на английском.
- Не придумывай требований сверх кейса и этого файла. Если решение спорное — выбери самое простое, запиши его в `docs/DESIGN.md` (раздел «Решения») и продолжай.
- После каждого этапа коротко объясни по-русски, что сделано и как это проверить: команда работает с ИИ и должна понимать код.

## 2. Структура репозитория

```
auditenv/
  __init__.py            # __version__ = "0.1.0", SCHEMA_VERSION = "1.0"
  money.py               # minor units, exponent валют, Decimal-конвертация, округление
  ids.py                 # непредсказуемые ID из потока naming
  config.py              # загрузка/валидация конфигов, config_hash
  generator/
    story.py             # скрытая история: сущности, события (sale, payment, refund, ...)
    books.py             # события → документы и проводки (чистая книга)
    invariants.py        # бухгалтерские равенства
    errors/              # по одному модулю на тип ошибки: duplicate_invoice.py, payment_allocation.py, fx_rate.py, period_cutoff.py
      base.py            # интерфейс ErrorType: applicable(), inject(), canonical_ids(), evidence_sets(), expected_amount()
    distractors.py       # корректные отвлекающие случаи
    interactions.py      # сценарии взаимодействующих ошибок
    transforms.py        # безвредные преобразования: перестановка строк, переименование ID (с переносом в truth)
    episode.py           # generate_episode(seed, config) -> Episode(public, truth, provenance)
    export.py            # запись эпизода на диск: public/ и grader/ раздельно
  env/
    env.py               # AuditEnv: reset(seed, config, mode) / step(action)
    tools.py             # list_records, get_record, get_document, calculator, submit
    calculator.py        # безопасный AST-калькулятор
    cursors.py           # непрозрачные стабильные курсоры (HMAC)
    errors.py            # ограниченные коды ошибок
  grader/
    schema.py            # JSON Schema для findings
    normalize.py         # канонизация ID, сумм, валют
    matcher.py           # взаимно однозначное сопоставление
    reward.py            # P, R, F1, терминальная награда (общая) + экспериментальная (отдельно)
    validate_truth.py    # независимый решатель: находит каждую ошибку по ОТКРЫТЫМ данным без provenance
    log.py               # grader_log.jsonl
  policies/              # random_explorer.py, simple_reconcile.py, flag_all.py, oracle.py (+ атаки в attacks.py)
  runner.py              # прогон политики в ОТДЕЛЬНОМ процессе по JSON-lines; оценщик в родительском процессе
  selfcheck.py           # табло в духе жюри: 4 блока × проверки + диагностика P/R/F1/возврат/шаги/время
  leakscan.py            # поиск закрытых данных в наблюдениях траекторий
  cli.py                 # python -m auditenv {generate,run,check,replay,export}
configs/                 # именованные версии конфигов (train-easy.json, dev-mixed.json, clean-only.json, interaction-heavy.json)
schemas/                 # JSON Schema: manifest, ledger row, invoice, payment, fx, policy, action, observation, findings, truth
episodes/train/, episodes/dev/   # 10 + 10 открытых эпизодов (public/ и grader/)
tests/
docs/CASE.md, docs/DESIGN.md, docs/LIMITATIONS.md
trajectories/trajectories.jsonl
Makefile, Dockerfile, requirements.txt, LICENSE (MIT), README.md
```

## 3. Модель данных

### Валюты и деньги
- Базовая валюта эпизода — `base_currency` (по умолчанию KZT). Иностранные: USD, EUR, плюс одна с другой разрядностью (JPY exponent 0) в конфигах сложности medium/hard.
- Таблица exponent: KZT 2, USD 2, EUR 2, JPY 0, KWD 3. Хранится в `manifest.json` → `currencies: {code: exponent}`.
- Разные валюты сравниваются только после конвертации по `fx.csv` и правилу из `policy.json`.

### Открытые файлы эпизода (`public/`)
- `manifest.json`: `schema_version, episode_id, base_currency, currencies, period_start, period_end (ISO-8601 со смещением), timezone (IANA, например Asia/Almaty), counts {ledger, invoices, payments, fx}, rounding {mode: "ROUND_HALF_EVEN", fx_conversion: "per_document"}, config_hash, generator_version`.
- `ledger.csv`: `row_id, timestamp, account, debit_minor, credit_minor, currency, entity_id, invoice_id, payment_id`. Ровно эти колонки. **Все суммы ledger — в base_currency** (иностранные документы проведены с конвертацией). Пустые ссылки — пустая ячейка, которая читается как `null`.
- `invoices.jsonl`: `doc_id, invoice_id, entity_id, issued_at, due_at, currency, total_minor, line_items[{description, service_period, quantity, unit_price_minor, amount_minor}]`. Сумма `line_items` равна `total_minor`.
- `payments.jsonl`: `doc_id, payment_id, timestamp, currency, amount_minor, invoice_refs` (список ID или `null`).
- `fx.csv`: `date, source_currency, target_currency, rate`, где rate — десятичная строка. Курсы есть только на рабочие дни. Через инструменты у каждой строки появляется ID `fx:{date}:{src}:{tgt}`.
- `policy.json`: `fx_rate_date: "transaction_date"` (для счёта это issued_at, для платежа timestamp, дата берётся в локальном timezone компании), `fx_missing_rate: "previous_business_day"`, `period_boundary: {start, end, timezone, inclusive_start: true, inclusive_end: false}`, `rounding: "ROUND_HALF_EVEN"`, `recognition: "invoice_issue_date"`. Через инструменты доступен как запись с ID `policy`.

### План счетов
`1000 Cash`, `1200 Accounts Receivable`, `2400 Unapplied Cash`, `4000 Revenue`, `4100 Refunds`, `6500 Bank Fees`, `7900 FX Gain/Loss`.

### Проводки (чистая книга)
- Счёт: Dr 1200 / Cr 4000 на сумму в base currency; `invoice_id` указан в обеих строках.
- Платёж: Dr 1000 / Cr 1200 на каждую распределённую часть (`payment_id` и `invoice_id` указаны). Банковская комиссия идёт отдельной парой Dr 6500 / Cr 1000. Курсовая разница при оплате в иностранной валюте проводится на 7900.
- Возврат: Dr 4100 / Cr 1000 со ссылкой на счёт.

### Инварианты (`invariants.py`) — должны выполняться в чистой книге
1. Сумма дебетов равна сумме кредитов: по всей книге и по каждой группе событий (одинаковые `timestamp` + `invoice_id`/`payment_id`).
2. Сальдо 1200 по каждому счёту = сумма счёта в base − распределённые оплаты.
3. Каждый счёт и платёж из документов проведён ровно один раз; каждая строка ledger ссылается на существующий документ или на null там, где это допустимо.
4. Все timestamp проводок лежат внутри периода (в локальном timezone).
5. Конвертация соответствует policy и fx.csv с точностью округления.

После внесения ошибок: инварианты, которые эта ошибка не затрагивает, выполняются, а затронутый нарушен ровно на `expected_amount_minor`. Это проверяется тестом для каждого типа ошибки.

### Закрытые файлы (`grader/`)
- `truth.json`: `{episode_id, issues:[{issue_id, type, affected_ids, expected_amount_minor, currency, evidence_sets:[[id,...], ...]}]}`.
- `provenance.json`: seed, config, версия, список событий, список мутаций с «до/после» по каждой затронутой записи.

## 4. Четыре типа ошибок (независимо включаются в config)

Для всех типов `currency = base_currency`, а `expected_amount_minor` — **модуль искажения в base currency, посчитанный как разница между книгой до мутации и после**. В `evidence_sets` 1–3 альтернативных набора, каждый не больше 6 ID. Каждый ID набора реально доступен через инструменты.

| type | Мутация | canonical affected_ids | Сумма | Минимальное доказательство |
|---|---|---|---|---|
| `duplicate_invoice` | Добавляется второй документ-счёт (новые doc_id и invoice_id) с тем же entity, теми же line_items и суммой, дата сдвигается на 0–2 дня. Оба счёта проведены | `[invoice_id дубля]` | сумма дубля в ledger | doc_id оригинала, doc_id дубля, строки ledger дубля |
| `payment_allocation` | Варианты: (а) платёж не распределён (Cr 2400 вместо 1200, `invoice_id` null); (б) распределён частично (часть на 1200, остаток на 2400) | `[payment_id]` | нераспределённая часть в base | doc_id платежа, doc_id счёта, строки ledger платежа |
| `fx_rate` | Документ в иностранной валюте проведён по курсу не той даты (обычно соседний рабочий день) или по перевёрнутому курсу | `[invoice_id или payment_id]` | модуль(проведено − правильно) | doc_id документа, строки ledger, `fx:...` правильного курса, `policy` |
| `period_cutoff` | Счёт, выписанный вне периода по локальному времени (ловушка UTC: `2026-10-31T21:30:00+00:00` = 1 ноября в Астане), проведён внутри периода | `[invoice_id]` | сумма счёта в base | doc_id счёта, строки ledger, `policy` |

Все функции типа ошибки лежат в одном модуле и регистрируются в реестре, чтобы новый тип добавлялся одним файлом.

## 5. Отвлекающие (корректные) случаи — не ошибки

Включаются в config с долей от 0 до 1: ежемесячная аренда с одинаковой суммой, но разным `service_period`; оплата одного счёта двумя частями; один платёж на 2–3 счёта; законная частичная оплата с открытым остатком; возврат; банковская комиссия; разница округления в 1 минимальную единицу; операция в 23:50 по местному времени в последний день периода; отменённый счёт (credit note) с перевыставлением.

После генерации **сканер случайных совпадений** проверяет чистые данные: если случайно получилось что-то похожее на ошибку и это не запланированный отвлекающий случай, эпизод перегенерируется со следующим под-seed.

## 6. Взаимодействующие ошибки (минимум 2 сценария)
- `partial_fx_cutoff`: частичный платёж в EUR в последний день периода, распределённый частично и проведённый по неверному курсу. Даёт два issue (`payment_allocation` + `fx_rate`) с разными affected_ids или с явно разведёнными суммами.
- `duplicate_fx`: дубль счёта в USD, проведённый по неверному курсу. Даёт `duplicate_invoice` (сумма дубля, как он проведён) и `fx_rate` на оригинале.

Мутации применяются в фиксированном порядке. Сумма каждого issue считается как разница относительно состояния **перед этой мутацией**. Это правило описано в DESIGN.md.

## 7. Среда (`env.py`)

```python
env = AuditEnv(data_root=..., mode="train" | "eval")
obs, info = env.reset(seed=int, config=dict)      # или reset(episode_dir=...)
obs, reward, terminated, truncated, info = env.step(action)   # action: dict, JSON-совместимый
```
- Действие: `{"tool": "<name>", "args": {...}}`.
  - `list_records(table, cursor=None, limit=50)`: table ∈ {ledger, invoices, payments, fx}, `limit` ≤ 50. Возвращает `{records, next_cursor}`. Курсор непрозрачный (HMAC от episode_id, table, offset с ключом эпизода), стабильный и недействительный в другом эпизоде.
  - `get_record(table, id)`: table ∈ {ledger, invoices, payments, fx, policy}.
  - `get_document(doc_id)`: возвращает документ счёта или платежа.
  - `calculator(expression)`: только числа, `+ - * /`, унарный минус и скобки, через AST. Decimal с точностью 34, не больше 200 символов и 10 уровней вложенности. Никаких имён, вызовов, атрибутов или степеней.
  - `submit(findings)`: завершает эпизод с `terminated=true`.
- Первое наблюдение: `{task, manifest, policy_summary, steps_remaining: 100}`.
- Каждое наблюдение: `{result | error, steps_remaining}`, и больше ничего.
- Ошибки: `{"error": {"code": C}}`, где C ∈ {`unknown_tool`, `bad_args`, `not_found`, `invalid_cursor`, `calc_error`, `episode_over`}. Без сообщений с данными. Для «нет такого ID» и «ID из другой таблицы» ответ одинаковый (`not_found`). Ошибка тратит шаг.
- Лимит: 100 шагов, включая submit. Шаг 100 без submit даёт `truncated=true` и пустой итоговый ответ. Лимит времени (60 с, монотонные часы, в тестах подменяемые) тоже даёт `truncated`. Шаг после завершения возвращает `episode_over` и не меняет итог.
- Награда по ходу всегда 0. В режиме `train` терминальная награда возвращается на финальном шаге. В режиме `eval` reward=0, `info={}`, а итог пишется только в `grader_log.jsonl` оценщика.
- Эпизоды изолированы: reset сбрасывает всё состояние, два env в одном процессе не влияют друг на друга.
- Данные открываются только на чтение. У среды нет пути к `grader/`, туда ходит только оценщик.

## 8. Оценщик: matcher и награда

- **Валидация** `findings` по JSON Schema (`additionalProperties: false`): `{episode_id, findings:[{type, affected_ids, claimed_amount_minor (int), currency, evidence_ids, explanation}]}`. Не больше 30 выводов, 10 evidence_ids и 1000 символов explanation. Неверная структура или чужой `episode_id` дают награду −1, `terminated`, и ошибку в журнале оценщика.
- **Нормализация** (`normalize.py`, код открытый): у ID обрезаются пробелы, повторы удаляются, список сортируется; регистр сохраняется. Валюта приводится к верхнему регистру.
- **Вывод может совпасть с issue**, если: тип совпадает; нормализованные `affected_ids` в точности равны каноническим; `|claimed − expected| ≤ tolerance` (по умолчанию 1 минимальная единица); валюта совпадает; хотя бы один набор из `evidence_sets` целиком входит в `evidence_ids`.
- **Сопоставление взаимно однозначное:** максимальное паросочетание (достаточно перебора с возвратом или Хопкрофта–Карпа). При ничьей побеждает меньший `issue_id`, затем меньший индекс вывода. Несопоставленные и повторные выводы считаются FP, пропущенные issue — FN.
- **Метрики:** P=TP/(TP+FP), R=TP/(TP+FN) (при нулевом знаменателе 0); F1=2TP/(2TP+FP+FN). Если эталон и выводы пусты, F1=1; если эталон пуст, а выводы есть, F1=0.
- **Общая награда:** `clip(2*F1 − 1 − 0.002*inspection_steps, −1, 1)`, где `inspection_steps` — число шагов до submit без самого submit. При truncated ответ пустой.
- **Экспериментальная награда** (показывается отдельно): TP засчитывается, только если все ID из сработавшего набора доказательств агент реально получал в наблюдениях.
- `explanation` на награду не влияет никак.
- В журнале оценщика по каждому несовпадению пишется код причины: `wrong_type, ids_mismatch, amount_out_of_tolerance, currency_mismatch, evidence_incomplete, duplicate_finding, unmatched`.

## 9. Политики

Каждая политика — это адаптер с методом `act(observation) -> action`, который запускается через `runner.py` в отдельном процессе. Общение идёт по JSON-строкам через stdin/stdout.
- `random_explorer`: фиксированный seed, случайные допустимые действия, в конце submit пустого ответа.
- `simple_reconcile`: честный скриптовый аудитор. Читает таблицы постранично, ищет дубли (тот же entity + те же line_items), нераспределённые оплаты, пересчитывает FX по policy, проверяет даты по локальному timezone. Это и есть демо-политика.
- `flag_all`: обвиняет всё подряд в пределах лимитов.
- `oracle`: читает truth, **только для оценщика**, отправляет верные выводы с первым набором доказательств.
- `attacks.py`: «близнецы» (один вывод 30 раз), перебор 4 типов на одних ID, перебор сумм X±k, угадывание ID, спам доказательствами, мусорный explanation.

## 10. Обязательные тесты (pytest и hypothesis)

Контракт: формы reset/step; лимит 50 строк; стабильные курсоры; курсор из чужого эпизода; неизвестные tool и ID; шаг расходуется на ошибку; 100 шагов дают truncated; тайм-аут; шаг после конца; калькулятор против `__import__`, лямбд, `9**9**9`, длинных строк и деления на 0; режим eval без награды и info; изоляция двух env.

Данные: инварианты чистой книги для 50 seed; каждый тип ошибки нарушает ровно свой инвариант на expected_amount; каждое доказательство доступно через инструменты; `validate_truth` находит все issue на всех тестовых эпизодах; на чистых эпизодах truth пуст и решатель ничего не находит.

Награда: oracle на ошибочных книгах лучше пустого ответа; пустой ответ на чистых лучше любого обвинения; дубли не дают выгоды; flag_all даёт плохую награду; одинаковые ответы с 10 и 50 шагами отличаются ровно на 0.08; explanation не влияет; угаданный ID без доказательств даёт FP; неверная валюта даёт FP; неверный JSON даёт −1; перестановка findings не меняет F1; property-based: лишний FP не повышает награду, лишний TP не понижает.

Воспроизводимость: одинаковые seed, config и действия дают одинаковые байты эпизода, траектории и наград; `transforms` (перестановка строк + переименование ID) сохраняют награду oracle и F1 при переносе ID; golden-хеши 3 эпизодов.

Утечки: `leakscan` по всем траекториям не находит issue_id, типы рядом с affected_ids, пути `grader/` или seed.

## 11. Команды

- `make quick`: быстрые тесты и 3 эпизода × 4 политики, не дольше 30 с.
- `make check`: **единая команда проверки**. Полный pytest, `selfcheck` на 20 dev-эпизодах и 20 парных преобразованиях, leakscan, табло в консоль и в `reports/selfcheck.md` (блоки Контракт / Данные / Награда / Воспроизводимость + таблица P, R, F1, возврат, шаги, время по 4 политикам и атакам).
- `make episodes`: генерирует 10 train + 10 dev из `configs/`.
- `make trajectories`: пишет `trajectories/trajectories.jsonl` (episode_id, step, action, observation, reward, terminated, truncated) для всех политик, кроме oracle.
- `make docker-check`: `docker build` и `docker run --network none --cpus 2 --memory 4g auditenv make check`.

## 12. Этапы
1. Каркас, money, ids, схемы, генератор чистой компании, 2 типа ошибок (`duplicate_invoice`, `fx_rate`), среда, калькулятор, matcher, награда, тесты, `make quick`.
2. `payment_allocation`, `period_cutoff`, отвлекающие случаи, сканер совпадений, `validate_truth`, конфиги сложности.
3. Взаимодействующие ошибки, transforms, runner в отдельном процессе, 4 политики и атаки, leakscan, траектории, эпизоды train/dev, selfcheck.
4. Docker, README с картой «пункт ТЗ → файл → тест», DESIGN.md, LIMITATIONS.md с измеренными числами, разбор сбоев simple_reconcile по типам, сценарий демо.

Размеры по умолчанию (чтобы oracle и simple_reconcile укладывались в 100 шагов): 150–400 проводок, 20–60 документов, 0–6 ошибок. Пресет `stress` (до 2000 проводок) нужен только для проверки производительности.
