"""Kết nối MongoDB (PyMongo đồng bộ; FastAPI chạy các endpoint `def` trong threadpool)."""
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.database import Database

from . import config
from .db_schema import apply_validators, ensure_indexes  # noqa: F401  (re-export)

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        _client = MongoClient(config.MONGO_URI, tz_aware=True, serverSelectionTimeoutMS=5000)
        _db = _client[config.MONGO_DB]
    return _db


def set_db(db: Database) -> None:
    """Dùng trong test (mongomock)."""
    global _db
    _db = db


def now() -> datetime:
    return datetime.now(timezone.utc)
