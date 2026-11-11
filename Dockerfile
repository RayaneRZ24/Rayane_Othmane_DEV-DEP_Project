FROM ghcr.io/astral-sh/uv:0.12.1 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --system --no-create-home --uid 10001 smartops
USER smartops
EXPOSE 8000
CMD ["uvicorn", "smartops.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
