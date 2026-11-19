FROM python:3.11-slim
ENV TZ=UTC PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-deps -r requirements.txt
COPY . .
RUN python -m compileall -q auditenv
# The official check runs offline: docker run --rm --network none --cpus 2 --memory 4g auditenv
CMD ["sh", "scripts/check.sh"]
