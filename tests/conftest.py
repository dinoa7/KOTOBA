import os
import tempfile

# Must happen before any `app.*` module is imported anywhere in the session:
# config.py reads these env vars once, at import time.
os.environ["KOTOBA_DATA_DIR"] = tempfile.mkdtemp(prefix="kotoba_test_")
os.environ["MOCK"] = "1"

import pytest

from app.db import DB_PATH, init_db
from app import vectors as vectors_module


@pytest.fixture(autouse=True)
def fresh_storage():
    if DB_PATH.exists():
        DB_PATH.unlink()
    if vectors_module.VECTORS_PATH.exists():
        vectors_module.VECTORS_PATH.unlink()
    vectors_module._store = None
    init_db()
    yield
