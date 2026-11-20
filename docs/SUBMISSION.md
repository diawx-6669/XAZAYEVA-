# Сдача — 22 ноября 2026, 23:59 (Астана)

## Чек‑лист по разделу 09 кейса

| Что требует кейс | Где лежит | Чем проверено |
|---|---|---|
| Исходный код с лицензией и зафиксированными зависимостями: генератор и среда | `auditenv/`, `LICENSE` (MIT), `requirements.txt` (все 13 зависимостей `==`), `Dockerfile` (база по sha256) | `tests/test_guards.py::test_every_dependency_is_pinned_and_installed_as_pinned` |
| README: инструкции контейнера и единая команда проверки | `README.md` (блок критериев в начале), `make docker-check`, `make check`, `scripts/check.sh` | CI `.github/workflows/check.yml` (тот же `docker run --network none --cpus 2 --memory 4g`); локальный прогон образа: табло <!--fact:selfcheck_total-->90/90<!--/fact-->, `check: ALL GREEN` |
| Matcher и награда: общий код сопоставления и награды, схемы и политики | `auditenv/grader/` (normalize, matcher, reward), `schemas/` (15 схем), `auditenv/policies/` | `tests/test_reward.py`, `tests/test_batch_c.py::test_jury_oracles_score_max`, блок «Надёжность награды» табло |
| Эпизоды: 10 train + 10 dev | `episodes/train/`, `episodes/dev/` (+ `index.json` с дайджестами public и grader) | `tests/test_repro.py::test_exported_episodes_match_generator`, `check-schemas`, `verify-independent`, `verify-provenance` |
| Тесты среды, сопоставления и награды | `tests/` (<!--fact:n_tests-->437<!--/fact--> тестов) | `make check` |
| Четыре адаптера базовых политик | `random_explorer.py`, `simple_reconcile.py`, `flag_all.py`, `oracle.py` в `auditenv/policies/`; свой агент — `--policy-cmd` (`docs/ADAPTER.md`) | `tests/test_runner.py`, диагностика в `reports/selfcheck.md` |
| Траектории: `trajectories.jsonl` с episode_id, step, action, observation, reward, terminated, truncated, без эталона в наблюдениях | `trajectories/trajectories.jsonl` (<!--fact:traj_lines-->1195<!--/fact--> строк, `run_id` + метаданные) | `leakscan`, `replay`, `check-schemas` (схема `trajectory`), `tests/test_leaks.py::test_committed_trajectories_are_clean` |
| Записка о дизайне | `docs/DESIGN.md` (+ `docs/CONTRACT.md`, `docs/ADAPTER.md`) | ревью; `make docs-check` сверяет числа |
| Демо (достаточно скриптовой политики) | `make demo` (`scripts/demo.sh`), `make finale-preflight` | ручной прогон 22.11 (см. план) |

Дополнительно (не требуется кейсом, но жюри проверяет «корректность среды и оценщика»):
`docs/FAILURES.md` (14 закрытых уязвимостей + разбор сбоев), `docs/LIMITATIONS.md`,
`docs/MANUAL_AUDIT.md` + `audit/` (ручной аудит), `reports/exploit_search.md` (автопоиск эксплойтов).

## План на 22.11 (время Астаны)

| Время | Что | Кто | Готово, если |
|---|---|---|---|
| 10:00 | `git pull`; `make check` на чистом клоне | Ералы | `check: ALL GREEN`, табло 90/90 |
| 10:30 | `make docker-check` (нужна сеть только для сборки) | Бека | тот же итог внутри `--network none` |
| 11:00–13:00 | ручной аудит 3 эпизодов по `docs/MANUAL_AUDIT.md`, протокол в `audit/` | Ибра | все строки протокола «да» или разобраны |
| 11:00–13:00 | форма сдачи найдена, zip репозитория на Google Drive (черновик) | Алдик | ссылка на Drive открывается без входа |
| 13:00 | вычитка README/DESIGN/LIMITATIONS/FAILURES; `make docs-check` | все | `0 mismatches` |
| 14:00 | репетиция демо: `make finale-preflight`, `make demo` | Ералы, Бека | ≤ 1 минуты, без сети |
| **16:00** | **заморозка**: в `main` больше ничего не сливаем (кроме опечаток в docs) | все | — |
| 16:00–17:00 | финальный `make docker-check` на свежем клоне; сохранить вывод | Бека | `ALL GREEN` |
| 17:00 | тег и SHA: `make submission-tag`, затем `git tag -a v1.0-submission -m "Genesis Hackathon submission"` и `git push origin v1.0-submission` | Ералы | тег виден на GitHub |
| 18:00 | отправить форму: ссылка на репозиторий, тег `v1.0-submission`, SHA; скриншот подтверждения | Алдик | скриншот сохранён в Drive |
| 19:00 | офлайн‑набор для финала: `docker save auditenv > auditenv.tar`, zip репозитория, видео‑демо, PDF слайдов — на флешку | Алдик | `docker load -i auditenv.tar && make finale-preflight` на другом ноутбуке |
| до 23:59 | запас времени; ничего не менять | — | — |

Если к 16:00 какой‑то пакет не закончен, его ветку **не сливаем**: `main` всегда рабочий.
