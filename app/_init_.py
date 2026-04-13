# app/__init__.py
# Marks `app` as a Python package.
# Required for:
#   - relative imports (from . import database)
#   - uvicorn app.main:app  to resolve correctly
#   - python -m app.seed_admin  to work from the project root
