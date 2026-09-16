# PowerTrace AI backend.
#
# Runs uvicorn directly rather than behind gunicorn: the polling workers and the
# WebSocket hub keep per-process state (the live value cache and trend ring
# buffers), so multiple workers would each poll the same controllers and serve
# different numbers depending on which one answered. Scale by putting a proxy
# in front of one process per site, not by adding workers to one site.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg[binary] ships wheels, so no build toolchain is needed.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Uploaded drawings live here. Mount a volume: losing them loses the link
# between the circuit model and the original the reviewer checked it against.
RUN mkdir -p /app/storage/schematics
VOLUME ["/app/storage"]

EXPOSE 8000

# Not root. The process only ever reads from the network and writes to storage.
RUN useradd --create-home --uid 10001 powertrace \
    && chown -R powertrace:powertrace /app
USER powertrace

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
