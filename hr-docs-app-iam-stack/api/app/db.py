"""Kết nối MongoDB (PyMongo đồng bộ; FastAPI chạy các endpoint `def` trong threadpool)."""
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.database import Database

from . import config

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


def ensure_indexes(db: Database) -> None:
    db.employees.create_index("email", unique=True)
    db.documents.create_index("owner_id")
    db.documents.create_index("department_id")
    db.audit_logs.create_index([("timestamp", -1)])
    db.audit_logs.create_index("scenario_id", sparse=True)


def now() -> datetime:
    return datetime.now(timezone.utc)
