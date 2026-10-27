# AGENTS.md

Single-package Python boilerplate (package `my_package`, Python >= 3.10). Everything below is verified against `pyproject.toml`, `Makefile`, and `.github/workflows/*.yml`.

## Environment

- A `.venv` already exists (Python 3.12.9) but dev tools are **not** installed in it. Activate first, then install:

  ```powershell
  # PowerShell (Windows)
  .venv\Scripts\Activate.ps1
  pip install -e '.[dev]'          # == make install-dev  (black, isort, pylint, pytest, build, twine, ...)
  ```

  If PowerShell blocks the script, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once.
- `make` targets may not work natively on Windows (`clean` uses `rm`). Run the underlying commands directly or use Git Bash/WSL.
- Importing `my_package` in tests requires the package installed (editable install above) or `PYTHONPATH` set to the repo root.

## Commands (run from repo root)

| Task | Command |
|------|---------|
| Format | `isort my_package && black my_package` (line-length 120; isort before black) |
| Lint | `pylint my_package` (line-length 120) |
| Run all tests | `pytest tests` |
| Run one test | `pytest tests/test_1.py::test_my_function -v` |
| Tests + coverage | `pytest tests --cov` (`make tests-cov`) |
| Build package | `python -m build .` (needs `pip install build`) |
| Clean artifacts | remove `build/`, `dist/`, `my_package.egg-info/` |

Convention order when changing code: `format -> lint -> test`.

## Versioning & publishing

- Version is dynamic, from git tags via setuptools_scm (`pyproject.toml`). `__init__.py` reads it with `importlib.metadata.version("my_package")` — works only after the package is installed.
- CI publishes to PyPI on pushes of tags matching `v*` (`.github/workflows/pypi.yml`, uses `twine upload dist/*` after `python -m build .`).

## Docs

- `pip install -e '.[docs]'` + `sphinx-build docs/source docs/build` (needs pandoc installed). CI deploys the `docs/build/` output to the `documentation` GitHub Pages branch (`.github/workflows/documentation.yml`).

## Known gotchas (verified)

1. **Line endings:** all repo files are CRLF, but `pyproject.toml` sets `expected-line-ending-format = "LF"` for pylint. `pylint my_package` will flag line endings on Windows — either convert files to LF or treat those findings as expected.
2. **CI mismatch:** `tests.yml` runs `make test` and `make install-test`, but the Makefile targets are `tests` and `install-test` (there is no `test` target). Use `pytest tests` directly.
3. **Metadata mismatch:** `pyproject.toml` declares `license.file = "LICENCE"`, but the file on disk is `LICENSE`. If packaging/build complains about the license file, this is why.
4. `black` in `pyproject` dev deps is pinned to `22.3`; pre-commit uses `22.10.0`.

## Repo layout

- `my_package/` — library code (`__init__.py`, `my_module.py`). Entrypoint import: `from my_package.my_module import MyClass, my_function`.
- `tests/` — pytest suite (`test_1.py`).
- `examples/` — `my_example.ipynb` + `data/`.
- `docs/` — Sphinx sources; CI builds to `docs/build/`.
- `.github/workflows/` — `tests.yml`, `pypi.yml`, `documentation.yml`.
- `.pre-commit-config.yaml` — black + standard hooks (`pre-commit install` to enable).
