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
  "BL-MY6YV7"
 ],
 "claimed_amount_minor": 121529806,
 "currency": "KZT",
 "evidence_ids": [
  "DC-YJFAMY",
  "DC-6Q6Y5K",
  "LR-E3A9K3"
 ],
 "explanation": "Тот же клиент и те же строки, что у более раннего счёта; оба проведены. ID — более поздний счёт, сумма — его Dr 1200."
}
```

Доказательства (что вернёт инструмент):

* `DC-YJFAMY` — счёт BL-VD7V47 от 2026-10-19T11:15:16+00:00, KZT 121529806, клиент CL-4EEAKW
* `DC-6Q6Y5K` — счёт BL-MY6YV7 от 2026-10-20T08:46:07+00:00, KZT 121529806, клиент CL-4EEAKW
* `LR-E3A9K3` — ledger 2026-10-20T08:46:07+00:00 счёт 1200 Dr 121529806 Cr 0 inv=BL-MY6YV7 pay=null
* (есть ещё 1 альтернативный набор — подойдёт любой целиком)

## `payment_allocation` (вариант `unallocated`)

Эпизод `episodes/train/ep-kcj4hkgrcj`, база KZT. Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400.

```json
{
 "type": "payment_allocation",
 "affected_ids": [
  "BNK-VJDJKS"
 ],
 "claimed_amount_minor": 465303494,
 "currency": "KZT",
 "evidence_ids": [
  "DOC-XZY7FG9",
  "DOC-2NCRBTT",
  "GL-T4J54V"
 ],
 "explanation": "Платёж ссылается на счёт, но часть (или всё) легла на 2400 Unapplied Cash вместо 1200. Сумма — то, что на 2400."
}
```

Доказательства (что вернёт инструмент):

* `DOC-XZY7FG9` — платёж BNK-VJDJKS от 2026-09-04T11:06:04+05:00, KZT 465303494, ссылки ['SF-VXZSSDNX']
* `DOC-2NCRBTT` — счёт SF-VXZSSDNX от 2026-08-27T14:06:28+05:00, KZT 465303494, клиент CP-457DFMFN
* `GL-T4J54V` — ledger 2026-09-04T11:06:04+05:00 счёт 2400 Dr 0 Cr 465303494 inv=null pay=BNK-VJDJKS

## `fx_rate` (вариант `utc_date`)

Эпизод `episodes/train/ep-ak4s2vjfjr`, база USD. Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте.

```json
{
 "type": "fx_rate",
 "affected_ids": [
  "RCV-Y86TXF"
 ],
 "claimed_amount_minor": 744,
 "currency": "USD",
 "evidence_ids": [
  "DOC-SJ49FX",
  "LR-5V3VAYX",
  "fx:2026-03-12:KZT:USD",
  "policy"
 ],
 "explanation": "Документ в иностранной валюте проведён по курсу не той даты (или перевёрнутому). Сумма — |проведено − правильно| в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `DOC-SJ49FX` — платёж RCV-Y86TXF от 2026-03-13T05:21:57+00:00, KZT 139143930, ссылки ['SF-GBMYSAC']
* `LR-5V3VAYX` — ledger 2026-03-13T05:21:57+00:00 счёт 1000 Dr 285252 Cr 0 inv=null pay=RCV-Y86TXF
* `fx:2026-03-12:KZT:USD` — fx 2026-03-12 KZT→USD = 0.00205540
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-02-01T00:00:00-11:00 … 2026-05-01T00:00:00-11:00
* (есть ещё 1 альтернативный набор — подойдёт любой целиком)

## `period_cutoff` (вариант `utc_trap`)

Эпизод `episodes/train/ep-6sbtnqcp2q`, база KZT. Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте.

```json
{
 "type": "period_cutoff",
 "affected_ids": [
  "INV-WQ6MYJG"
 ],
 "claimed_amount_minor": 637887689,
 "currency": "KZT",
 "evidence_ids": [
  "FD-JKH43TF3",
  "LR-DEBXQDW",
  "policy"
 ],
 "explanation": "Счёт выписан вне периода по местному времени компании, а проведён внутри. Сумма — сумма счёта в базовой валюте."
}
```

Доказательства (что вернёт инструмент):

* `FD-JKH43TF3` — счёт INV-WQ6MYJG от 2026-10-31T19:54:01+00:00, KZT 637887689, клиент CUST-P2KN4Z
* `LR-DEBXQDW` — ledger 2026-10-31T19:54:01+00:00 счёт 1200 Dr 637887689 Cr 0 inv=INV-WQ6MYJG pay=null
* `policy` — policy: курс — transaction_date, нет курса — previous_business_day, период 2026-08-01T00:00:00+05:00 … 2026-11-01T00:00:00+05:00
