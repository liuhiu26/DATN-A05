"""Lược đồ MongoDB: validator ($jsonSchema) và index cho 4 collection. Thiết kế chi tiết: DATABASE.md.

- apply_validators(db): tạo collection / cập nhật validator (cần quyền collMod -> chạy bằng tài khoản quản trị DB,
  được gọi trong `python -m app.seed` và `python -m app.db_setup`).
- ensure_indexes(db): tạo index (idempotent), gọi khi API khởi động.
"""
import logging

from pymongo import ASCENDING as ASC
from pymongo import DESCENDING as DESC
from pymongo.database import Database
from pymongo.errors import OperationFailure

log = logging.getLogger("hrdocs.db")

ROLES = ["employee", "manager", "admin"]
UUID = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"  # Keycloak user id (sub)
DEPT_CODE = r"^[A-Z][A-Z0-9_]{1,15}$"

_str = {"bsonType": "string"}
_date = {"bsonType": "date"}
_nullable = lambda schema: {"anyOf": [schema, {"bsonType": "null"}]}  # noqa: E731

VALIDATORS = {
    # Phòng ban. _id = mã phòng ban (IT, HR, SALES) = tên group trong Keycloak.
    "departments": {
        "bsonType": "object",
        "required": ["_id", "code", "name"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "string", "pattern": DEPT_CODE},
            "code": {"bsonType": "string", "pattern": DEPT_CODE},
            "name": {"bsonType": "string", "minLength": 1, "maxLength": 120},
            "manager_id": _nullable({"bsonType": "string", "pattern": UUID}),  # -> employees._id (R6)
            "createdAt": _date,
            "updatedAt": _date,
        },
    },
    # Hồ sơ nhân viên. _id = Keycloak sub; role/department_id/isActive là bản sao của Keycloak.
    "employees": {
        "bsonType": "object",
        "required": ["_id", "email", "fullName", "role", "isActive", "createdAt", "updatedAt"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "string", "pattern": UUID},
            "username": {"bsonType": "string", "minLength": 1, "maxLength": 254},
            "email": {"bsonType": "string", "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$", "maxLength": 254},
            "fullName": {"bsonType": "string", "minLength": 1, "maxLength": 120},
            "role": {"enum": ROLES},
            "department_id": _nullable({"bsonType": "string", "pattern": DEPT_CODE}),  # -> departments._id
            "position": _nullable({"bsonType": "string", "maxLength": 120}),
            "phone": _nullable({"bsonType": "string", "maxLength": 30}),
            "address": _nullable({"bsonType": "string", "maxLength": 300}),
            "salary": {"bsonType": ["int", "long"], "minimum": 0},
            "isActive": {"bsonType": "bool"},
            "createdAt": _date,
            "updatedAt": _date,
        },
    },
    # Tài liệu. department_id = phòng ban của chủ sở hữu lúc tạo (thuộc tính tài nguyên cho R2).
    "documents": {
        "bsonType": "object",
        "required": ["_id", "title", "classification", "owner_id", "createdAt", "updatedAt"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "objectId"},
            "title": {"bsonType": "string", "minLength": 1, "maxLength": 200},
            "content": {"bsonType": "string", "maxLength": 100_000},
            "classification": {"enum": ["internal", "confidential"]},  # R3
            "owner_id": {"bsonType": "string", "pattern": UUID},  # -> employees._id (R1)
            "department_id": _nullable({"bsonType": "string", "pattern": DEPT_CODE}),  # -> departments._id (R2)
            "createdAt": _date,
            "updatedAt": _date,
        },
    },
    # Log theo schema chốt với TV3. Chỉ thêm, không sửa/xóa (xem scripts/mongo-init.js).
    "audit_logs": {
        "bsonType": "object",
        "required": ["timestamp", "request_id", "ip", "method", "endpoint", "http_status", "decision", "latency_ms"],
        "additionalProperties": False,
        "properties": {
            "_id": {"bsonType": "objectId"},
            "timestamp": _date,
            "request_id": {"bsonType": "string", "maxLength": 64},
            "user_id": _nullable(_str),
            "role": _nullable(_str),
            "department": _nullable(_str),
            "ip": _str,
            "method": _str,
            "endpoint": {"bsonType": "string", "maxLength": 2048},
            "resource_id": _nullable(_str),
            "resource_owner_id": _nullable(_str),
            "http_status": {"bsonType": "int", "minimum": 100, "maximum": 599},
            "decision": {"enum": ["allow", "deny"]},
            "policy_rule": _nullable(_str),
            "latency_ms": {"bsonType": ["double", "int", "long"], "minimum": 0},
            "user_agent": _nullable({"bsonType": "string", "maxLength": 1024}),
            "scenario_id": {"bsonType": "string", "maxLength": 128},
        },
    },
}

# (collection, keys, options) – mỗi index phục vụ một truy vấn cụ thể, xem bảng trong DATABASE.md.
INDEXES = [
    ("departments", [("manager_id", ASC)], {"name": "manager_id"}),
    ("employees", [("email", ASC)], {"name": "email_unique", "unique": True}),
    ("employees", [("username", ASC)], {"name": "username_unique", "unique": True, "partialFilterExpression": {"username": {"$type": "string"}}}),
    ("employees", [("department_id", ASC), ("fullName", ASC)], {"name": "department_fullName"}),
    ("employees", [("fullName", ASC)], {"name": "fullName"}),
    ("documents", [("owner_id", ASC), ("updatedAt", DESC)], {"name": "owner_updatedAt"}),
    ("documents", [("department_id", ASC), ("updatedAt", DESC)], {"name": "department_updatedAt"}),
    ("documents", [("department_id", ASC), ("classification", ASC)], {"name": "department_classification"}),
    ("audit_logs", [("timestamp", DESC)], {"name": "timestamp"}),
    ("audit_logs", [("user_id", ASC), ("timestamp", DESC)], {"name": "user_timestamp"}),
    ("audit_logs", [("decision", ASC), ("policy_rule", ASC), ("timestamp", DESC)], {"name": "decision_rule_timestamp"}),
    ("audit_logs", [("scenario_id", ASC), ("timestamp", DESC)], {"name": "scenario_timestamp", "partialFilterExpression": {"scenario_id": {"$exists": True}}}),
    ("audit_logs", [("request_id", ASC)], {"name": "request_id"}),
]

# Index của bản trước (đã được các index ghép ở trên thay thế).
LEGACY_INDEXES = {"documents": ["owner_id_1", "department_id_1"], "audit_logs": ["timestamp_-1", "scenario_id_1"], "employees": ["email_1"]}


def apply_validators(db: Database) -> None:
    existing = set(db.list_collection_names())
    for name, schema in VALIDATORS.items():
        opts = {"validator": {"$jsonSchema": schema}, "validationLevel": "strict", "validationAction": "error"}
        if name in existing:
            db.command({"collMod": name, **opts})
        else:
            db.create_collection(name, **opts)


def ensure_indexes(db: Database) -> None:
    for coll, names in LEGACY_INDEXES.items():
        try:
            current = db[coll].index_information()
            for idx in names:
                if idx in current:
                    db[coll].drop_index(idx)
        except OperationFailure as exc:  # tài khoản ứng dụng không có quyền dropIndex: bỏ qua
            log.warning("cannot drop legacy indexes on %s: %s", coll, exc)
    for coll, keys, opts in INDEXES:
        try:
            db[coll].create_index(keys, **opts)
        except OperationFailure as exc:  # vd. tài khoản DB không có quyền createIndex
            log.warning("cannot create index %s.%s: %s", coll, opts["name"], exc)
