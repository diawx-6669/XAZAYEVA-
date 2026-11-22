# Сдача — 22 ноября 2026, 23:59 (Астана)

## Чек‑лист по разделу 09 кейса

| Что требует кейс | Где лежит | Чем проверено |
|---|---|---|
| Исходный код с лицензией и зафиксированными зависимостями: генератор и среда | `auditenv/`, `LICENSE` (MIT), `requirements.txt` (все <!--fact:n_wheels-->7<!--/fact--> зависимостей `==`, колёса в `vendor/wheels/`; лицензии — `THIRD_PARTY_NOTICES.md`, хеши — `reports/sbom.json`), `Dockerfile` (база по sha256) | `tests/test_guards.py::test_every_dependency_is_pinned_and_installed_as_pinned` |
| README: инструкции контейнера и единая команда проверки | `README.md` (блок критериев в начале), `make docker-check`, `make check`, `scripts/check.sh` | CI `.github/workflows/check.yml` (тот же `docker run --network none --cpus 2 --memory 4g`); локальный прогон образа: табло <!--fact:selfcheck_total-->90/90<!--/fact-->, `check: ALL GREEN` |
| Matcher и награда: общий код сопоставления и награды, схемы и политики | `auditenv/grader/` (normalize, matcher, reward), `schemas/` (15 схем), `auditenv/policies/` | `tests/test_reward.py`, `tests/test_batch_c.py::test_jury_oracles_score_max`, блок «Надёжность награды» табло |
| Эпизоды: 10 train + 10 dev | `episodes/train/`, `episodes/dev/` (+ `index.json` с дайджестами public и grader) | `tests/test_repro.py::test_exported_episodes_match_generator`, `check-schemas`, `verify-independent`, `verify-provenance` |
| Тесты среды, сопоставления и награды | `tests/` (<!--fact:n_tests-->661<!--/fact--> тестов) | `make check` |
| Четыре адаптера базовых политик | `random_explorer.py`, `simple_reconcile.py`, `flag_all.py`, `oracle.py` в `auditenv/policies/`; свой агент — `--policy-cmd` (`docs/ADAPTER.md`) | `tests/test_runner.py`, диагностика в `reports/selfcheck.md` |
| Траектории: `trajectories.jsonl` с episode_id, step, action, observation, reward, terminated, truncated, без эталона в наблюдениях | `trajectories/trajectories.jsonl` (<!--fact:traj_lines-->1195<!--/fact--> строк, `run_id` + метаданные) | `leakscan`, `replay`, `check-schemas` (схема `trajectory`), `tests/test_leaks.py::test_committed_trajectories_are_clean` |
| Записка о дизайне | `docs/DESIGN.md` (+ `docs/CONTRACT.md`, `docs/ADAPTER.md`) | ревью; `make docs-check` сверяет числа |
| Демо (достаточно скриптовой политики) | `make demo` (`scripts/demo.sh`), `make finale-preflight` | ручной прогон 22.11 (см. план) |

Дополнительно (не требуется кейсом, но жюри проверяет «корректность среды и оценщика»):
`docs/FAILURES.md` (<!--fact:failures_closed-->18<!--/fact--> закрытых уязвимостей + разбор сбоев), `docs/LIMITATIONS.md`,
`docs/MANUAL_AUDIT.md` + `audit/` (ручной аудит), `reports/exploit_search.md` (автопоиск эксплойтов).

## Проверка 22.11 утром — что уже проверено и что осталось руками

Дедлайн: 23:59 Астаны = **18:59 UTC**. Внутренний дедлайн: 22:00 Астаны = 17:00 UTC.

| Риск | Статус | Как проверено / что сделать |
|---|---|---|
| Основная ветка на GitHub = `main` | **руками** | сейчас основная — `claude/inspiring-tesla-8qyaxh`. Settings → General → Default branch → `main`. Без этого бейдж CI показывает не ту ветку |
| Старые ветки | **руками, после смены основной** | все ветки, кроме `main`, уже целиком в `main` (`git cherry` — 0 непринятых правок; сайт из `claude/funny-lovelace-7alc4p` перенесён и доработан). Команда ниже |
| `make check` на свежем `main` | готово | ALL GREEN, 1 мин 49 с; `make verify-release` 7/7 |
| Docker на финальном коммите | готово | CI `docker-check` зелёный: сборка и `--network none --cpus 2 --memory 4g` |
| `make venv` без сети | исправлено | раньше ставил пакеты из PyPI, хотя README обещает «без сети»; теперь `--no-index --find-links vendor/wheels --no-deps`, как в Dockerfile; тест `tests/test_guards.py` |
| Секреты в истории | готово | `make prepublish`: 0 находок |
| Личная почта в коммитах | **решить** | в 5 коммитах — личный e‑mail участника; после открытия репозитория он станет виден. Историю **не переписывать** (меняются все SHA, ломаются заголовок self‑check, сертификат и цепочка журнала) — только согласовать с участником |
| Подсказки в данных | найдено и описано | `reports/shortcut_probe.md`: одна слабая подсказка (секунды `00`), исправление — `docs/ROADMAP.md` R0 |

Удалить старые ветки (после смены основной ветки):

```bash
git push origin --delete claude/inspiring-tesla-8qyaxh claude/funny-lovelace-7alc4p beka beka-jury beka-ps-leak round3 round4
```

Тег (после последнего коммита и зелёного CI на нём):

```bash
make verify-release && git tag -a v1.0-submission -m "Genesis Hackathon submission" && git push origin v1.0-submission
```

В форму — ссылку на тег, а не на репозиторий: `https://github.com/diawx-6669/XAZAYEVA-/tree/v1.0-submission` и полный SHA
(`git rev-parse v1.0-submission^{commit}`).

Проверка из инкогнито после открытия (20:00 Астаны = 15:00 UTC), с телефона на мобильном интернете:
README отрисовался; бейдж CI зелёный; ссылка на тег открывается; `git clone` без входа; видео
(YouTube «доступ по ссылке») играет без входа; Google Drive «доступ всем, у кого есть ссылка»;
обложка репозитория (Settings → Social preview, `site/brand/social-preview.png`) видна в превью ссылки.

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
| 19:00 | офлайн‑набор для финала: `make offline-kit` (zip репозитория по тегу, образ `docker save`, SHA256SUMS в `dist/`), видео‑демо, PDF слайдов — на флешку | Алдик | на другом ноутбуке без сети: команды, которые печатает `make offline-kit` (`sha256sum -c`, `docker load`, `make finale-preflight`) |
| до 23:59 | запас времени; ничего не менять | — | — |

Если к 16:00 какой‑то пакет не закончен, его ветку **не сливаем**: `main` всегда рабочий.
