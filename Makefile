.PHONY: setup download up dbt-build test lint app

setup:
	uv sync
	uv run pre-commit install

download:
	uv run python scripts/download_data.py

up:
	docker compose up --build

dbt-build:
	cd dbt_project && uv run dbt build --profiles-dir .

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

app:
	uv run streamlit run app/main.py
