import os

import pytest

# Point the app at a throwaway DB and a fake Ollama host *before* any
# app module is imported, since app.config.settings is built once at
# import time.
os.environ.setdefault("DATABASE_PATH", "./data/test_arena.db")
os.environ.setdefault("OLLAMA_HOST", "http://ollama.test")


@pytest.fixture(autouse=True)
def _clean_test_db():
    from app.config import settings

    db_path = settings.database_full_path
    if db_path.exists():
        db_path.unlink()
    yield
    if db_path.exists():
        db_path.unlink()