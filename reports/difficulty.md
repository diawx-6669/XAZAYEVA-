# Сложность вариантов ошибок (модель Раша)

Сгенерировано `make difficulty` (`tools/rasch.py`): 300 свежих эпизодов (6 открытых конфигов, seed 660000+),
панель из 10 вариантов `simple_reconcile` с выключаемыми правилами, ответ = «этот issue получил TP».
Модель: P(решил) = σ(θ_политики − b_варианта); штрафованное совместное ML (Ньютон, априорное N(0, 3²)),
среднее b = 0. Интервал — b ± 1.96 / √информации. Чем **больше b, тем труднее** вариант для панели.

Оговорка: панель — 10 близких скриптовых политик, а не люди и не LLM; модель одномерная, а правила
многомерны (выключенное правило обнуляет целый тип). Шкала показывает, какие варианты требуют **больше
правил и аккуратности** для этой панели, а не «абсолютную» трудность для агентов вообще.

## Шкала сложности

| Вариант | n (issue) | Решено официальной базой | b | 95 % интервал | Шкала |
|---|---|---|---|---|---|
| payment_allocation / wrong_invoice | 3 | 0/3 | +7.69 | [+5.58; +9.79] | `                   ─────●─────` |
| fx_rate / historical_rate | 10 | 2/10 | +1.28 | [+0.75; +1.81] | `       ─●──                   ` |
| fx_rate / wrong_pair | 19 | 10/19 | +0.18 | [-0.19; +0.54] | `     ─●─                      ` |
| fx_rate / due_date | 5 | 3/5 | -0.06 | [-0.78; +0.65] | `    ─●──                      ` |
| fx_rate / adjacent_day | 131 | 91/131 | -0.36 | [-0.50; -0.22] | `    ─●                        ` |
| fx_rate / inverted | 13 | 10/13 | -0.66 | [-1.14; -0.19] | `   ─●─                        ` |
| period_cutoff / backdated_posting | 9 | 9/9 | -0.78 | [-1.36; -0.20] | `  ──●─                        ` |
| duplicate_invoice / paid_twice | 15 | 15/15 | -0.79 | [-1.24; -0.33] | `  ──●─                        ` |
| period_cutoff / utc_trap | 27 | 27/27 | -0.79 | [-1.12; -0.45] | `   ─●                         ` |
| payment_allocation / unallocated | 38 | 38/38 | -0.79 | [-1.07; -0.50] | `   ●─                         ` |
| duplicate_invoice / copy_as_posted | 53 | 53/53 | -0.79 | [-1.03; -0.55] | `   ●─                         ` |
| duplicate_invoice / copy | 65 | 65/65 | -0.79 | [-1.01; -0.57] | `   ●─                         ` |
| period_cutoff / prior_period | 66 | 66/66 | -0.79 | [-1.00; -0.57] | `   ●─                         ` |
| payment_allocation / partial | 85 | 85/85 | -0.79 | [-0.98; -0.60] | `   ●─                         ` |
| fx_rate / utc_date | 21 | 21/21 | -1.76 | [-2.24; -1.28] | `─●─                           ` |

## Способность политик панели (θ)

| Политика | Правила | θ | Решено всего |
|---|---|---|---|
| full (all rules) | alloc, credit_note_aware, cutoff, dup, fx, fx_prev_business_day, overpayment_aware, skip_dup_in_fx | +5.77 | 557/560 |
| baseline + prev_business_day | alloc, cutoff, dup, fx, fx_prev_business_day | +5.77 | 557/560 |
| full - credit_note_aware | alloc, cutoff, dup, fx, fx_prev_business_day, overpayment_aware, skip_dup_in_fx | +3.91 | 551/560 |
| official baseline | alloc, cutoff, dup, fx | +1.50 | 495/560 |
| full - prev_business_day | alloc, credit_note_aware, cutoff, dup, fx, overpayment_aware, skip_dup_in_fx | +1.50 | 495/560 |
| baseline - cutoff | alloc, dup, fx | +0.26 | 393/560 |
| baseline - alloc | cutoff, dup, fx | +0.08 | 372/560 |
| baseline - dup | alloc, cutoff, fx | -0.01 | 362/560 |
| baseline - fx | alloc, cutoff, dup | -0.04 | 358/560 |
| fx specialist | fx, fx_prev_business_day | -1.25 | 199/560 |

## Как читать

* Варианты внизу шкалы решает почти любая политика, у которой включено правило своего типа.
* Вверху — варианты, которые требуют дополнительных правил (`previous_business_day` для выходных курсов,
  учёт credit note и переплаты) или которые простые правила вообще не видят (`wrong_invoice`).
* Широкий интервал — мало примеров варианта (см. столбец n): вариант редкий в открытых конфигах.
