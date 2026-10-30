"""OPA và Casbin phải cho cùng quyết định trên mọi tổ hợp đầu vào.
Cần OPA đang chạy:  OPA_URL=http://localhost:8181/v1/data/hrdocs/authz/decision pytest tests/test_policy_parity.py
(OPA phải nạp cùng giá trị giờ làm việc / dải IP với .env). Không có OPA thì test được bỏ qua."""
import itertools
import os

import httpx
import pytest

from app.authz.casbin_engine import CasbinEngine
from app.authz.opa_engine import OpaEngine

OPA_URL = os.getenv("OPA_URL", "")

SUBJECTS = [
    {"id": "u-admin", "role": "admin", "department": ""},
    {"id": "u-itm", "role": "manager", "department": "IT"},
    {"id": "u-alice", "role": "employee", "department": "IT"},
    {"id": "u-bob", "role": "employee", "department": "IT"},
    {"id": "u-x", "role": "", "department": "IT"},
]
RESOURCES = [
    {"id": "d1", "owner_id": "u-alice", "department": "IT", "classification": "internal"},
    {"id": "d2", "owner_id": "u-alice", "department": "IT", "classification": "confidential"},
    {"id": "u-alice", "owner_id": "u-alice", "department": "IT"},
    {"id": "u-admin", "owner_id": "u-admin", "department": None},
    {"id": "IT", "department": "IT", "manager_id": "u-itm"},
    {"id": "HR", "department": "HR", "manager_id": "u-hrm"},
]
ACTIONS = ["document:read", "document:update", "document:delete", "employee:read", "employee:update",
           "department:report", "admin:access", "document:list", "profile:read"]
FIELDS = [[], ["phone"], ["salary"], ["role", "phone"], ["position"], ["email"]]
IPS = ["10.0.0.1", "203.0.113.9"]
TIMES = [1792033200 * 10**9, 1792069200 * 10**9]  # 2026-10-15 10:00 và 20:00 giờ VN


@pytest.mark.skipif(not OPA_URL, reason="đặt OPA_URL để so sánh với OPA thật")
def test_opa_and_casbin_agree():
    try:
        opa = OpaEngine(OPA_URL)
        httpx.get(OPA_URL.split("/v1/")[0] + "/health", timeout=2).raise_for_status()
    except Exception:
        pytest.skip("OPA không chạy")
    casbin = CasbinEngine()
    mismatches = []
    for a, s, r, f, ip, t in itertools.product(ACTIONS, SUBJECTS, RESOURCES, FIELDS, IPS, TIMES):
        if f and a != "employee:update":
            continue
        inp = {"action": a, "subject": s, "resource": r, "fields": f, "env": {"ip": ip, "now_ns": t}}
        if opa.decide(inp) != casbin.decide(inp):
            mismatches.append((inp, opa.decide(inp), casbin.decide(inp)))
    assert not mismatches, mismatches[:3]
