import os
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    for env_file in (ROOT / "backend" / ".env", ROOT / "instaclone" / ".env"):
        if env_file.exists():
            load_dotenv(env_file)

from instaclone import posts_store


@pytest.fixture(autouse=True)
def isolated_posts_table(monkeypatch):
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is not configured")
    table = f"test_posts_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("POSTS_TABLE", table)
    posts_store.drop_posts_table(table)
    posts_store.init_posts_db(table)
    yield table
    posts_store.drop_posts_table(table)
