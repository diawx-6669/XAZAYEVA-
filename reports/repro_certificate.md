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
| `episode/train/train-easy#101/public` | `2372433dab1ad11f` |
| `episode/train/train-easy#101/grader` | `715db3c85dee2c03` |
| `episode/train/train-easy#102/public` | `12346af13532903c` |
| `episode/train/train-easy#102/grader` | `de7fdd954cccf6de` |
| `episode/train/train-easy#103/public` | `76856a03ffc589c0` |
| `episode/train/train-easy#103/grader` | `1bf662a71a19f24e` |
| `episode/train/train-easy#104/public` | `7079ad49ca7d1a43` |
| `episode/train/train-easy#104/grader` | `0590544faf2886c3` |
| `episode/train/train-easy#105/public` | `238823877648f638` |
| `episode/train/train-easy#105/grader` | `0a5efa70e0da7546` |
| `episode/train/train-easy#106/public` | `30ace29c58d65a5c` |
| `episode/train/train-easy#106/grader` | `09950bedc93ba310` |
| `episode/train/train-global#107/public` | `41b4dddd70d176e6` |
| `episode/train/train-global#107/grader` | `983c5d251876633a` |
| `episode/train/train-global#108/public` | `cc290baac0d76b92` |
| `episode/train/train-global#108/grader` | `3f76bdcf117202fc` |
| `episode/train/train-global#109/public` | `2d887d3d4d9a2b27` |
| `episode/train/train-global#109/grader` | `3ac9763e8f1981f5` |
| `episode/train/train-global#110/public` | `594a60999e498501` |
| `episode/train/train-global#110/grader` | `eb0b874878f40ab0` |
| `episode/dev/dev-mixed#201/public` | `be2369f17eb605c4` |
| `episode/dev/dev-mixed#201/grader` | `6caf632f366a4938` |
| `episode/dev/dev-mixed#202/public` | `aaa528bfaffb1d9e` |
| `episode/dev/dev-mixed#202/grader` | `e53920de8713d9b3` |
| `episode/dev/dev-mixed#203/public` | `eeca5972a1bbe672` |
| `episode/dev/dev-mixed#203/grader` | `33c3c327efabf374` |
| `episode/dev/dev-global#204/public` | `53011d5c92d4d871` |
| `episode/dev/dev-global#204/grader` | `4c48feb1ba7528a9` |
| `episode/dev/dev-global#205/public` | `9c37d5b67093b3a3` |
| `episode/dev/dev-global#205/grader` | `bb81d31bc862996d` |
| `episode/dev/interaction-heavy#206/public` | `b2852fd0d9ffccdf` |
| `episode/dev/interaction-heavy#206/grader` | `54f43dbdd3d16626` |
| `episode/dev/interaction-heavy#207/public` | `e828cb7a22d12283` |
| `episode/dev/interaction-heavy#207/grader` | `43b64268eceba390` |
| `episode/dev/interaction-heavy#208/public` | `5d2a63355f6bae47` |
| `episode/dev/interaction-heavy#208/grader` | `1f94178ff8601d69` |
| `episode/dev/clean-only#209/public` | `e88cd2c79c47005c` |
| `episode/dev/clean-only#209/grader` | `c3dd32bf163ce820` |
| `episode/dev/clean-only#210/public` | `a87e7346dd63e77a` |
| `episode/dev/clean-only#210/grader` | `941e4292205affd9` |
| `golden/dev-mixed#22/public` | `b98d9a747b248cb3` |
| `golden/dev-mixed#22/truth` | `6b1a930d769b23f5` |
| `golden/interaction-heavy#33/public` | `b2769602b5391daa` |
| `golden/interaction-heavy#33/truth` | `2cab7ad70f1c5b57` |
| `golden/train-easy#11/public` | `eae826feb4ac00c9` |
| `golden/train-easy#11/truth` | `2a81a21b8aec9095` |
| `config/clean-only` | `75364dea035f003d` |
| `config/dev-global` | `6758725924324bb2` |
| `config/dev-mixed` | `5e1f417bd366cf52` |
| `config/interaction-heavy` | `0b4a5ffba66d6c72` |
| `config/stress` | `0e3fc9f073c43cfd` |
| `config/train-easy` | `d9c840b728596a92` |
| `config/train-global` | `3a25e26fa41cce5b` |
| `selfcheck/deterministic` | `da3ef1b2ebe0d6f1` |
| `selfcheck/total` | `90.0/90` |
| `selfcheck/grader_log_head` | `4c522f15d41095ec` |
