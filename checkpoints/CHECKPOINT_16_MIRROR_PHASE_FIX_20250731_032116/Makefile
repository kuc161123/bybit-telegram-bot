# Makefile for Bybit Telegram Bot

.PHONY: help install dev-install test run clean lint check-env setup

# Default target
help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make dev-install  - Install all dependencies including dev"
	@echo "  make test         - Run all tests"
	@echo "  make run          - Start the bot"
	@echo "  make clean        - Clean up generated files"
	@echo "  make lint         - Run code quality checks"
	@echo "  make check-env    - Verify environment setup"
	@echo "  make setup        - Initial project setup"

# Install production dependencies
install:
	pip install -r requirements.txt

# Install all dependencies including development
dev-install:
	pip install -r requirements.txt
	pip install black flake8 mypy

# Run tests
test:
	pytest tests/ -v

# Run specific test categories
test-unit:
	pytest tests/ -v -m unit

test-integration:
	pytest tests/ -v -m integration

# Run the bot
run:
	python main.py

# Run with auto-restart
run-prod:
	./scripts/shell/run_main.sh

# Clean up generated files
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete
	find . -type f -name "debug_*.png" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

# Run linting
lint:
	@echo "Running flake8..."
	flake8 . --exclude=venv,env,.venv,archive,backups --max-line-length=120
	@echo "Running black check..."
	black --check --exclude="/(venv|env|.venv|archive|backups)/" .

# Format code
format:
	black --exclude="/(venv|env|.venv|archive|backups)/" .

# Check environment setup
check-env:
	@echo "Checking Python version..."
	@python --version
	@echo "\nChecking required environment variables..."
	@python -c "import os; print('TELEGRAM_TOKEN:', 'Set' if os.getenv('TELEGRAM_TOKEN') else 'Not set')"
	@python -c "import os; print('BYBIT_API_KEY:', 'Set' if os.getenv('BYBIT_API_KEY') else 'Not set')"
	@python -c "import os; print('BYBIT_API_SECRET:', 'Set' if os.getenv('BYBIT_API_SECRET') else 'Not set')"
	@echo "\nChecking Bybit connection..."
	@python check_bybit_setup.py || echo "Bybit connection check failed"

# Initial setup
setup:
	@echo "Setting up Bybit Telegram Bot..."
	@echo "1. Creating virtual environment..."
	python -m venv venv
	@echo "2. Activating virtual environment..."
	@echo "   Run: source venv/bin/activate"
	@echo "3. Installing dependencies..."
	@echo "   Run: make install"
	@echo "4. Copy .env.example to .env and add your credentials"
	@echo "   Run: cp .env.example .env"
	@echo "5. Edit .env with your API keys"
	@echo "Setup complete!"

# Diagnostic commands
diag-status:
	python check_current_status.py

diag-monitors:
	python find_missing_monitors_complete.py

diag-positions:
	python check_all_mirror_positions.py

# Maintenance commands
clean-monitors:
	python clean_orphaned_monitors.py

clean-stuck:
	python cleanup_stuck_monitors.py

# Kill the bot
kill:
	./kill_bot.sh