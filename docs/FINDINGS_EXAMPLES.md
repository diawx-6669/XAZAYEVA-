# Примеры правильных выводов

По одному верному выводу на каждый тип ошибки — из **открытых** эпизодов (`episodes/`). Сгенерировано
`python tools/findings_examples.py`; тест проверяет, что каждый пример проходит схему `schemas/findings.schema.json`
и даёт TP на своём эпизоде. Что должно совпасть для TP: тип, `affected_ids` (ровно канонический ID), сумма ±1,
валюта = базовая, и **один набор доказательств целиком** в `evidence_ids`. `explanation` на награду не влияет.

Отправка: `{"tool": "submit", "args": {"findings": {"episode_id": "…", "findings": [вывод, …]}}}`.
Проверить свой ответ офлайн: `python -m auditenv grade episodes/<split>/<id> my.json`.

## `duplicate_invoice` (вариант `copy`)

Эпизод `episodes/train/ep-qmagfmdtgk`, база KZT. Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200.

```json
{
 "type": "duplicate_invoice",
 "affected_ids": [
  "BL-782JS8"
 ],
 "claimed_amount_minor": 121529806,
 "currency": "KZT",
 "evidence_ids": [
  "DC-YJFAMY",
  "DC-MMQP8H",
  "LR-4WZP6M"
 ],
 "explanation": "Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200."
}
```

Доказательства (что вернёт инструмент):

* `DC-YJFAMY` — счёт BL-VD7V47 от 2026-10-19T11:15:16+00:00, KZT 121529806, клиент CL-4EEAKW
* `DC-MMQP8H` — счёт BL-782JS8 от 2026-10-20T08:46:07+00:00, KZT 121529806, клиент CL-4EEAKW
* `LR-4WZP6M` — ledger 2026-10-20T08:46:07+00:00 счёт 1200 Dr 121529806 Cr 0 inv=BL-782JS8 pay=null
* (есть ещё 1 альтернативный набор — подойдёт любой целиком)

## `payment_allocation` (вариант `unallocated`)

Эпизод `episodes/train/ep-axybv5w3gj`, база KZT. Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400.

```json
{
 "type": "payment_allocation",
 "affected_ids": [
  "BNK-MQX2YY"
 ],
 "claimed_amount_minor": 252181295,
 "currency": "KZT",
 "evidence_ids": [
  "DOC-3P9FQR6",
  "DOC-JRP3KQN",
  "GL-RNJ3J9"
 ],
 "explanation": "Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400."
}
```

Доказательства (что вернёт инструмент):

* `DOC-3P9FQR6` — платёж BNK-MQX2YY от 2026-09-02T09:13:52+05:00, KZT 252181295, ссылки ['SF-M2S52RAD']
* `DOC-JRP3KQN` — счёт SF-M2S52RAD от 2026-08-25T13:32:49+05:00, KZT 252181295, клиент CP-MYX8WEKC
* `GL-RNJ3J9` — ledger 2026-09-02T09:13:52+05:00 счёт 2400 Dr 0 Cr 252181295 inv=null pay=BNK-MQX2YY

## `fx_rate` (вариант `adjacent_day`)

Эпизод `episodes/train/ep-kcjvzycstz`, база USD. Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте.

```json
{
 "type": "fx_rate",
 "affected_ids": [
  "BL-W2TDZR"
 ],
 "claimed_amount_minor": 604,
 "currency": "USD",
 "evidence_ids": [
  "FD-6EB27NK",
  "LR-Q97N6ZQ",
  "fx:2026-12-22:KWD:USD",
  "policy"
 ],
 "explanation": "Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `FD-6EB27NK` — счёт BL-W2TDZR от 2026-12-22T22:54:32+00:00, KWD 771300, клиент CUST-DWM5Y7E
* `LR-Q97N6ZQ` — ledger 2026-12-22T22:54:32+00:00 счёт 1200 Dr 241833 Cr 0 inv=BL-W2TDZR pay=null
* `fx:2026-12-22:KWD:USD` — fx 2026-12-22 KWD→USD = 3.12757
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-11-01T00:00:00-05:00 … 2027-02-01T00:00:00-05:00

## `period_cutoff` (вариант `prior_period`)

Эпизод `episodes/train/ep-hg7nbxf7rj`, база KZT. Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте.

```json
{
 "type": "period_cutoff",
 "affected_ids": [
  "SF-3MCF5RE4"
 ],
 "claimed_amount_minor": 795518700,
 "currency": "KZT",
 "evidence_ids": [
  "FD-Z6CD8HG8",
  "JE-ZWNGYWQ",
  "policy"
 ],
 "explanation": "Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `FD-Z6CD8HG8` — счёт SF-3MCF5RE4 от 2026-07-28T05:42:37+00:00, KZT 795518700, клиент CUST-4CSRVK
* `JE-ZWNGYWQ` — ledger 2026-07-28T05:42:37+00:00 счёт 1200 Dr 795518700 Cr 0 inv=SF-3MCF5RE4 pay=null
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-08-01T00:00:00+05:00 … 2026-11-01T00:00:00+05:00
