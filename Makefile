.PHONY: test build publish release clean dev lint help

PYPIRC := $(HOME)/.pypirc
VERSION := $(shell grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

test: ## Run all tests
	uv run pytest tests/ -v

build: clean ## Build sdist and wheel
	uv build

publish: build ## Build and publish to PyPI
	@test -f $(PYPIRC) || (echo "Error: $(PYPIRC) not found" && exit 1)
	UV_PUBLISH_TOKEN=$$(grep -A2 '\[pypi\]' $(PYPIRC) | grep password | cut -d'=' -f2 | tr -d ' ') \
		uv publish

release: ## Tag, build, and publish (usage: make release VERSION=1.2.0)
ifndef VERSION
	$(error VERSION is required. Usage: make release VERSION=1.2.0)
endif
	@echo "Releasing v$(VERSION)..."
	sed -i 's/^version = ".*"/version = "$(VERSION)"/' pyproject.toml
	git add pyproject.toml
	git commit -m "chore: Bump version to $(VERSION)"
	git tag -a v$(VERSION) -m "Release $(VERSION)"
	git push origin main --tags
	$(MAKE) publish
	@echo "Published texflow-mcp $(VERSION) to PyPI"

clean: ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info texflow_mcp.egg-info texflow/*.egg-info

dev: ## Start MCP server locally
	uv run texflow

lint: ## Run linter
	uv run ruff check .
