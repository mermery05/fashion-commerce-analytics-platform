FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
EXPOSE 3000
CMD ["uv", "run", "dagster", "dev", "-h", "0.0.0.0", "-p", "3000", "-m", "orchestration.definitions"]
