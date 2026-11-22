# Слепая проверка эталона (22.11)

Проверяющий — отдельный агент без доступа к коду генератора, оценщика и к `episodes/`: только [`docs/MANUAL_AUDIT.md`](MANUAL_AUDIT.md) и CSV в `audit/`. Человеческую проверку это не заменяет, но независимо от нашего кода подтверждает эталон. Ниже — его отчёт без правок (английский).

# Blind cross-check of the answer key (audit/ folders), 22.11.2026

Scope: only `docs/MANUAL_AUDIT.md` (incl. "Уточнения после слепой проверки 22.11") and the CSVs in
`audit/1_interaction_ep-wm5bxcrh9d`, `audit/2_clean_ep-md93e84dvw`, `audit/3_fx_weekend_ep-xt9h93jnn2`.
Calculator: Python `decimal.Decimal`, ROUND_HALF_EVEN. FX business days = Mon-Fri minus `fx_holidays`
(2026-07-06, 2026-08-31, 2026-10-26); missing rate -> previous business day. Tolerance from issues.csv = 1 minor unit.

For each evidence set only that set's rows from evidence.csv were used to compute the amount. The full CSVs were
used afterwards, only to confirm that each affected_id is really wrong and to check that the evidence was enough.

## Folder 1: `1_interaction_ep-wm5bxcrh9d` (base KZT, Asia/Dubai +04:00, period 2026-07-01 .. 2026-10-01)

| issue_id | type | affected_id | set | your amount | expected_amount | match | comment |
|---|---|---|---|---|---|---|---|
| ISS-001 | fx_rate | SF-E66KPSR | 1 | 2174.62 | 2174.62 | yes | 686.000 KWD x 1435.49 (Tue 2026-08-04, invoice local date) = 984 746.14; Dr 1200 LR-92H5GYV = 986 920.76; abs diff = 2 174.62. Set enough. |
| ISS-001 | fx_rate | SF-E66KPSR | 2 | 2174.62 | 2174.62 | yes | Cr 4000 rows: 638 765.04 + 48 914.44 + 299 241.28 = 986 920.76 (the invoice has 3 lines, so these are all its 4000 rows); 986 920.76 - 984 746.14 = 2 174.62. Set enough. |
| ISS-002 | duplicate_invoice | SF-J4M89YZ | 1 | 986920.76 | 986920.76 | yes | SF-E66KPSR (08-04) and SF-J4M89YZ (08-05): same client CP-GGHBVZ, both 686.000 KWD. The later one is the duplicate. Its Dr 1200 LR-ZFTXFC7 = 986 920.76. Set enough: the "same line items" check is a total-level check in the set; the full invoices.csv confirms identical lines. |
| ISS-002 | duplicate_invoice | SF-J4M89YZ | 2 | 986920.76 | 986920.76 | yes | Cr 4000: 638 765.04 + 48 914.44 + 299 241.28 = 986 920.76. Set enough. |

Confirmation of affected_ids (full data):
* SF-E66KPSR: it was posted at 1438.66, which is the rate for Mon 2026-08-03 (the previous business day), and the policy rate is 1435.49 for Tue 08-04. It really is wrong. No payment touches this invoice.
* SF-J4M89YZ: the only invoice pair with the same entity and identical line items/service_period (2026-08), issued 1 day apart. It really is a duplicate. It was copied "as posted" (986 920.76). At its own policy rate (Wed 08-05, 1437.07) it would be 985 830.02, a 1 090.74 gap. Clarification 2 says this is not a separate fx_rate issue, so the key is consistent.
* Everything else in folder 1 reconciles exactly: 41 invoices and 21 payments posted once each; FX on weekends and holidays is correct (for example SF-MYC568S on holiday Mon 08-31 uses Fri 08-28 = 505.691); VAT lines are correct; dates are in period. I found no extra error.

## Folder 3: `3_fx_weekend_ep-xt9h93jnn2` (base KZT, Asia/Almaty +05:00, period 2026-08-01 .. 2026-11-01)

| issue_id | type | affected_id | set | your amount | expected_amount | match | comment |
|---|---|---|---|---|---|---|---|
| ISS-001 | fx_rate | BNK-TAM4YY | 1 | 7261.80 | 7261.80 | yes | Payment at 2026-10-30T21:29:12Z = local Sat 2026-10-31 02:29 -> previous business day Fri 10-30, rate 1610.87. 2 660.000 x 1610.87 = 4 284 914.20; Dr 1000 JE-75NVAYB = 4 277 652.40; diff 7 261.80. Set enough. |
| ISS-001 | fx_rate | BNK-TAM4YY | 2 | 7261.80 | 7261.80 | yes | Credits 1200 + 2400 + 7900 = 1 646 945.12 + 2 613 797.66 + 16 909.62 = 4 277 652.40 (the posted cash amount, because the group balances and there is no fee); 4 284 914.20 - 4 277 652.40 = 7 261.80. Set enough, but it relies on inferring the 1000 debit from the double-entry balance. |
| ISS-002 | payment_allocation | BNK-TAM4YY | 1 | 2613797.66 | 2613797.66 | yes | The payment refs only SF-PK6ZD2D (total 2 660.000 KWD = payment amount); the amount not applied to it = Cr 2400 JE-NN2G9PC = 2 613 797.66. Set enough for the amount by the manual rule. |

