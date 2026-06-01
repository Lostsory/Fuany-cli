# Repository Guidelines

## Project Structure & Module Organization

This is a Python 3.13 CLI project packaged as `fuany-cli`. The executable entry point is `fuany`, mapped to `mini_cc:main` in `pyproject.toml`.

- `mini_cc.py`: REPL entry point and main agent loop.
- `registry.py`: tool registration, schema derivation, permissions, and dispatch.
- `config.py`: environment loading and typed runtime settings.
- `llm.py`: provider/client/model construction.
- `state.py`: per-agent context state.
- `tools/`: built-in tool implementations such as files, shell, search, web, task, and skill.
- `skills/`: local skill definitions loaded progressively.
- `.zed/`: local Zed editor settings and tasks; currently ignored by Git.

There is no dedicated `tests/` directory yet.

## Build, Test, and Development Commands

Use `uv` for environment and command execution:

```bash
uv sync
uv run fuany
uv run python mini_cc.py
uv run python -m compileall -q -x '(^|/)(.venv|.git|__pycache__)(/|$)' .
```

- `uv sync`: installs locked dependencies and the local editable package.
- `uv run fuany`: runs the packaged CLI entry point.
- `uv run python mini_cc.py`: runs the entry file directly.
- `compileall`: performs a lightweight syntax/import-bytecode check.

For global CLI development, use:

```bash
uv tool install --editable .
```

## Coding Style & Naming Conventions

Follow standard Python style with 4-space indentation, explicit type hints where they clarify contracts, and small modules with clear ownership. Use `snake_case` for functions, variables, and modules; use `PascalCase` for dataclasses and typed records.

Imports with side effects are intentional when annotated, for example `import tools` for registration and `import readline` for REPL editing support.

## Testing Guidelines

No formal test framework is configured. For now, validate changes with `uv sync`, `uv run fuany`, and the `compileall` command above. When adding tests, prefer `pytest`, place files under `tests/`, and name them `test_<module>.py`.

## Commit & Pull Request Guidelines

Recent history uses short, imperative messages with optional conventional prefixes, for example `chore: ...`, `docs: ...`, and `refactor: ...`. Keep commits focused and mention user-visible CLI behavior when relevant.

Pull requests should include a concise summary, commands run for verification, any environment/configuration changes, and linked issues when applicable.

## Security & Configuration Tips

Copy `.env.example` to `.env` and keep secrets local. `DEEPSEEK_API_KEY` is required for the default provider. `MINI_CC_BRAVE_SEARCH_API_KEY` is optional and only affects web search. Never commit `.env`, `.venv/`, logs, caches, or `*.egg-info/`.
