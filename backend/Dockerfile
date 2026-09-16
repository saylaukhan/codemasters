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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
