# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-17

### Added

- `skilldiff run` for baseline vs. variant agent A/B tests.
- `skilldiff demo` zero-config mock run (no API key).
- Gemini and Ollama backends, LLM-as-a-Judge with short-circuit, score-parity, and swap-order guards.
- Rich table + `.agent_diff/results_<timestamp>.json` reporter.
- CI flags `--exit-on-loss` and `--min-win-rate`.
- Example tool scripts, root sanity `tasks.json`, and `fixtures/demo-repo/` (sanity + eval).
- pytest suite, ruff/mypy, and GitHub Actions on Python 3.10–3.13.
- PyPI Trusted Publishing workflow on `v*` tags; Dependabot for pip and Actions.
