"""Policy Engine dự phòng: Casbin (bật bằng POLICY_ENGINE=casbin).

Cùng input và cùng mã quy tắc với OPA. Khác biệt: các thuộc tính môi trường (giờ làm việc, IP nội bộ,
danh sách trường được sửa) được tính sẵn bằng Python rồi đưa vào r.env, vì matcher của Casbin chỉ so sánh.
"""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import casbin

from .. import config
from ..net import is_internal
from . import Decision

HERE = Path(__file__).parent / "casbin"
SELF_EDITABLE = {"fullName", "phone", "address"}
ADMIN_EDITABLE = {"fullName", "phone", "address", "position", "role", "salary", "department", "isActive"}
SELF_PROTECTED = {"role", "salary"}


def _minutes(hhmm: str) -> int:
    h, _, m = hhmm.partition(":")
    return int(h) * 60 + int(m or 0)


def working_hours(now_ns: int) -> bool:
    t = datetime.fromtimestamp(now_ns / 1e9, ZoneInfo(config.TIMEZONE))
    m = t.hour * 60 + t.minute
    return _minutes(config.WORK_HOURS_START) <= m < _minutes(config.WORK_HOURS_END)


class CasbinEngine:
    name = "casbin"

    def __init__(self):
        self.enforcer = casbin.Enforcer(str(HERE / "model.conf"), str(HERE / "policy.csv"))

    def decide(self, input_: dict) -> Decision:
        s, o, fields = input_["subject"], input_.get("resource") or {}, set(input_.get("fields") or [])
        sub = SimpleNamespace(
            id=s.get("id", ""), role=s.get("role", ""), department=s.get("department") or "",
            has_role=s.get("role") in ("admin", "manager", "employee"),
        )
        obj = SimpleNamespace(
            id=o.get("id"), owner_id=o.get("owner_id"), department=o.get("department"),
            classification=o.get("classification"), manager_id=o.get("manager_id"),
        )
        env = SimpleNamespace(
            working_hours=working_hours(input_["env"]["now_ns"]),
            internal_ip=is_internal(input_["env"]["ip"]),
            touches_protected=bool(fields & SELF_PROTECTED),
            fields_admin_ok=fields <= ADMIN_EDITABLE,
            fields_self_ok=fields <= SELF_EDITABLE,
        )
        if not sub.has_role:
            return Decision(False, "NO_ROLE")
        ok, explain = self.enforcer.enforce_ex(sub, obj, input_["action"], env)
        rule = explain[3] if explain else "DEFAULT_DENY"
        return Decision(bool(ok), rule)
