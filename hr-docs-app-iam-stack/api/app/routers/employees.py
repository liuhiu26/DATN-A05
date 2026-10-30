from typing import Any

from fastapi import APIRouter, Body, Depends, Request

from ..authz import authorize
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
    authorize(request, p, "employee:read", as_resource(emp), resource_owner_id=emp["_id"])
    return employee_out(emp)


@router.patch("/{emp_id}", summary="Cập nhật hồ sơ: bản thân (fullName, phone, address), admin; không ai tự sửa role/salary (R4)")
def patch_employee(emp_id: str, request: Request, body: Any = Body(..., examples=[{"phone": "0900000000"}]), p: Principal = Depends(current_principal)):
    emp = load(emp_id)
    fields = list(body.keys()) if isinstance(body, dict) else []
    authorize(request, p, "employee:update", as_resource(emp), fields=fields, resource_owner_id=emp["_id"])

    data = parse(EmployeePatch, body).model_dump(exclude_unset=True)
    if "department" in data:
        dept = data.pop("department")
        if dept and not get_db().departments.find_one({"_id": dept}):
            raise HttpError(400, "Department not found")
        data["department_id"] = dept or None

    # Đồng bộ thuộc tính dùng để phân quyền sang Keycloak trước (nơi phát token), rồi mới ghi Mongo.
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
