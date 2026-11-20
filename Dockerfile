# AuditEnv — контейнер для единой команды проверки.
#
# Сборка работает БЕЗ интернета: все пакеты лежат в vendor/wheels/ (только чисто-питоновские
# *-none-any.whl). Сеть нужна один раз — скачать базовый образ, если его ещё нет на машине.
#   make docker-build          (= git rev-parse > VERSION && docker build -t auditenv .)
#
# Запуск проверки в условиях жюри (без сети, 2 CPU, 4 ГБ RAM):
#   docker run --rm --network none --cpus 2 --memory 4g auditenv
#
# Забрать отчёт selfcheck на свой компьютер:
#   docker run --rm --network none --cpus 2 --memory 4g -v "$(pwd)/reports:/app/reports" auditenv

# Базовый образ закреплён по ДАЙДЖЕСТУ (python:3.11-slim, multi-arch index, Docker Hub, 2026-11-20):
# сдвинутый тег "3.11-slim" не может изменить результат сборки.
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535

# TZ=UTC и PYTHONHASHSEED=0 — одинаковые даты и hash() на любой машине (детерминизм).
# HYPOTHESIS_STORAGE_DIRECTORY — база примеров hypothesis в /tmp, потому что /app только для чтения.
ENV TZ=UTC \
    PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=C.UTF-8 \
    HYPOTHESIS_STORAGE_DIRECTORY=/tmp/hypothesis

WORKDIR /app

# Сначала только зависимости: при правке кода Docker не ставит их заново.
# --no-index: pip не ходит в интернет, берёт пакеты только из vendor/wheels.
COPY requirements.txt .
COPY vendor/wheels vendor/wheels
RUN pip install --no-index --find-links vendor/wheels --no-deps -r requirements.txt \
    && python --version && pip --version

COPY . .
# a+rX: код и данные читаемы всеми — и пользователем auditor, и песочницей агента `nobody`
# (она включается, если оценщик запущен от root: docker run --user root ...). Писать в них нельзя.
RUN python -m compileall -q auditenv && chmod -R a+rX,go-w /app

# Работаем не от root. Код, episodes/ (включая grader/ и эталоны) остаются за root и доступны
# пользователю auditor только на чтение: запись в оценщик блокирует оценивание.
# Писать можно только в папки результатов.
RUN useradd --create-home --uid 1000 auditor \
    && mkdir -p reports trajectories \
    && chown -R auditor:auditor reports trajectories
USER auditor

# The official check runs offline: docker run --rm --network none --cpus 2 --memory 4g auditenv
CMD ["sh", "scripts/check.sh"]
