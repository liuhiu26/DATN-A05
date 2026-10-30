from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request

from ..authz import authorize
from ..db import get_db, now
from ..errors import HttpError
from ..keycloak_admin import get_admin
from ..schemas import UserCreate, parse
from ..security import Principal, current_principal
from ..serializers import employee_out


def admin_guard(request: Request, p: Principal = Depends(current_principal)) -> Principal:
    """Admin + R5 (chỉ từ IP nội bộ) cho toàn bộ /api/admin/*. Kong cũng chặn IP ở gateway (ip-restriction)."""
    authorize(request, p, "admin:access")
    return p


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(admin_guard)])


@router.post("/users", status_code=201, summary="Tạo tài khoản (Keycloak + hồ sơ Mongo)")
def create_user(request: Request, body: Any = Body(..., examples=[{"email": "eve@corp.local", "password": "Password123!", "fullName": "Trịnh Thu Em", "role": "employee", "department": "IT"}])):
    data = parse(UserCreate, body)
    db = get_db()
    email = data.email.lower()
    if data.department and not db.departments.find_one({"_id": data.department}):
        raise HttpError(400, "Department not found")
    if db.employees.find_one({"email": email}):
        raise HttpError(409, "Email already exists")

    kc = get_admin()
    user_id = kc.create_user(email=email, password=data.password, full_name=data.fullName, role=data.role, department=data.department)
    ts = now()
    emp = {
        "_id": user_id, "email": email, "fullName": data.fullName, "role": data.role,
        "department_id": data.department, "position": data.position, "phone": data.phone,
        "address": data.address, "salary": data.salary, "isActive": True, "createdAt": ts, "updatedAt": ts,
    }
    try:
        db.employees.insert_one(emp)
    except Exception:
        kc.delete_user(user_id)
        raise
    request.state.authz.update(resource_id=user_id, resource_owner_id=user_id)
    return employee_out(emp)


FILTERS = ("decision", "policy_rule", "user_id", "scenario_id", "endpoint", "method", "request_id")


@router.get("/audit", summary="Xem audit log (đúng log schema)")
def audit(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    decision: str | None = None,
    policy_rule: str | None = None,
    user_id: str | None = None,
    scenario_id: str | None = None,
    endpoint: str | None = None,
    method: str | None = None,
    request_id: str | None = None,
    http_status: int | None = None,
):
    values = dict(decision=decision, policy_rule=policy_rule, user_id=user_id, scenario_id=scenario_id,
                  endpoint=endpoint, method=method, request_id=request_id)
    flt: dict = {k: v for k, v in values.items() if v}
    if http_status is not None:
        flt["http_status"] = http_status
    col = get_db().audit_logs
    items = []
    for row in col.find(flt).sort("timestamp", -1).skip((page - 1) * limit).limit(limit):
        row["_id"] = str(row["_id"])
        items.append(row)
    return {"page": page, "limit": limit, "total": col.count_documents(flt), "items": items}
