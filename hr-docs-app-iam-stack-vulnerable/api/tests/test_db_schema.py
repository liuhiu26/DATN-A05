"""Kiểm validator + index trên MongoDB thật (mongomock không hỗ trợ).
    MONGO_TEST_URI=mongodb://localhost:27017 pytest tests/test_db_schema.py
Dùng DB riêng `hr_docs_schema_test` và xóa nó sau khi chạy."""
import os
from datetime import datetime, timezone

import pytest
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, WriteError

from app import db as appdb
from app.seed import seed
from app.seed_data import USERS

URI = os.getenv("MONGO_TEST_URI", "")
pytestmark = pytest.mark.skipif(not URI, reason="đặt MONGO_TEST_URI để chạy với Mongo thật")
ALICE = USERS[2][1]
NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def mdb():
    client = MongoClient(URI, tz_aware=True)
    database = client["hr_docs_schema_test"]
    appdb.set_db(database)
    seed()
    yield database
    client.drop_database("hr_docs_schema_test")


def employee(**kw):
    base = {"_id": "b0000000-0000-4000-8000-000000000099", "email": "x@corp.local", "fullName": "X", "role": "employee",
            "department_id": "IT", "salary": 1, "isActive": True, "createdAt": NOW, "updatedAt": NOW}
    return {**base, **kw}


@pytest.mark.parametrize("bad", [
    {"role": "superadmin"},
    {"salary": -1},
    {"isAdmin": True},                       # trường lạ (mass assignment) bị chặn ở tầng DB
    {"_id": "not-a-keycloak-id"},
    {"department_id": "it"},
    {"email": "no-at-sign"},
])
def test_employee_validator_rejects(mdb, bad):
    with pytest.raises(WriteError):
        mdb.employees.insert_one(employee(**bad))


def test_employee_validator_accepts_and_email_unique(mdb):
    mdb.employees.insert_one(employee())
    with pytest.raises(DuplicateKeyError):
        mdb.employees.insert_one(employee(_id="b0000000-0000-4000-8000-000000000098"))
    mdb.employees.delete_one({"_id": employee()["_id"]})


@pytest.mark.parametrize("bad", [{"classification": "secret"}, {"owner_id": "x"}, {"title": ""}, {"owner": ALICE}])
def test_document_validator_rejects(mdb, bad):
    doc = {"title": "t", "content": "", "classification": "internal", "owner_id": ALICE, "department_id": "IT",
           "createdAt": NOW, "updatedAt": NOW, **bad}
    with pytest.raises(WriteError):
        mdb.documents.insert_one(doc)


def test_audit_log_validator(mdb):
    good = {"timestamp": NOW, "request_id": "r1", "user_id": None, "role": None, "department": None, "ip": "10.0.0.1",
            "method": "GET", "endpoint": "/api/x", "resource_id": None, "resource_owner_id": None, "http_status": 200,
            "decision": "allow", "policy_rule": None, "latency_ms": 1.5, "user_agent": None}
    mdb.audit_logs.insert_one(dict(good))
    with pytest.raises(WriteError):
        mdb.audit_logs.insert_one({**good, "decision": "maybe"})


def winning_index(cursor_explain) -> str:
    plan = cursor_explain["queryPlanner"]["winningPlan"]
    names = []

    def walk(node):
        if "indexName" in node:
            names.append(node["indexName"])
        for key in ("inputStage", "queryPlan"):
            if key in node:
                walk(node[key])
        for child in node.get("inputStages", []):
            walk(child)

    walk(plan)
    return ",".join(sorted(set(names))) or "COLLSCAN"


@pytest.mark.parametrize("coll,query,sort,expected", [
    ("documents", {"owner_id": ALICE}, [("updatedAt", -1)], "owner_updatedAt"),                     # R1 list
    ("documents", {"department_id": "IT"}, [("updatedAt", -1)], "department_updatedAt"),             # R2 list
    ("documents", {"department_id": "IT", "classification": "confidential"}, None, "department_classification"),
    ("employees", {"department_id": "IT"}, [("fullName", 1)], "department_fullName"),                # manager list / R6
    ("employees", {"email": "alice@corp.local"}, None, "email_unique"),
    ("departments", {"manager_id": ALICE}, None, "manager_id"),
    ("audit_logs", {"scenario_id": "S1"}, [("timestamp", -1)], "scenario_timestamp"),
    ("audit_logs", {"decision": "deny", "policy_rule": "R4_NO_SELF_ROLE_SALARY"}, [("timestamp", -1)], "decision_rule_timestamp"),
    ("audit_logs", {"user_id": ALICE}, [("timestamp", -1)], "user_timestamp"),
])
def test_queries_use_index(mdb, coll, query, sort, expected):
    cur = mdb[coll].find(query)
    if sort:
        cur = cur.sort(sort)
    assert winning_index(cur.explain()) == expected


def test_manager_or_query_uses_both_indexes(mdb):
    cur = mdb.documents.find({"$or": [{"owner_id": ALICE}, {"department_id": "IT"}]})
    used = winning_index(cur.explain())
    assert "COLLSCAN" not in used and "owner" in used and "department" in used
