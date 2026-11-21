# Глоссарий / Глоссарий / Glossary

Термины среды на русском, казахском и английском — с тем, где они встречаются в данных и коде. Казахские
термины подобраны по бухгалтерской лексике; если найдёте более принятый вариант — поправьте в этом файле.

| Русский | Қазақша | English | Где в AuditEnv |
|---|---|---|---|
| книга проводок, проводка | бухгалтерлік жазбалар кітабы, жазба | ledger, journal entry | `ledger.csv`, `row_id` |
| двойная запись, дебет, кредит | қос жазба, дебет, кредит | double entry, debit, credit | `debit_minor`, `credit_minor`; инвариант `double_entry` |
| счёт (документ), строка счёта | шот-фактура, шот жолы | invoice, line item | `invoices.jsonl`, `line_items` |
| счёт плана счетов | шоттар жоспарының шоты | account (chart of accounts) | `1000`, `1200`, `2400`, `4000`, `4100`, `6500`, `7900` |
| денежные средства | ақша қаражаты | cash | счёт `1000 Cash` |
| дебиторская задолженность | дебиторлық берешек | accounts receivable | счёт `1200 Accounts Receivable` |
| нераспределённые поступления | бөлінбеген түсімдер | unapplied cash | счёт `2400 Unapplied Cash` |
| выручка | түсім | revenue | счёт `4000 Revenue` |
| возврат | қайтару | refund | счёт `4100 Refunds` |
| банковская комиссия | банк комиссиясы | bank fee | счёт `6500 Bank Fees` |
| курсовая разница | бағам айырмасы | FX gain/loss | счёт `7900 FX Gain/Loss` |
| платёж, распределение платежа | төлем, төлемді бөлу | payment, payment allocation | `payments.jsonl`, `invoice_refs`; ошибка `payment_allocation` |
| кредит-нота (отмена счёта), перевыставление | кредиттік нота, қайта шығару | credit note, reissue | `cancels_invoice_id` в строках счёта |
| дубль счёта | қайталанған шот | duplicate invoice | ошибка `duplicate_invoice` |
| валютный курс, курс на дату | валюта бағамы, күнгі бағам | FX rate, rate of the date | `fx.csv`, ID `fx:DATE:SRC:TGT`; ошибка `fx_rate` |
| базовая и иностранная валюта | негізгі және шетел валютасы | base and foreign currency | `base_currency`, `currencies` в `manifest.json` |
| минимальные единицы (тиын, цент) | ең кіші бірліктер (тиын, цент) | minor units | все суммы — целые `*_minor`; экспонента валюты |
| округление «банковское» | банктік дөңгелектеу | round half to even | `ROUND_HALF_EVEN` в `policy.json` |
| рабочий день, предыдущий рабочий день | жұмыс күні, алдыңғы жұмыс күні | business day, previous business day | `fx_missing_rate: previous_business_day` |
| отчётный период, отсечение периода | есепті кезең, кезеңді бөлу | reporting period, period cut-off | `period_boundary`; ошибка `period_cutoff` |
| часовой пояс, местное время | уақыт белдеуі, жергілікті уақыт | time zone, local time | `timezone`; «UTC‑ловушка» |
| учётная политика | есеп саясаты | accounting policy | `policy.json`, запись `policy` |
| эпизод | эпизод | episode | одна компания за один период |
| эталон | эталон (дұрыс жауап) | answer key | `grader/truth.json` (агенту закрыт) |
| история мутаций | өзгерістер тарихы | provenance | `grader/provenance.json` |
| вывод (находка) | тұжырым | finding | элемент `findings` в `submit` |
| доказательства, набор доказательств | дәлелдер, дәлелдер жиыны | evidence, evidence set | `evidence_ids`, `evidence_sets` |
| отвлекающий (корректный) случай, «двойник» | алаңдататын (дұрыс) жағдай | distractor, look-alike | 14 видов в `story.py` |
| награда, шаг осмотра | сыйақы, тексеру қадамы | reward, inspection step | `clip(2·F1 − 1 − 0.002·шаги, −1, 1)` |
| точность, полнота, F1 | дәлдік, толықтық, F1 | precision, recall, F1 | `grader/reward.py` |
| ложное срабатывание, пропуск | жалған табылым, өткізіп алу | false positive, false negative | FP, FN; коды причин в журнале оценщика |
| оценщик, журнал оценщика | бағалаушы, бағалаушы журналы | grader, grader log | `auditenv/grader/`, `grader_log.jsonl` |
| соль (секрет для закрытых seed) | тұз (жабық seed құпиясы) | salt | `AUDITENV_SEED_SALT` |
