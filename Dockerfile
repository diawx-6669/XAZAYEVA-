# Base image pinned by DIGEST (python:3.11-slim, multi-arch index, resolved 2026-11-20 from Docker Hub):
# the same bytes for every build, a moved "3.11-slim" tag cannot change the result.
FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535
ENV TZ=UTC PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 LANG=C.UTF-8
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-deps -r requirements.txt && python --version && pip --version
COPY . .
RUN python -m compileall -q auditenv && chmod -R a+rX /app
# The official check runs offline: docker run --rm --network none --cpus 2 --memory 4g auditenv
CMD ["sh", "scripts/check.sh"]
