# Итог раунда 4 (22.11, ветка `round4`)

> Ветка `round4` влита в `main` (`a1a9d66`); в опубликованном репозитории остаётся только `main`.
> «Раунд» — внутренний цикл доработки команды, не этап хакатона.

Ветка `round4` создана от `origin/main` (`b76846a`). Ядро (`auditenv/generator/`, `env/`, `grader/`, `runner.py`,
`schemas/`, `configs/`) не менялось, кроме **одного** исправления настоящего бага, найденного новым тестом
(`auditenv/env/cursors.py`, `docs/FAILURES.md` п. 18). Каждая идея — отдельный коммит, после каждой — `make quick`.

## Итог проверок

| Проверка | До раунда (`origin/main`) | После раунда 4 |
|---|---|---|
| `make check` (нативно, 4 CPU) | 1:51, ALL GREEN, 90/90 | **1:48**, ALL GREEN, 90/90, docs-check 0 mismatches |
| `make docker-check` (официальный Dockerfile, `--network none --cpus 2 --memory 4g`) | 2:35, ALL GREEN | **2:42**, ALL GREEN, 90/90, docs-check 0 mismatches |
| Тестов | 484 | <!--fact:n_tests-->705<!--/fact--> |
| Мутации оценщика (`make mutation`) | 23/23 | 23/23 |
| Симуляция жюри под Linux (`jury_sim/`) | контракт 19/20 (курсор) | 20/20; 8 солей — 8/8 (`make jury-salts`) |

Время `make check` удержано ниже 2 минут: самый медленный тест (цикл памяти, 40 с) теперь трассирует только
нужную часть циклов с той же чувствительностью к утечке, а тяжёлые проверки раунда — отдельные make‑цели.

## Найдено и исправлено в раунде

| Что | Как нашли | Исправление |
|---|---|---|
| Курсор принимался в неканонической записи base64 (замена последнего символа) | повтор симуляции жюри под Linux | канонический курсор, тест, `FAILURES.md` п. 18 |
| `.dockerignore` не пускал `reports/` в образ, а тесты и docs-check их читают | пробная сборка и запуск Docker | `.dockerignore` + тест контекста сборки |
| Тесты, вызывающие `git`, падали в образе без `.git` | пробный `docker run` | пропуск вне git‑клона |
| Параллельные закрытые прогоны под root убивают агентов друг друга | тест примеров документации | ограничение записано в `docs/LIMITATIONS.md` (ядро не меняли) |
| Устаревшее «13 зависимостей» (на деле 7 колёс) | сверка документов | факт `n_wheels` в docs-check |
| Таблицы Markdown ломались от `\|` в регулярных выражениях | генерация справочника схем | экранирование в генераторах |
| Абсолютный путь машины в HTML примеров | тест на абсолютные пути | путь относительно репозитория |

## Часть 1 (A1–A23)

| Пункт | Статус | Где смотреть |
|---|---|---|
| A1 HOTFIX | сделано | `docs/HOTFIX.md` |
| A2 исполняемые примеры документации | сделано | `tests/test_docs_examples.py`, `tests/docs_examples.json` |
| A3 справочник конфига + `validate-config` | сделано | `docs/CONFIG_REFERENCE.md`, `tests/test_round4_config.py` |
| A4 сертификат воспроизводимости | сделано | `make repro-cert`, `reports/repro_certificate.md` |
| A5 сторонние лицензии | сделано | `THIRD_PARTY_NOTICES.md` |
| A6 нет реальных данных | сделано | `make pii-scan`, `docs/SAFETY.md` |
| A7 тексты формы сдачи | сделано | `docs/SUBMISSION_FORM.md` |
| A8 prepublish | сделано | `make prepublish`, `scripts/prepublish_check.sh` |
| A9 использование ИИ | сделано | `docs/AI_USAGE.md` |
| A10 прогноз | сделано | `docs/PREDICTION.md` |
| A11 минимальный бюджет | сделано | `make min-budget`, `reports/min_budget.md` |
| A12 мощность | сделано | `make power`, `reports/power.md` |
| A13 datasheet | сделано | `docs/DATASHEET.md` |
| A14 SBOM | сделано | `reports/sbom.json`, `python -m auditenv verify-sbom` |
| A15 LLM‑инструменты + Gymnasium | сделано | `tools/llm/`, `examples/gym_wrapper.py` |
| A16 сложность по Рашу | сделано | `make difficulty`, `reports/difficulty.md` |
| A17 explain | сделано | `python -m auditenv explain`, `site/explain/` |
| A18 пул сред и бенчмарк | сделано | `make bench`, `reports/bench.md` |
| A19 карта покрытия | сделано | `make coverage-map`, `reports/coverage_map.md` |
| A20 полный перебор награды | сделано | `make exhaustive`, `reports/reward_exhaustive.md` |
| A21 верх README | сделано | `README.md` |
| A22 краткая записка о дизайне | сделано | `docs/DESIGN_SHORT.md` |
| A23 зал атак | сделано | `site/attacks.html` |

## Часть 2 (B1–B30)

Список, польза, риск и статус каждой идеи — `docs/ROUND4_IDEAS.md` (30 из 30 сделано; B15 вошла в B14).
Главное: `python -m auditenv grade` (оценить свой ответ), абляция доказательств и чувствительность к допуску и цене
шага, отпечаток контракта, `make verify-release`, `make offline-kit`, `make repro-cross` (Python 3.11/3.12/3.13 — 9/9),
памятка автору агента, FAQ, матрица раздела 10, глоссарий RU/KK/EN, повтор мутаций и симуляции жюри.
