.PHONY: help install test lint format clean deploy-dev deploy-staging deploy-prod destroy-dev package

# Default target
help:
	@echo "Available commands:"
	@echo "  install       - Install Python dependencies"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  test-performance - Run performance tests only"
	@echo "  lint          - Run code linting"
	@echo "  format        - Format code with black"
	@echo "  type-check    - Run type checking with mypy"
	@echo "  package       - Package Lambda functions for deployment"
	@echo "  deploy-dev    - Deploy to development environment"
	@echo "  deploy-staging - Deploy to staging environment"
	@echo "  deploy-prod   - Deploy to production environment"
	@echo "  destroy-dev   - Destroy development infrastructure"
	@echo "  clean         - Clean up temporary files"

# Python environment setup
install:
	pip install -r requirements.txt

# Testing
test: test-unit test-integration
	@echo "All tests completed"

test-unit:
	pytest tests/unit/ -v --cov=src --cov-report=html

test-integration:
	pytest tests/integration/ -v

test-performance:
	pytest tests/performance/ -v

# Code quality
lint:
	flake8 src/ tests/
	@echo "Linting completed"

format:
	black src/ tests/ scripts/
	@echo "Code formatting completed"

type-check:
	mypy src/

# Packaging
package:
	@echo "Packaging Lambda functions..."
	./scripts/deployment/package_lambdas.sh

# Terraform operations
plan-dev:
	cd terraform/environments/dev && terraform plan

deploy-dev: package
	@echo "Deploying to development environment..."
	cd terraform/environments/dev && terraform init && terraform apply -auto-approve

plan-staging:
	cd terraform/environments/staging && terraform plan

deploy-staging: package
	@echo "Deploying to staging environment..."
	cd terraform/environments/staging && terraform init && terraform apply -auto-approve

plan-prod:
	cd terraform/environments/prod && terraform plan

deploy-prod: package
	@echo "Deploying to production environment..."
	cd terraform/environments/prod && terraform init && terraform apply

destroy-dev:
	@echo "Destroying development infrastructure..."
	cd terraform/environments/dev && terraform destroy -auto-approve

# Maintenance
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -name ".coverage" -delete
	rm -rf dist/ build/ *.egg-info/
	@echo "Cleanup completed"

# Data operations
sample-data:
	python scripts/analysis/generate_sample_data.py

validate-data:
	python scripts/analysis/validate_data.py

# Development helpers
dev-setup: install
	@echo "Setting up development environment..."
	pre-commit install || echo "pre-commit not available, skipping hook installation"

local-test:
	@echo "Running local tests with Docker..."
	docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit