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
| `episode/train/train-easy#101/public` | `2d2005922d640975` |
| `episode/train/train-easy#101/grader` | `586192350207a997` |
| `episode/train/train-easy#102/public` | `4de29f72bb00e574` |
| `episode/train/train-easy#102/grader` | `0aa1ec15818a8a6f` |
| `episode/train/train-easy#103/public` | `1c521fc5915fb02b` |
| `episode/train/train-easy#103/grader` | `8e2ef131b0eb2449` |
| `episode/train/train-easy#104/public` | `e3e35690e8071b35` |
| `episode/train/train-easy#104/grader` | `803350d1e76357b2` |
| `episode/train/train-easy#105/public` | `5470d345e76f4010` |
| `episode/train/train-easy#105/grader` | `42344771957b3b88` |
| `episode/train/train-easy#106/public` | `858af478466b8272` |
| `episode/train/train-easy#106/grader` | `d9ff775a6145779c` |
| `episode/train/train-global#107/public` | `5804667238d6b67f` |
| `episode/train/train-global#107/grader` | `87eb9c6fbf36166c` |
| `episode/train/train-global#108/public` | `cc8c9ce25de4bed9` |
| `episode/train/train-global#108/grader` | `d1500308bada7682` |
| `episode/train/train-global#109/public` | `37e743278eefe1e4` |
| `episode/train/train-global#109/grader` | `b3e14f980dbcdc5e` |
| `episode/train/train-global#110/public` | `7f4231c2f603264e` |
| `episode/train/train-global#110/grader` | `d0c0c04586cc083a` |
| `episode/dev/dev-mixed#201/public` | `2269bd17aab31ec2` |
| `episode/dev/dev-mixed#201/grader` | `a3cdf70c19e1eb84` |
| `episode/dev/dev-mixed#202/public` | `905794ec1340197d` |
| `episode/dev/dev-mixed#202/grader` | `4e3b0923f6f7be23` |
| `episode/dev/dev-mixed#203/public` | `cc9b606d0ac15086` |
| `episode/dev/dev-mixed#203/grader` | `dc06e40fcd69066b` |
| `episode/dev/dev-global#204/public` | `4aa6c035b75f4f2a` |
| `episode/dev/dev-global#204/grader` | `f4ececd249f2aa1c` |
| `episode/dev/dev-global#205/public` | `681f82fa8313a046` |
| `episode/dev/dev-global#205/grader` | `5f15f8abcaf67963` |
| `episode/dev/interaction-heavy#206/public` | `fbba48b95d26b7ea` |
| `episode/dev/interaction-heavy#206/grader` | `db31a35de2f4d6ce` |
| `episode/dev/interaction-heavy#207/public` | `21864fbedae3df9c` |
| `episode/dev/interaction-heavy#207/grader` | `82cf6b9fb9e9c887` |
| `episode/dev/interaction-heavy#208/public` | `b6d746be3efe3998` |
| `episode/dev/interaction-heavy#208/grader` | `375df38e76e15510` |
| `episode/dev/clean-only#209/public` | `9d832f1586de4b6d` |
| `episode/dev/clean-only#209/grader` | `b23e1f37c1c2cfa2` |
| `episode/dev/clean-only#210/public` | `6fec4d34f6226ed1` |
| `episode/dev/clean-only#210/grader` | `5d039e6678f12c90` |
| `golden/dev-mixed#22/public` | `29a3823792300c75` |
| `golden/dev-mixed#22/truth` | `202444fbb0d06d8c` |
| `golden/interaction-heavy#33/public` | `6ef81fad2ee16cfe` |
| `golden/interaction-heavy#33/truth` | `7fe57d2c47d1ecc9` |
| `golden/train-easy#11/public` | `938c294522ee9abd` |
| `golden/train-easy#11/truth` | `7568485ae3a7579f` |
| `config/clean-only` | `75364dea035f003d` |
| `config/dev-global` | `6758725924324bb2` |
| `config/dev-mixed` | `5e1f417bd366cf52` |
| `config/interaction-heavy` | `0b4a5ffba66d6c72` |
| `config/stress` | `0e3fc9f073c43cfd` |
| `config/train-easy` | `d9c840b728596a92` |
| `config/train-global` | `3a25e26fa41cce5b` |
| `selfcheck/deterministic` | `89bc19e64d053496` |
| `selfcheck/total` | `90.0/90` |
| `selfcheck/grader_log_head` | `7becea591853dc6e` |
