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
| `episode/train/train-easy#101/public` | `5463d7b46b090c8b` |
| `episode/train/train-easy#101/grader` | `350f39b46bc6b600` |
| `episode/train/train-easy#102/public` | `4d2d8a5795f683cc` |
| `episode/train/train-easy#102/grader` | `832f2a5de296dc38` |
| `episode/train/train-easy#103/public` | `814563cd3c3cfae5` |
| `episode/train/train-easy#103/grader` | `5c572ccd38e524e0` |
| `episode/train/train-easy#104/public` | `554b7d341702c98e` |
| `episode/train/train-easy#104/grader` | `8a7ae5a9db5f2186` |
| `episode/train/train-easy#105/public` | `2f0b3b4904123346` |
| `episode/train/train-easy#105/grader` | `904f70883774cf42` |
| `episode/train/train-easy#106/public` | `7b166022eeabc9f1` |
| `episode/train/train-easy#106/grader` | `27cf86db1d9f63ec` |
| `episode/train/train-global#107/public` | `138e74f3ada59095` |
| `episode/train/train-global#107/grader` | `2522b0aa2c5b8e2e` |
| `episode/train/train-global#108/public` | `028c2e8c9d98a87b` |
| `episode/train/train-global#108/grader` | `3f8fab8943c5ffaa` |
| `episode/train/train-global#109/public` | `72ae11da234c0e32` |
| `episode/train/train-global#109/grader` | `26c3c22620b12e3a` |
| `episode/train/train-global#110/public` | `5456bdc3646a14e3` |
| `episode/train/train-global#110/grader` | `45300c9a4244c461` |
| `episode/dev/dev-mixed#201/public` | `c44a09b581f62f8b` |
| `episode/dev/dev-mixed#201/grader` | `a79c62118d902d0b` |
| `episode/dev/dev-mixed#202/public` | `2326b81137081b6f` |
| `episode/dev/dev-mixed#202/grader` | `4e37409bafe9b015` |
| `episode/dev/dev-mixed#203/public` | `1e0b6f46d415454b` |
| `episode/dev/dev-mixed#203/grader` | `4fe035a8d946ef3e` |
| `episode/dev/dev-global#204/public` | `e9468424dd590b3e` |
| `episode/dev/dev-global#204/grader` | `a8033b1cdcf315e0` |
| `episode/dev/dev-global#205/public` | `5b22f83aed5ddb71` |
| `episode/dev/dev-global#205/grader` | `d83474858c712521` |
| `episode/dev/interaction-heavy#206/public` | `1c542ed2f328363f` |
| `episode/dev/interaction-heavy#206/grader` | `bfb361d1644f91f9` |
| `episode/dev/interaction-heavy#207/public` | `cb4e6ddea1dfd62d` |
| `episode/dev/interaction-heavy#207/grader` | `637d79d2bf936f66` |
| `episode/dev/interaction-heavy#208/public` | `969c5e239c65141a` |
| `episode/dev/interaction-heavy#208/grader` | `74b6985be029db06` |
| `episode/dev/clean-only#209/public` | `377592e3ca77f259` |
| `episode/dev/clean-only#209/grader` | `291748a4d8bf6edb` |
| `episode/dev/clean-only#210/public` | `a01096a58adb98ea` |
| `episode/dev/clean-only#210/grader` | `213d5359c01cc900` |
| `golden/dev-mixed#22/public` | `10a9d80affd0d4bf` |
| `golden/dev-mixed#22/truth` | `2e101c4313083c19` |
| `golden/interaction-heavy#33/public` | `9b9f9bd2f0dbe9ef` |
| `golden/interaction-heavy#33/truth` | `263aebb8ebf5003e` |
| `golden/train-easy#11/public` | `0519edcb1f2dbbdb` |
| `golden/train-easy#11/truth` | `69dbe63a6fb8a2a6` |
| `config/clean-only` | `888d9b2efe8dabab` |
| `config/dev-global` | `3e5719530ff397f6` |
| `config/dev-mixed` | `58d390229a2b5ad5` |
| `config/interaction-heavy` | `11d80441ae5df73a` |
| `config/stress` | `60b0fe2dbb0fcdfe` |
| `config/train-easy` | `8946748a75222c01` |
| `config/train-global` | `54ed4c6d541dc3f9` |
| `selfcheck/deterministic` | `7b9070908ef75118` |
| `selfcheck/total` | `90.0/90` |
| `selfcheck/grader_log_head` | `123c0f370bb03583` |
