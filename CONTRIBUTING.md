# Contributing

Bug reports and small patches are welcome. Open an issue first for larger changes.

## Setup

```bash
python3 -m pip install -e ".[dev]"
ruff check skilldiff tests examples fixtures
mypy
pytest -v
skilldiff demo
```

Python 3.10+. Do not commit `.env` or `.agent_diff/`.

## What to test

- Lint: `ruff check` and `mypy` on `skilldiff`.
- Offline: `pytest -v` (no API key). Includes [`fixtures/demo-repo/`](fixtures/demo-repo/).
- CLI smoke: `skilldiff demo` exits 0 and writes JSON.
- Live Gemini/Ollama runs are optional and belong in a PR comment, not required CI.

## Pull requests

- Keep the diff focused. One concern per PR.
- Match existing code style (type hints, Pydantic v2, no extra dependencies unless justified).
- Update README examples if you change CLI flags.

## Release (maintainers)

1. Bump `version` in `pyproject.toml` and `skilldiff/__init__.py`.
2. Update [CHANGELOG.md](CHANGELOG.md).
3. Tag `vX.Y.Z` and push the tag. [`.github/workflows/publish.yml`](.github/workflows/publish.yml) builds and uploads to PyPI.

**One-time PyPI Trusted Publisher:** on [pypi.org](https://pypi.org) create project `skilldiff` (or register the publisher before the first file exists), publisher GitHub, repo `shunvel/skilldiff`, workflow `publish.yml`, environment `pypi`. In GitHub, add environment `pypi` (no secrets — OIDC).
