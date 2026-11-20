# Журнал версий конфигураций

Правило: любое изменение, которое может изменить сгенерированные эпизоды (сам файл конфига **или**
значение по умолчанию в `auditenv/config.py::DEFAULT_CONFIG`), требует поднять `version` в каждом
затронутом конфиге, обновить `configs/LOCK.json` (`python -m auditenv lock-configs`) и записать
строку сюда. Тест `tests/test_configs_lock.py` падает, если содержимое изменилось, а версия — нет.
В `manifest.json` каждого эпизода есть `config_version` и `config_hash`.

| Версия | Конфиги | Что изменилось |
|---|---|---|
| 2.0 | все | Раунд 2: новые варианты ошибок (`paid_twice`, `wrong_invoice`, `historical_rate`, `wrong_pair`, `due_date`, `backdated_posting`, `prior_period`), отвлекалки `night_fx` / `weekend_fx` / `overpayment`, `min_lookalikes_per_type = 1`, пояса Asia/Kathmandu, Pacific/Kiritimati, Pacific/Pago_Pago (в `dev-mixed`, `interaction-heavy`), `period_months` может быть диапазоном. В `train-easy` новые варианты выключены. |
| 2.0 | `train-global`, `dev-global` (новые) | База USD/JPY/KWD, старт в ноябре (через Новый год), декабре и феврале, периоды 1–3 месяца, экстремальные пояса. |
| 1.0 | `train-easy`, `dev-mixed`, `clean-only`, `interaction-heavy`, `stress` | Раунд 1: исходные конфиги. |
