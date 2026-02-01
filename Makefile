.PHONY: run update-data refresh-data init-db validate test clean export-csv api help

# Configuration
PYTHON ?= python3
STREAMLIT_PORT ?= 8501
API_PORT ?= 8000
DATABASE_PATH ?= data/benchmark.duckdb
BENCHMARK ?=
DRY_RUN ?= 0

help:
	@echo "AI Benchmark Dashboard - Available Commands"
	@echo ""
	@echo "  make run              Start Streamlit dashboard"
	@echo "  make api              Start FastAPI server"
	@echo "  make refresh-data     Refresh from official sources (recommended)"
	@echo "  make update-data      Update from all sources"
	@echo "  make update-data BENCHMARK=swe_bench_verified  Update single benchmark"
	@echo "  make refresh-data DRY_RUN=1  Dry run (no DB changes)"
	@echo "  make init-db          Initialize database with seed data"
	@echo "  make validate         Run data integrity checks"
	@echo "  make test             Run test suite"
	@echo "  make export-csv       Export database to CSV files"
	@echo "  make clean            Remove generated files"
	@echo ""

# Run the Streamlit dashboard
run:
	@echo "Starting Streamlit dashboard on port $(STREAMLIT_PORT)..."
	$(PYTHON) -m streamlit run src/dashboard/app.py \
		--server.port $(STREAMLIT_PORT) \
		--server.address 0.0.0.0

# Run the FastAPI server
api:
	@echo "Starting FastAPI server on port $(API_PORT)..."
	$(PYTHON) -m uvicorn src.api.main:app \
		--host 0.0.0.0 \
		--port $(API_PORT) \
		--reload

# Update data from sources
update-data:
	@echo "Running data update pipeline..."
ifeq ($(DRY_RUN),1)
	@echo "(Dry run mode - no database changes)"
endif
ifdef BENCHMARK
	$(PYTHON) -m scripts.update_data \
		--benchmark $(BENCHMARK) \
		$(if $(filter 1,$(DRY_RUN)),--dry-run,)
else
	$(PYTHON) -m scripts.update_data \
		$(if $(filter 1,$(DRY_RUN)),--dry-run,)
endif

# Refresh data from official sources (prioritizes official leaderboards)
refresh-data:
	@echo "Refreshing data from official sources..."
ifeq ($(DRY_RUN),1)
	@echo "(Dry run mode - no database changes)"
endif
ifdef BENCHMARK
	$(PYTHON) -m src.cli.refresh_data \
		--benchmark $(BENCHMARK) \
		$(if $(filter 1,$(DRY_RUN)),--dry-run,)
else
	$(PYTHON) -m src.cli.refresh_data \
		$(if $(filter 1,$(DRY_RUN)),--dry-run,)
endif

# Initialize database with seed data
init-db:
	@echo "Initializing database..."
	$(PYTHON) -m scripts.init_db

# Validate database integrity
validate:
	@echo "Running validation checks..."
	$(PYTHON) -m scripts.validate_db

# Run tests
test:
	@echo "Running tests..."
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing

# Export to CSV
export-csv:
	@echo "Exporting database to CSV..."
	$(PYTHON) -m scripts.export_csv --output-dir exports/

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf data/raw/*
	rm -rf exports/*
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Development setup
dev-setup:
	@echo "Setting up development environment..."
	$(PYTHON) -m pip install -e ".[dev]"
	pre-commit install

# Docker commands
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# Backup database
backup:
	@echo "Creating database backup..."
	@mkdir -p data/backups
	@cp $(DATABASE_PATH) data/backups/benchmark_$$(date +%Y%m%d_%H%M%S).duckdb
	@echo "Backup created."

# Lint and format
lint:
	$(PYTHON) -m ruff check src/ tests/ scripts/

format:
	$(PYTHON) -m ruff check --fix src/ tests/ scripts/
	$(PYTHON) -m ruff format src/ tests/ scripts/
