# Воспроизводимость между интерпретаторами

Сгенерировано `make repro-cross` (`tools/repro_cross.py`): сертификат `tools/repro_cert.py` пересчитан каждым
найденным Python 3.11+ при трёх разных окружениях (`PYTHONHASHSEED`, `TZ`, `LANG`) и сравнён с первым прогоном.
Сравниваются хеши, которые зависят только от генератора: 20 открытых эпизодов (public и grader), 3 golden‑эпизода
и хеши конфигов; часть self‑check берётся из одного и того же файла и здесь не сравнивается.

| Python | Интерпретатор | PYTHONHASHSEED | TZ | LANG | Хешей | Расхождений |
|---|---|---|---|---|---|---|
| 3.11.18 | `python` | 0 | UTC | C.UTF-8 | 73 | 0 |
| 3.11.18 | `python` | 12345 | Asia/Almaty | ru_RU.UTF-8 | 73 | 0 |
| 3.11.18 | `python` | random | America/Bogota | C | 73 | 0 |
| 3.12.3 | `python3.12` | 0 | UTC | C.UTF-8 | 73 | 0 |
| 3.12.3 | `python3.12` | 12345 | Asia/Almaty | ru_RU.UTF-8 | 73 | 0 |
| 3.12.3 | `python3.12` | random | America/Bogota | C | 73 | 0 |
| 3.13.18 | `python3.13` | 0 | UTC | C.UTF-8 | 73 | 0 |
| 3.13.18 | `python3.13` | 12345 | Asia/Almaty | ru_RU.UTF-8 | 73 | 0 |
| 3.13.18 | `python3.13` | random | America/Bogota | C | 73 | 0 |

**Итог: 9 из 9 прогонов побайтно совпали с эталонным.**
