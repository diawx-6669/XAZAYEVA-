# Примеры правильных выводов

По одному верному выводу на каждый тип ошибки — из **открытых** эпизодов (`episodes/`). Сгенерировано
`python tools/findings_examples.py`; тест проверяет, что каждый пример проходит схему `schemas/findings.schema.json`
и даёт TP на своём эпизоде. Что должно совпасть для TP: тип, `affected_ids` (ровно канонический ID), сумма ±1,
валюта = базовая, и **один набор доказательств целиком** в `evidence_ids`. `explanation` на награду не влияет.

Отправка: `{"tool": "submit", "args": {"findings": {"episode_id": "…", "findings": [вывод, …]}}}`.
Проверить свой ответ офлайн: `python -m auditenv grade episodes/<split>/<id> my.json`.

## `duplicate_invoice` (вариант `copy`)

Эпизод `episodes/train/ep-wtma6rce3f`, база KZT. Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200.

```json
{
 "type": "duplicate_invoice",
 "affected_ids": [
  "BL-KPWBBZ"
 ],
 "claimed_amount_minor": 121529806,
 "currency": "KZT",
 "evidence_ids": [
  "DC-YJFAMY",
  "DC-4WZP6M",
  "LR-AKXYEQ"
 ],
 "explanation": "Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200."
}
```

Доказательства (что вернёт инструмент):

* `DC-YJFAMY` — счёт BL-VD7V47 от 2026-10-19T11:15:16+00:00, KZT 121529806, клиент CL-4EEAKW
* `DC-4WZP6M` — счёт BL-KPWBBZ от 2026-10-20T08:46:07+00:00, KZT 121529806, клиент CL-4EEAKW
* `LR-AKXYEQ` — ledger 2026-10-20T08:46:07+00:00 счёт 1200 Dr 121529806 Cr 0 inv=BL-KPWBBZ pay=null
* (есть ещё 1 альтернативный набор — подойдёт любой целиком)

## `payment_allocation` (вариант `unallocated`)

Эпизод `episodes/train/ep-rntewpty5c`, база KZT. Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400.

```json
{
 "type": "payment_allocation",
 "affected_ids": [
  "BNK-MQX2YY"
 ],
 "claimed_amount_minor": 355081979,
 "currency": "KZT",
 "evidence_ids": [
  "DOC-3P9FQR6",
  "DOC-CQRYGNR",
  "GL-8M2DJJ"
 ],
 "explanation": "Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400."
}
```

Доказательства (что вернёт инструмент):

* `DOC-3P9FQR6` — платёж BNK-MQX2YY от 2026-08-20T07:40:01+00:00, USD 728094, ссылки ['SF-BV3353Q6']
* `DOC-CQRYGNR` — счёт SF-BV3353Q6 от 2026-08-09T10:19:38+05:00, USD 728094, клиент CP-YQ77TTFM
* `GL-8M2DJJ` — ledger 2026-08-20T07:40:01+00:00 счёт 2400 Dr 0 Cr 355081979 inv=null pay=BNK-MQX2YY

## `fx_rate` (вариант `adjacent_day`)

Эпизод `episodes/train/ep-mt68p5wbd2`, база USD. Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте.

```json
{
 "type": "fx_rate",
 "affected_ids": [
  "BL-M4525R"
 ],
 "claimed_amount_minor": 2834,
 "currency": "USD",
 "evidence_ids": [
  "FD-TJFKT9J",
  "LR-KFF4SQT",
  "fx:2026-12-04:JPY:USD",
  "policy"
 ],
 "explanation": "Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `FD-TJFKT9J` — счёт BL-M4525R от 2026-12-06T12:04:37-05:00, JPY 1660150, клиент CUST-VRAT6J9
* `LR-KFF4SQT` — ledger 2026-12-06T12:04:37-05:00 счёт 1200 Dr 1180297 Cr 0 inv=BL-M4525R pay=null
* `fx:2026-12-04:JPY:USD` — fx 2026-12-04 JPY→USD = 0.00712665
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-11-01T00:00:00-05:00 … 2027-02-01T00:00:00-05:00

## `period_cutoff` (вариант `prior_period`)

Эпизод `episodes/train/ep-p2ndc2nyey`, база KZT. Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте.

```json
{
 "type": "period_cutoff",
 "affected_ids": [
  "SF-BXQARK5D"
 ],
 "claimed_amount_minor": 394778079,
 "currency": "KZT",
 "evidence_ids": [
  "FD-FEPFXQ39",
  "JE-8BRDWBT",
  "policy"
 ],
 "explanation": "Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `FD-FEPFXQ39` — счёт SF-BXQARK5D от 2026-07-28T10:42:37+05:00, KZT 394778079, клиент CUST-C8HRBQ
* `JE-8BRDWBT` — ledger 2026-07-28T10:42:37+05:00 счёт 1200 Dr 394778079 Cr 0 inv=SF-BXQARK5D pay=null
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-08-01T00:00:00+05:00 … 2026-11-01T00:00:00+05:00
