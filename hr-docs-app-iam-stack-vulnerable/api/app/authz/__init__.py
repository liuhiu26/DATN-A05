"""Điểm thực thi chính sách (PEP) phía FastAPI.

Router gọi `authorize(...)`; quyết định do Policy Engine trả về (OPA mặc định, Casbin dự phòng),
kết quả được ghi vào request.state.authz để middleware log điền decision / policy_rule / resource_*.
"""
import time
from dataclasses import dataclass

from fastapi import Request

from .. import config
from ..errors import HttpError
from ..net import client_ip
from ..security import Principal


@dataclass(frozen=True)
class Decision:
    allow: bool
    rule: str


def build_input(action: str, principal: Principal, resource: dict | None, fields: list[str] | None, ip: str) -> dict:
    return {
        "action": action,
        "subject": {"id": principal.id, "role": principal.role, "department": principal.department},
        "resource": resource or {},
        "fields": list(fields or []),
        "env": {"ip": ip, "now_ns": time.time_ns()},
    }


_engine = None


def get_engine():
    global _engine
    if _engine is None:
        if config.POLICY_ENGINE == "casbin":
            from .casbin_engine import CasbinEngine

            _engine = CasbinEngine()
        else:
            from .opa_engine import OpaEngine

            _engine = OpaEngine()
    return _engine


def set_engine(engine) -> None:
    global _engine
    _engine = engine


def record(request: Request, allow: bool, rule: str, resource_id=None, resource_owner_id=None) -> None:
    request.state.authz = {
        "decision": "allow" if allow else "deny",
        "policy_rule": rule,
        "resource_id": str(resource_id) if resource_id is not None else None,
        "resource_owner_id": str(resource_owner_id) if resource_owner_id is not None else None,
    }


def authorize(
    request: Request,
    principal: Principal,
    action: str,
    resource: dict | None = None,
    *,
    fields: list[str] | None = None,
    resource_owner_id=None,
) -> Decision:
    """Hỏi Policy Engine; ghi quyết định; ném 403 nếu bị từ chối (503 nếu engine không trả lời)."""
    resource_id = (resource or {}).get("id")
    payload = build_input(action, principal, resource, fields, client_ip(request))
    try:
        decision = get_engine().decide(payload)
    except Exception as exc:  # fail closed
        record(request, False, "POLICY_ENGINE_UNAVAILABLE", resource_id, resource_owner_id)
        raise HttpError(503, "Policy engine unavailable") from exc

    record(request, decision.allow, decision.rule, resource_id, resource_owner_id)
    if not decision.allow:
        raise HttpError(403, f"Forbidden ({decision.rule})")
    return decision
