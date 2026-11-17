ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    READING_BENCH_HOST=0.0.0.0 \
    READING_BENCH_PORT=8787 \
    READING_BENCH_DATA_DIR=/app/var

WORKDIR /app
RUN groupadd --gid 10001 readingbench && useradd --uid 10001 --gid 10001 --no-create-home readingbench \
    && mkdir -p /app/var /app/docs && chown 10001:10001 /app/var
COPY backend ./backend
COPY frontend ./frontend
COPY data ./data
COPY docs/metrics-and-methodology.md ./docs/metrics-and-methodology.md
USER 10001:10001
VOLUME ["/app/var"]
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=3).read()"
CMD ["python", "-m", "backend.server"]