Confirmation of affected_ids (full data):
* BNK-TAM4YY fx_rate: the posted cash 4 277 652.40 / 2 660.000 = 1608.14, which is the rate for Thu 2026-10-29. The rule says the rate is from Fri 10-30 (weekend local date). It really is wrong.
* BNK-TAM4YY payment_allocation: payments.csv has no other payment referencing SF-PK6ZD2D, so its open balance was the full 2 660.000 KWD (clarification 3: not an overpayment). The whole receipt should be applied and 2400 should be 0. The posting split is:
  1037.400 KWD to 1200 at the invoice rate 1587.57 (Sun 08-30 -> Fri 08-28) = 1 646 945.12;
  1622.600 KWD to 2400 at the payment's policy rate 1610.87 = 2 613 797.66 (exactly the expected amount, as clarification 1 says).
  The "invoice-rate" alternative (422 293 620 - 164 694 512 = 2 575 991.08) differs. Clarification 1 says this is not a key error. It really is wrong.
* Everything else in folder 3 reconciles exactly. Correct look-alikes seen:
  * SF-CZTXQ4A has a -0.01 residual on 1200 (paid in 2 JPY parts; rounding twin, clarification 4).
  * Monthly "Office rent" for CL-P9P8DEK: SF-NZWC6BH, SF-E9MVMQR, SF-8N3ZNWZ have the same lines but service_period 08/09/10.
  * SF-E9MVMQR is legitimately part-paid.
  * SF-4Y8ARNR has a refund of 389 545.96, which is no more than what was paid.
  * BNK-T7K2K9 falls on the holiday 10-26 but is in KZT.
  * BNK-M4QS8X has null refs and goes to 2400 (correct).
  * SF-HB4ZYDJ at 23:50 on 10-31 local is inside the period.

## Clean folder: `2_clean_ep-md93e84dvw` (issues.csv empty; base KZT, Asia/Almaty +05:00, period 2026-07-01 .. 2026-10-01)

Full recomputation:
* Every invoice: lines sum to the total, qty x unit_price = amount, VAT, policy FX rate with weekend/holiday fallback, Dr 1200 = base, Cr 4000 split by largest remainder, local date in period.
* Every payment: chronological allocation in invoice_refs order up to the open balance; Dr 1000 at the payment rate; Cr 1200 at the invoice rate; 7900 as the difference; 2400 only for null refs or overpayment; bank fees as 6500/1000.
* Every ledger row: in period, refs exist, entity matches, each document posted exactly once (39 invoices, 30 payments).
* fx.csv: no rows on weekends or holidays, no missing business days.
* Result: 0 mismatches.

