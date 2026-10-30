# Release Process

## 1. Pre-Release Verification Checklist

Before tagging a release, run the complete local verification suite:

```bash
# 1. Lint & format check
uv run ruff check .
uv run ruff format --check .

# 2. Strict type check
uv run mypy src/llm_gateway_sdk

# 3. Full keyless test suite with coverage (>= 90% branch coverage required)
uv run pytest --cov=llm_gateway_sdk --cov-report=term-missing

# 4. Build wheel and sdist artifacts
uv build

# 5. Validate package metadata with Twine
uv run twine check dist/*
```

## 2. Tagging and Publishing a Release

1. Update `__version__` in `src/llm_gateway_sdk/__init__.py` and `version` in `pyproject.toml`.
2. Update `CHANGELOG.md` with the release date and summary of changes.
3. Commit and push to `main`.
4. Create and push an annotated Git tag:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```
5. The `.github/workflows/publish.yml` workflow builds the wheel and source distribution, verifies metadata, generates a GitHub Release, and optionally publishes to PyPI via Trusted Publishing (OIDC).

