# Сертификат воспроизводимости

Машина: Python 3.11.18 (CPython), Linux x86_64.
Сгенерировано `make repro-cert` (`tools/repro_cert.py`). Хеши не зависят от времени, процессора, ОС и
версии Python: 20 открытых эпизодов пересобираются в памяти из (seed, config) и сверяются с
`episodes/*/index.json`; плюс 3 golden‑эпизода, хеши конфигов и детерминированная часть
`reports/selfcheck.json` (всё, кроме заголовка и замеров времени) после `make check`.

## Как сверить свою машину (Беке, Ералы, CI)

```text
make check                     # пересобирает reports/selfcheck.json на вашей машине
make repro-cert-check          # пересчитать и сравнить с закоммиченным сертификатом
```

Сравнить два файла (например, артефакт CI `reports/repro_certificate.json` и файл с Мака):

```text
python tools/repro_cert.py --out /tmp/mac.json            # на Маке
python tools/repro_cert.py --compare /tmp/mac.json        # здесь: таблица совпадений
```

Эпизодов, совпавших с `index.json`: **20/20**. Итог self‑check: **90.0/90**.

| Что | Хеш (первые 16 знаков) |
|---|---|
| `episode/train/train-easy#101/public` | `0830a6b0f2566620` |
| `episode/train/train-easy#101/grader` | `40d4405606a0a02e` |
| `episode/train/train-easy#102/public` | `5ae55121e0396f2f` |
| `episode/train/train-easy#102/grader` | `004dd09ae362ac60` |
| `episode/train/train-easy#103/public` | `25d6bde83b39b812` |
| `episode/train/train-easy#103/grader` | `799fa39689df5f9e` |
| `episode/train/train-easy#104/public` | `4ba99e733626af54` |
| `episode/train/train-easy#104/grader` | `c176dfd962c8d693` |
| `episode/train/train-easy#105/public` | `31e3bf9ae19fc159` |
| `episode/train/train-easy#105/grader` | `1ca5699f18546ebb` |
| `episode/train/train-easy#106/public` | `4c5bac118e05725d` |
| `episode/train/train-easy#106/grader` | `507a2ec10270b8b1` |
| `episode/train/train-global#107/public` | `1942465976e87510` |
| `episode/train/train-global#107/grader` | `60f80b5060dc149e` |
| `episode/train/train-global#108/public` | `172824170d6ce434` |
| `episode/train/train-global#108/grader` | `0032ea0eff3d7025` |
| `episode/train/train-global#109/public` | `ec84a5fa34923ad7` |
| `episode/train/train-global#109/grader` | `1a61cc74de2c3a02` |
| `episode/train/train-global#110/public` | `37938338394a440c` |
| `episode/train/train-global#110/grader` | `90c5c0593600c6ae` |
| `episode/dev/dev-mixed#201/public` | `389730ca9edd301d` |
| `episode/dev/dev-mixed#201/grader` | `e2f90eeb0e153126` |
| `episode/dev/dev-mixed#202/public` | `7271ea6b6a15ab27` |
| `episode/dev/dev-mixed#202/grader` | `8262c5045f537461` |
| `episode/dev/dev-mixed#203/public` | `db2a6dffc9343473` |
| `episode/dev/dev-mixed#203/grader` | `32027dfefd04f7c9` |
| `episode/dev/dev-global#204/public` | `d290703271912009` |
| `episode/dev/dev-global#204/grader` | `29a8140ea218aef9` |
| `episode/dev/dev-global#205/public` | `44c05ee2ae362d76` |
| `episode/dev/dev-global#205/grader` | `c65ecf8487f3d468` |
| `episode/dev/interaction-heavy#206/public` | `db2446710986d2c4` |
| `episode/dev/interaction-heavy#206/grader` | `e583e211ba2ad97e` |
| `episode/dev/interaction-heavy#207/public` | `f2fb2ae6aaa2c247` |
| `episode/dev/interaction-heavy#207/grader` | `ae321c129dccb8a8` |
| `episode/dev/interaction-heavy#208/public` | `7e9f50aaab774c20` |
| `episode/dev/interaction-heavy#208/grader` | `9c2398de8283c5c1` |
| `episode/dev/clean-only#209/public` | `1a78648e0b3615c2` |
| `episode/dev/clean-only#209/grader` | `234106ba7309f397` |
| `episode/dev/clean-only#210/public` | `04bce58fb94c9340` |
| `episode/dev/clean-only#210/grader` | `27b0e24b9b712f77` |
| `golden/dev-mixed#22/public` | `90bf7fdbcf3b940d` |
| `golden/dev-mixed#22/truth` | `73be0527438f26b0` |
| `golden/interaction-heavy#33/public` | `bf4352f101b0628b` |
| `golden/interaction-heavy#33/truth` | `c39703c1c3169978` |
| `golden/train-easy#11/public` | `3782fee1bb148447` |
| `golden/train-easy#11/truth` | `d69b15782057b5c3` |
| `config/clean-only` | `888d9b2efe8dabab` |
| `config/dev-global` | `3e5719530ff397f6` |
| `config/dev-mixed` | `58d390229a2b5ad5` |
| `config/interaction-heavy` | `11d80441ae5df73a` |
| `config/stress` | `60b0fe2dbb0fcdfe` |
| `config/train-easy` | `8946748a75222c01` |
| `config/train-global` | `54ed4c6d541dc3f9` |
| `selfcheck/deterministic` | `a76087669d90aa42` |
| `selfcheck/total` | `90.0/90` |
| `selfcheck/grader_log_head` | `a9f87c7fec92d41f` |
