# Contributing

```bash
uv venv && uv pip install -e '.[all,dev]'     # or: python -m venv .venv && pip install -e '.[all,dev]'
pytest -q && ruff check src tests && ruff format --check src tests && mypy src
```

Good first contributions:

- **A new scanner format**: add a parser in `src/openfix/ingest.py`, register it in `detect()`, and add a sample to
  `tests/test_ingest.py`.
- **A new provider**: see [docs/providers.md](docs/providers.md#adding-a-provider).
- **A scanner preset** for rescans in `src/openfix/scanners.py`.
- **A deterministic fixer** for another ecosystem in `src/openfix/deps.py`.

Keep the separation that makes OpenFix trustworthy: models propose, code verifies. A change that lets model output
affect a verification result, or widens what the agent's tools can touch, needs a test that shows the boundary still
holds.
