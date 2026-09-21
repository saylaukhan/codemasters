FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so this layer is rebuilt only when pyproject.toml changes.
# app/__init__.py is needed because the package version is read from it (dynamic version).
COPY pyproject.toml ./
COPY app/__init__.py app/
RUN pip install .

# Source tree (what .dockerignore leaves): app/, alembic/, alembic.ini, pyproject.toml.
# Reinstall only the package itself; the dependencies are already in the image.
COPY . .
RUN pip install --no-deps .

EXPOSE 8000

# One uvicorn process, and WEB_CONCURRENCY is deliberately left unset.
#
# Several processes are the obvious answer to a thousand agents sending their queues in the
# same minute (ТЗ п. 3, T-56), and uvicorn reads WEB_CONCURRENCY on its own, so it would be
# one line here. What stops it is the metrics of T-54: GET /metrics renders the registry of
# whichever process happened to answer the scrape (app/core/observability.py), and four
# processes behind one socket would show Prometheus about a quarter of the requests each,
# a different quarter every 30 seconds. A counter that falls is a reset, so every Grafana
# panel would read noise instead of load. The Celery worker solves this with
# PROMETHEUS_MULTIPROC_DIR, which the API cannot reuse as it stands: that directory is emptied
# at import (prepare_multiproc_dir), so the workers would erase each other's counters while
# starting up.
#
# Widening the API is therefore its own task — a multiprocess registry the children do not
# clean, or a separate port for the metrics, then the number of processes, then a measurement
# of both — and not a default nobody has run. What T-56 buys today is the event loop itself:
# the token check no longer holds it for tens of milliseconds (app/core/security.py). A
# deployment that needs more processes before that task is done sets WEB_CONCURRENCY in the
# environment, knowing that /metrics stops being usable until the registry is fixed.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
