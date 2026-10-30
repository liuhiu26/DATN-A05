"""Ghi một bản ghi log cho mỗi request /api/* theo schema đã chốt với TV3 (mốc M1):

timestamp, request_id, user_id, role, department, ip, method, endpoint, resource_id, resource_owner_id,
http_status, decision (allow/deny), policy_rule, latency_ms, user_agent, scenario_id (chỉ có ở log tấn công).

Đích ghi: Mongo `audit_logs` (cho GET /api/admin/audit) và file JSON Lines ACCESS_LOG_FILE,
được Grafana Alloy đọc và đẩy vào Loki (job="hrdocs-api").
"""
import json
import logging
import threading
import time
import uuid
from pathlib import Path

from fastapi import Request

from . import config
from .db import get_db, now
from .net import client_ip, from_trusted_proxy

log = logging.getLogger("hrdocs.access")
SKIP = {"/api/health", "/api/docs", "/api/openapi.json", "/api/docs/oauth2-redirect"}

_lock = threading.Lock()
_file = None
if config.ACCESS_LOG_FILE:
    path = Path(config.ACCESS_LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    _file = path.open("a", encoding="utf-8", buffering=1)


def _request_id(request: Request) -> str:
    # Kong (plugin correlation-id) gắn X-Request-Id; chỉ nhận lại khi request đi qua Kong để nối log 2 tầng.
    rid = request.headers.get("x-request-id", "")
    if rid and from_trusted_proxy(request) and len(rid) <= 64:
        return rid
    return str(uuid.uuid4())


async def request_log_middleware(request: Request, call_next):
    started = time.perf_counter()
    request.state.request_id = _request_id(request)
    request.state.authz = None
    request.state.principal = None

    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id

    endpoint = request.url.path
    # V-LOG-1: client tự tắt audit log cho request của mình bằng header X-Debug-Skip-Log.
    # Kẻ tấn công thêm header này để hành vi khai thác KHÔNG để lại vết trong audit_logs / Loki.
    # Bản secure: không có lối tắt này; mọi request /api/* đều sinh đúng một bản ghi log.
    if request.method == "OPTIONS" or endpoint in SKIP or request.headers.get("x-debug-skip-log"):
        return response

    status = response.status_code
    authz = request.state.authz or {}
    p = request.state.principal
    scenario = request.headers.get("x-scenario-id")
    entry = {
        "timestamp": now(),
        "request_id": request.state.request_id,
        "user_id": p.id if p else None,
        "role": (p.role or None) if p else None,
        "department": (p.department or None) if p else None,
        "ip": client_ip(request),
        "method": request.method,
        "endpoint": endpoint,
        "resource_id": authz.get("resource_id"),
        "resource_owner_id": authz.get("resource_owner_id"),
        "http_status": status,
        "decision": authz.get("decision") or ("deny" if status in (401, 403) else "allow"),
        "policy_rule": authz.get("policy_rule") or ("AUTHN" if status == 401 else None),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "user_agent": request.headers.get("user-agent"),
    }
    if scenario:
        entry["scenario_id"] = scenario[:128]

    line = json.dumps({**entry, "timestamp": entry["timestamp"].isoformat(timespec="milliseconds")}, ensure_ascii=False)
    if _file:
        with _lock:
            _file.write(line + "\n")
    try:
        get_db().audit_logs.insert_one(entry)
    except Exception as exc:  # không để lỗi ghi log làm hỏng response
        log.error("cannot write audit log: %s", exc)
    return response
