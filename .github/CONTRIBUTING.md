# Contributing to PowerSearch MCP

Thanks for investing your time into PowerSearch MCP! This guide covers how to set up a dev environment, what we expect from changes, and how to ship high-quality contributions.

## Ground rules

- Read and follow the project principles in [AGENTS.md](AGENTS.md) (simplicity, developer ergonomics, maintainability, tests for every change).
- Optimize for clarity and locality: keep related logic close together and resist unnecessary abstraction.
- Keep changes small and focused; prefer one feature/bugfix per pull request.
- When in doubt, start a discussion in an issue before implementing a large change.

## Getting set up

1. Install Python 3.13 and [uv](https://docs.astral.sh/uv/).
2. Create the virtual environment and install dependencies:

- `make init` (creates `.venv`, installs dev deps, installs pre-commit hooks)

1. Fetch the Camoufox browser assets: `camoufox fetch`.
2. (Optional but recommended) Start a local SearXNG instance for realistic testing (see [README.md](README.md) for the Docker command).

## Development workflow

- Use `uv` for all Python commands (project convention):
  - Install/sync deps: `make sync`
  - Run quality gates: `make test` (runs `uv run pre-commit run --all-files`)
- Write tests for new code and regression tests for bug fixes. Tests must be deterministic and isolated; prefer fakes over live services.
- Keep configuration simple. Runtime config comes from environment variables with the `POWERSEARCH_` prefix; add new settings only when necessary and document them in [README.md](README.md).
- If you touch scraping, networking, or concurrency, add failure-path coverage (timeouts, retries, duplication).
- Update documentation when behavior, flags, or interfaces change.

## Style and linting

- Follow the existing formatting and linting enforced by pre-commit (ruff, black, mypy, etc.). Let the tools format for you.
- Use clear names and concise comments only when the code is non-obvious.
- Keep line length within the Ruff config (80 chars) and target Python 3.13.

## Testing

- Fast check: `make test` (runs all pre-commit hooks across the repo).
- Run targeted tests when iterating: `uv run pytest tests/test_powersearch.py -k your_case` (optional but encouraged).
- Add at least one happy-path and one failure-path test for new functionality.

## Submitting changes

1. Ensure `make test` passes locally.
2. Include a clear description of what changed and why in your pull request. Link related issues.
3. Keep commits atomic and meaningful; small, reviewable PRs get merged faster.
4. Open pull requests against the default branch (`master`).
5. Be responsive to review feedback; ask questions if anything is unclear.

## Reporting issues

- Check existing issues first. If you open a new one, include steps to reproduce, expected vs. actual behavior, logs, and environment details (OS, Python version, relevant `POWERSEARCH_` settings).

Thank you for helping make PowerSearch reliable and easy to use.
