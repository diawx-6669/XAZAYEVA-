# Компании, собранные вручную (фикстуры)

Сюда кладутся компании, которые человек построил сам в Google Таблицах, вместе с **его** ответом.
Тест `tests/test_fixtures.py` проверяет для каждой папки, что
`validate_truth` (решатель в репозитории), `tools/verify_independent.py` (независимый проверяльщик, без
импорта `auditenv`) и `oracle` дают **ровно ответ автора** из `issues.csv`, а файлы проходят схемы.

## Как добавить компанию

1. Формат листов — тот же, что у ручного аудита (`audit/*/`, `docs/MANUAL_AUDIT.md`). Проще всего взять
   папку `audit/2_clean_*` как шаблон, скопировать листы в Google Таблицу и править там.
2. Каждый лист: *Файл → Скачать → CSV*. Имена файлов: `ledger.csv`, `invoices.csv`, `payments.csv`,
   `fx.csv`, `policy.csv`, `issues.csv` (+ необязательный `meta.csv` с ключами `episode_id`, `author`, `source`).
3. Положить в `tests/fixtures/<имя>/`. Компании Ибры: `ibra_duplicate/`, `ibra_fx_rate/`, `ibra_clean_rent/`
   (для них тест ещё и сверяет тип ошибки; пока папок нет, `test_ibra_companies` помечен как пропущенный).
4. Проверить: `python -m pytest -q tests/test_fixtures.py`; посмотреть, что получилось:
   `python -m auditenv import-csv --src tests/fixtures/<имя> --out /tmp/ep` и
   `python -m auditenv run --policy simple_reconcile --episode-dir /tmp/ep`.

Правила листов (подробно — docstring `auditenv/fixtures.py`): суммы — целые в минимальных единицах
(`*_minor`), лишние колонки (`local_time`, `debit`, `credit`, `total`, `amount`, `weekday`, `fx_id`)
игнорируются; `invoice_refs` и наборы доказательств — через `;`; пустая ячейка = `null`. В `issues.csv`
`currency` — базовая валюта, `expected_amount_minor` — модуль искажения в базовой валюте. Ячейка, которая не
читается, — ошибка с именем листа, строкой и колонкой; импорт ничего не «чинит».