| item | why suspicious | verdict |
|---|---|---|
| INV-BZH6FX / INV-8MZ8XA (CP-XGCZ6NK, 9 026.18 EUR, same 5 lines, both service_period 2026-07, 3 days apart) | looks like a duplicate | correct look-alike: credit note INV-8RB97Q (-9 026.18 EUR, cancels_invoice_id = INV-BZH6FX) cancels the original, so INV-8MZ8XA is a reissue. The CN is posted at the same base as the original (-4 750 956.92; local Sun 07-12 -> Fri 07-10 rate 526.353). The reissue is posted at its own date's rate (Mon 07-13, 525.879) = 4 746 678.51. Correct. |
| INV-PWP5FN (CP-VF35KTB, July) / INV-AVEYBQ (CP-M67PWHP, August): identical line items and identical VAT 398 173.83 | looks like a duplicate | not a duplicate by the rule: different client and different service_period. VAT on both = 12% x 3 318 115.29 = 398 173.83, correct. |
| INV-MN77FE / INV-CPFSJ2 / INV-F8V4HH (CP-M67PWHP, 97 370.00 each, "Office rent") | same amount, same client | monthly rent, service_period 07/08/09. Correct. |
| RCV-8A8YVNJ: 408 384.00 KZT to 2400 | unapplied cash | invoice_refs = null, so the whole receipt goes to 2400 by policy. Correct. |
| INV-FWYGAV: two payments (1 705 830.78 + 3 796 849.18 = 5 502 679.96 = total) then a refund of 1 100 535.99 (Dr 4100 / Cr 1000) | 2 payments + refund | part payments sum exactly to the invoice; the refund is no more than what was paid. Correct. |
| INV-SZ5E2Y: 1200 balance -0.01 after 2 EUR payments (3 601.99 + 5 876.95 = 9 478.94 EUR) | residual on AR | rounding twin (each part converted at the invoice rate 526.073 and rounded). Within tolerance, per clarification 4. Correct. |
| RCV-TVCTFF3: one KZT payment for INV-M3GBCJ + INV-NQEX7F | one payment for 2 invoices | exact amounts 3 013 114.61 + 2 445 439.45. Correct. |
| INV-S8BSQK (USD part-paid, 2 265.23 USD open), INV-3D6WES (KZT part-paid) | open balance | legitimate partial payments, nothing in 2400. Correct. |
| Weekend FX docs: INV-QJCAN7 Sun 08-30 -> Fri 08-28 (not holiday 08-31); INV-TK2PF4, INV-YH558N, INV-SZ5E2Y, INV-9F8ZY2, INV-W33V5B, INV-FKTSYD; payments RCV-642CGNN, RCV-FWCQDT9, RCV-G688PE9 | weekend rate | all use the previous business day. Posted amounts match to the minor unit. Correct. |
| INV-26RTGC issued on holiday Mon 08-31 | holiday | KZT document, so no FX. Correct. |
| INV-M3GBCJ 2026-06-30T19:09Z = 07-01 00:09 local; RCV-7ZC6YN4 23:45 and INV-8FY4BW 23:54 local on 09-30; INV-8RB97Q 23:14 Sun | UTC/boundary traps | local dates are inside [07-01, 10-01). Correct. |
| 6 bank-fee payments (6500/1000 pair, Dr 1000 = gross receipt) | fees | consistent with policy. Correct. |
| VAT lines (INV-PWP5FN, INV-3BH968, INV-3D6WES, INV-RS746W, INV-S43VGV, INV-26RTGC, INV-AVEYBQ) | VAT | all equal round_half_even(12% x other lines). Correct. |

Real errors found in the clean folder: 0. There were also no exact .5 rounding ties in any FX conversion in all three folders, so half-even vs half-up never matters.

## Arithmetic, one item per type

* **fx_rate (folder 1, ISS-001):**
  * rate date = invoice local date 2026-08-04 (Tue, business day) -> 1435.49.
  * 686 000 minor KWD x 1435.49 x 10^(2-3) = 98 474 614.0 -> 98 474 614 minor = 984 746.14 KZT.
  * Posted Dr 1200 = 98 692 076. |98 692 076 - 98 474 614| = 217 462 minor = 2 174.62 KZT.
  * Posted/686 = 1438.66 = rate of Mon 08-03.
* **duplicate_invoice (folder 1, ISS-002):** original SF-E66KPSR 2026-08-04 12:37; duplicate SF-J4M89YZ 2026-08-05 10:24 (later). Same CP-GGHBVZ and 686.000 KWD. Duplicate's Dr 1200 = 98 692 076 minor = 986 920.76 KZT. Set 2: 63 876 504 + 4 891 444 + 29 924 128 = 98 692 076.
* **payment_allocation (folder 3, ISS-002):**
  * Cr 2400 JE-NN2G9PC = 261 379 766 minor = 2 613 797.66 KZT.
  * Cross-check: Cr 1200 164 694 512 / 1587.57 = 103 740 KZT-minor/rate -> 1 037.400 KWD applied; 2 660.000 - 1 037.400 = 1 622.600 KWD unapplied.
  * 1 622 600 x 1610.87 x 10^-1 = 261 379 766.2 -> 261 379 766. Exact match.
* **fx_rate on a weekend (folder 3, ISS-001):**
  * Local Sat 10-31 -> Fri 10-30 = 1610.87.
  * 2 660 000 x 1610.87 / 10 = 428 491 420; posted 427 765 240.
  * Diff 726 180 minor = 7 261.80 KZT (posted rate 1608.14 = Thu 10-29).

## Remaining notes (none changes a verdict)

1. Folder 1: the duplicate SF-J4M89YZ is also off its own policy rate by 1 090.74. Clarification 2 resolves this: it is not a separate fx_rate issue.
2. Folder 3 ISS-002, set 1 has no fx row and no policy row. The amount is the posted 2400 credit (manual rule), and from the set alone you can't confirm that this credit uses the payment's policy rate. With fx.csv I confirmed it does (1 622.600 x 1610.87). Ruling out overpayment needs payments.csv (clarification 3).
3. Folder 3 ISS-001, set 2 gets the posted cash amount indirectly, as the sum of the credits in a balanced group with no fee row.
4. -0.01 AR residuals (folder 2 INV-SZ5E2Y, folder 3 SF-CZTXQ4A) are rounding twins within tolerance (clarification 4).

**Verdict: 7 evidence-set recomputations, 7 matches, 0 mismatches (all 4 affected_ids confirmed really wrong); 0 real errors found in the clean folder; 0 unresolved ambiguities (4 notes above, all covered by the manual's clarifications or by the stated rules).**
