from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from ..authz import authorize, record
from ..db import get_db, now
from ..errors import HttpError
from ..keycloak_admin import get_admin
from ..schemas import EmployeePatch, parse
from ..security import Principal, current_principal
from ..serializers import employee_out

router = APIRouter(prefix="/api/employees", tags=["employees"])


def load(emp_id: str) -> dict:
    emp = get_db().employees.find_one({"_id": emp_id})
    if not emp:
        raise HttpError(404, "Employee not found")
    return emp


def as_resource(emp: dict) -> dict:
    return {"id": emp["_id"], "owner_id": emp["_id"], "department": emp.get("department_id")}


@router.get("", summary="Danh sách nhân viên được xem")
def list_employees(request: Request, p: Principal = Depends(current_principal)):
    authorize(request, p, "employee:list")
    if p.role == "admin":
        flt = {}
    elif p.role == "manager" and p.department:
        flt = {"department_id": p.department}
    else:
        flt = {"_id": p.id}
    cache: dict = {}
    rows = get_db().employees.find(flt).sort("fullName", 1)
    return [employee_out(e, cache, fields=("email", "fullName", "role", "position")) for e in rows]


@router.get("/{emp_id}", summary="Xem hồ sơ: bản thân, manager cùng phòng, admin")
def get_employee(emp_id: str, request: Request, p: Principal = Depends(current_principal)):
    emp = load(emp_id)
    # V-BOLA-3 / IDOR: bỏ authorize('employee:read'). Ai cũng đọc hồ sơ đầy đủ của người khác,
    # GỒM CẢ salary, chỉ cần biết id. Bản secure: authorize(... "employee:read" ..., resource_owner_id=emp["_id"]).
    record(request, True, "NO_CHECK", resource_id=emp["_id"], resource_owner_id=emp["_id"])
    return employee_out(emp)


@router.patch("/{emp_id}", summary="Cập nhật hồ sơ: bản thân (fullName, phone, address), admin; không ai tự sửa role/salary (R4)")
def patch_employee(emp_id: str, request: Request, body: Any = Body(..., examples=[{"phone": "0900000000"}]), p: Principal = Depends(current_principal)):
    emp = load(emp_id)
    # V-PRIVESC-1: bỏ authorize('employee:update') → mất R4 (không ai tự sửa role/salary) và kiểm tra bản thân/admin.
    # V-MASS-2: ghi thẳng mọi trường trong body vào Mongo, không qua allowlist (EmployeePatch).
    # Nhân viên tự PATCH chính mình {"role":"admin","salary":999999999} → thành admin, tự tăng lương.
    # Bản secure: authorize('employee:update', fields=...) rồi parse(EmployeePatch) chỉ cho self sửa fullName/phone/address.
    record(request, True, "NO_CHECK", resource_id=emp["_id"], resource_owner_id=emp["_id"])
    data = dict(body) if isinstance(body, dict) else {}
    if "department" in data:
        data["department_id"] = data.pop("department") or None

    # Đồng bộ thuộc tính dùng để phân quyền sang Keycloak (nơi phát token) rồi mới ghi Mongo.
    kc = get_admin()
    if "role" in data and data["role"] != emp.get("role"):
        kc.set_role(emp["_id"], data["role"])
    if "department_id" in data and data["department_id"] != emp.get("department_id"):
        kc.set_department(emp["_id"], data["department_id"])
    if "isActive" in data and data["isActive"] != emp.get("isActive", True):
        kc.set_enabled(emp["_id"], data["isActive"])

    if data:
        data["updatedAt"] = now()
        get_db().employees.update_one({"_id": emp["_id"]}, {"$set": data})
        emp.update(data)
    out = employee_out(emp)
    out["department"] = emp.get("department_id")  # frontend cũ nhận id phòng ban sau PATCH
    return out
