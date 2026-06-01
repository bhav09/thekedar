# Contributing to Thekedar

Thank you for contributing. This project uses a monorepo with `uv` workspaces.

## Development setup

```bash
git clone https://github.com/bhav66d/thekedar.git
cd thekedar
uv sync --all-packages --dev
./scripts/bootstrap.sh --demo
```

## Running tests

```bash
uv run pytest tests -q
uv run ruff check packages tests
uv run bandit -r packages -ll
```

## Pull request checklist

- [ ] Tests pass locally (`make test`)
- [ ] Ruff clean (`make lint`)
- [ ] No secrets or credentials in the diff
- [ ] Dashboard/API changes include auth + tenant scoping where applicable
- [ ] Documentation updated if behavior or env vars changed

## Code style

- Python 3.12+, line length 100 (Ruff)
- Match existing package layout under `packages/`
- Prefer minimal, focused diffs

## Getting help

Open a [bug report](.github/ISSUE_TEMPLATE/bug_report.md) or [feature request](.github/ISSUE_TEMPLATE/feature_request.md).
