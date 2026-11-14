# Conventions

Start minimal. Add a rule only after an agent (or human) gets it wrong.

- Code lives in `src/trend_detective/`, tests in `tests/` mirroring `src/` paths.
- Names: `snake_case` files for Python, `kebab-case` for web assets.
- Each module has a short docstring/header saying what it owns.
- Prefer pure functions in `core/`; side effects (I/O, network) at the edges.
- Notebooks are for exploration only; anything the demo depends on gets moved into `src/`.
