# Copyright (c) 2026 Almoon-D. All rights reserved.
# The API image (MASTER_PLAN §4.9): `subphora serve`, the user and backup commands, and the
# nightly backup service. Built for x86-64 and ARM64 from the same file. It holds no
# private data and no secret: data/ is a volume, keys come from the environment.
FROM ghcr.io/astral-sh/uv:0.11.32 AS uv

FROM python:3.15-slim-trixie

# WeasyPrint's libraries for the PDF report (decision 0038): Pango and HarfBuzz's subsetter,
# and the font report.css names; mdbtools for `subphora piezometry import` (decision 0031).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core mdbtools \
 && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

# The image's own Python, the locked dependencies, nothing for development. The caches of
# fontconfig (WeasyPrint) and numba (pyflwdir) go to /tmp: the app runs as an unprivileged
# user who cannot write in /app.
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/cache \
    NUMBA_CACHE_DIR=/tmp/numba

WORKDIR /app
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY config ./config
# The Spanish catalogue the PDF report reads (decision 0038); nothing else of web/.
COPY web/src/i18n/es.json ./web/src/i18n/es.json
RUN uv sync --locked --no-dev

RUN useradd --system --uid 10001 --home-dir /app --shell /usr/sbin/nologin subphora \
 && mkdir -p /app/data /app/backups \
 && chown subphora /app/data /app/backups
USER subphora

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]
CMD ["subphora", "serve", "--host", "0.0.0.0"]
