# AuditEnv — контейнер для единой команды проверки.
#
# Сборка работает БЕЗ интернета: все пакеты лежат в vendor/wheels/.
# Сеть нужна только один раз, чтобы скачать базовый образ, если его ещё нет на машине.
#   docker build -t auditenv .
#
# Запуск проверки в условиях жюри (без сети, 2 CPU, 4 ГБ RAM):
#   docker run --rm --network none --cpus 2 --memory 4g auditenv
#
# Забрать отчёт selfcheck на свой компьютер:
#   docker run --rm --network none --cpus 2 --memory 4g \
#     -v "$(pwd)/reports:/app/reports" auditenv

FROM python:3.11-slim

# TZ=UTC и PYTHONHASHSEED=0 — одинаковые даты и hash() на любой машине (детерминизм).
# HYPOTHESIS_STORAGE_DIRECTORY — база примеров hypothesis в /tmp, потому что /app только для чтения.
ENV TZ=UTC \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HYPOTHESIS_STORAGE_DIRECTORY=/tmp/hypothesis

WORKDIR /app

# Сначала только зависимости: при правке кода Docker не ставит их заново.
# --no-index: pip не ходит в интернет, берёт пакеты только из vendor/wheels.
COPY requirements.txt .
COPY vendor/wheels vendor/wheels
RUN pip install --no-index --find-links vendor/wheels --no-deps -r requirements.txt

COPY . .
RUN python -m compileall -q auditenv

# Работаем не от root. Код, episodes/ (включая grader/ и эталоны) остаются за root
# и доступны пользователю auditor только на чтение: запись в оценщик блокирует оценивание.
# Писать можно только в папки результатов.
RUN useradd --create-home --uid 1000 auditor \
    && mkdir -p reports trajectories \
    && chown -R auditor:auditor reports trajectories
USER auditor

# The official check runs offline: docker run --rm --network none --cpus 2 --memory 4g auditenv
CMD ["sh", "scripts/check.sh"]
