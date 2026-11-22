# Примеры правильных выводов

По одному верному выводу на каждый тип ошибки — из **открытых** эпизодов (`episodes/`). Сгенерировано
`python tools/findings_examples.py`; тест проверяет, что каждый пример проходит схему `schemas/findings.schema.json`
и даёт TP на своём эпизоде. Что должно совпасть для TP: тип, `affected_ids` (ровно канонический ID), сумма ±1,
валюта = базовая, и **один набор доказательств целиком** в `evidence_ids`. `explanation` на награду не влияет.

Отправка: `{"tool": "submit", "args": {"findings": {"episode_id": "…", "findings": [вывод, …]}}}`.
Проверить свой ответ офлайн: `python -m auditenv grade episodes/<split>/<id> my.json`.

## `duplicate_invoice` (вариант `copy`)

Эпизод `episodes/train/ep-j2mnqc5h54`, база KZT. Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200.

```json
{
 "type": "duplicate_invoice",
 "affected_ids": [
  "BL-SVAMKM"
 ],
 "claimed_amount_minor": 317232520,
 "currency": "KZT",
 "evidence_ids": [
  "DC-YJFAMY",
  "DC-EYD99S",
  "LR-P4XPNY"
 ],
 "explanation": "Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200."
}
```

Доказательства (что вернёт инструмент):

* `DC-YJFAMY` — счёт BL-VD7V47 от 2026-09-27T13:16:13+00:00, KZT 317232520, клиент CL-FD3CND
* `DC-EYD99S` — счёт BL-SVAMKM от 2026-09-28T13:46:07+05:00, KZT 317232520, клиент CL-FD3CND
* `LR-P4XPNY` — ledger 2026-09-28T13:46:07+05:00 счёт 1200 Dr 317232520 Cr 0 inv=BL-SVAMKM pay=null
* (есть ещё 1 альтернативный набор — подойдёт любой целиком)

## `payment_allocation` (вариант `unallocated`)

Эпизод `episodes/train/ep-kcj4hkgrcj`, база KZT. Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400.

```json
{
 "type": "payment_allocation",
 "affected_ids": [
  "BNK-E46CXS"
 ],
 "claimed_amount_minor": 786849369,
 "currency": "KZT",
 "evidence_ids": [
  "DOC-YX3FSND",
  "DOC-7AQKR2S",
  "DOC-DGQ6X6J",
  "GL-QKGNMY"
 ],
 "explanation": "Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400."
}
```

Доказательства (что вернёт инструмент):

* `DOC-YX3FSND` — платёж BNK-E46CXS от 2026-07-25T17:40:02+05:00, KZT 786849369, ссылки ['SF-VR3KJ2RV', 'SF-WXE475GD']
* `DOC-7AQKR2S` — счёт SF-VR3KJ2RV от 2026-07-01T08:43:44+00:00, KZT 339338465, клиент CP-HACM8C6H
* `DOC-DGQ6X6J` — счёт SF-WXE475GD от 2026-07-06T11:48:20+05:00, KZT 447510904, клиент CP-HACM8C6H
* `GL-QKGNMY` — ledger 2026-07-25T17:40:02+05:00 счёт 2400 Dr 0 Cr 786849369 inv=null pay=BNK-E46CXS

## `fx_rate` (вариант `adjacent_day`)

Эпизод `episodes/train/ep-ak4s2vjfjr`, база USD. Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте.

```json
{
 "type": "fx_rate",
 "affected_ids": [
  "RCV-WEX5ZM"
 ],
 "claimed_amount_minor": 2963,
 "currency": "USD",
 "evidence_ids": [
  "DOC-6252JX",
  "LR-6QAFFH3",
  "fx:2026-04-24:JPY:USD",
  "policy"
 ],
 "explanation": "Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `DOC-6252JX` — платёж RCV-WEX5ZM от 2026-04-25T13:08:14-11:00, JPY 1353472, ссылки ['SF-Z84AGW2']
* `LR-6QAFFH3` — ledger 2026-04-25T13:08:14-11:00 счёт 1000 Dr 897547 Cr 0 inv=null pay=RCV-WEX5ZM
* `fx:2026-04-24:JPY:USD` — fx 2026-04-24 JPY→USD = 0.00665333
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-02-01T00:00:00-11:00 … 2026-05-01T00:00:00-11:00
* (есть ещё 1 альтернативный набор — подойдёт любой целиком)

## `period_cutoff` (вариант `utc_trap`)

Эпизод `episodes/train/ep-6sbtnqcp2q`, база KZT. Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте.

```json
{
 "type": "period_cutoff",
 "affected_ids": [
  "INV-ATCDK3V"
 ],
 "claimed_amount_minor": 546668571,
 "currency": "KZT",
 "evidence_ids": [
  "FD-QMYHBQQD",
  "LR-5J7TYSQ",
  "policy"
 ],
 "explanation": "Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `FD-QMYHBQQD` — счёт INV-ATCDK3V от 2026-10-31T19:54:01+00:00, KZT 546668571, клиент CUST-6TY87T
* `LR-5J7TYSQ` — ledger 2026-10-31T19:54:01+00:00 счёт 1200 Dr 546668571 Cr 0 inv=INV-ATCDK3V pay=null
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-08-01T00:00:00+05:00 … 2026-11-01T00:00:00+05:00
