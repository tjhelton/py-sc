# Makefile for rcscripts Python linting and development

.PHONY: help install lint fix check-deps clean test

# Default target
help:
	@echo "Available commands for rcscripts development:"
	@echo ""
	@echo "  make install     - Install development dependencies"
	@echo "  make lint        - Run all linters (check mode)"
	@echo "  make fix         - Run linters and apply automatic fixes"
	@echo "  make check-deps  - Check if linting tools are installed"
	@echo "  make clean       - Clean up temporary files"
	@echo "  make pre-commit  - Install pre-commit hooks"
	@echo ""
	@echo "Quick start:"
	@echo "  1. make install"
	@echo "  2. make pre-commit"
	@echo "  3. make lint"

# Install development dependencies
install:
	@echo "Installing development dependencies..."
	pip install -r requirements-dev.txt

# Run linters in check mode
lint:
	@echo "Running linters on current directory..."
	python3 lint-and-fix.py

# Run linters and apply fixes
fix:
	@echo "Running linters with auto-fix on current directory..."
	python3 lint-and-fix.py --fix

# Check if dependencies are installed
check-deps:
	@echo "Checking linting dependencies..."
	python3 lint-and-fix.py --check-deps

# Install pre-commit hooks
pre-commit:
	@echo "Installing pre-commit hooks..."
	pre-commit install --config .pre-commit-config.yaml
	@echo "Pre-commit hooks installed! They will run automatically on git commits."

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find .. -type f -name "*.pyc" -delete
	find .. -type d -name "__pycache__" -delete
	find .. -type d -name "*.egg-info" -exec rm -rf {} +
	find .. -name ".mypy_cache" -type d -exec rm -rf {} +

# Script files only (preserves functionality)
SCRIPT_FILES = ../scripts/actions/*/*.py ../scripts/assets/*/*.py ../scripts/courses/*/*.py ../scripts/groups/*/*.py ../scripts/inspections/*/*.py ../scripts/issues/*/*.py ../scripts/nuke_account/*.py ../scripts/organizations/*/*.py ../scripts/sites/*/*.py ../scripts/templates/*/*.py ../scripts/users/*/*.py

# Run individual linters
black-check:
	black --check --diff --skip-string-normalization $(SCRIPT_FILES)

black-fix:
	black --skip-string-normalization $(SCRIPT_FILES)

isort-check:
	isort --check-only --diff $(SCRIPT_FILES)

isort-fix:
	isort $(SCRIPT_FILES)

flake8:
	flake8 --config .flake8 $(SCRIPT_FILES)

# mypy temporarily disabled due to duplicate main.py module conflicts
# mypy:
# 	mypy $(SCRIPT_FILES)
