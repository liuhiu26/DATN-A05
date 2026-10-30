from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from ..authz import authorize
from ..db import get_db
from ..errors import HttpError
from ..security import Principal, current_principal
from ..serializers import person_brief

router = APIRouter(prefix="/api/departments", tags=["departments"])


def dept_out(d: dict) -> dict:
    return {"_id": d["_id"], "code": d["code"], "name": d["name"], "manager": person_brief(d.get("manager_id"))}


@router.get("", summary="Danh sách phòng ban (thông tin chung nội bộ)")
def list_departments(request: Request, p: Principal = Depends(current_principal)):
    authorize(request, p, "department:list")
    return [dept_out(d) for d in get_db().departments.find().sort("code", 1)]


@router.get("/{dept_id}/reports", summary="Báo cáo phòng ban: manager của chính phòng ban đó (R6), admin")
def department_report(dept_id: str, request: Request, p: Principal = Depends(current_principal)):
    db = get_db()
    dept = db.departments.find_one({"_id": dept_id})
    if not dept:
        raise HttpError(404, "Department not found")
    authorize(
        request, p, "department:report",
        {"id": dept["_id"], "department": dept["_id"], "manager_id": dept.get("manager_id")},
        resource_owner_id=dept.get("manager_id"),
    )
    employees = list(db.employees.find({"department_id": dept_id}, {"fullName": 1, "email": 1, "role": 1, "position": 1, "salary": 1, "isActive": 1}))
    total = sum(e.get("salary") or 0 for e in employees)
    by_role: dict = {}
    for e in employees:
        by_role[e.get("role")] = by_role.get(e.get("role"), 0) + 1
    return {
        "department": dept_out(dept),
        "generatedAt": datetime.now(timezone.utc),
        "headcount": len(employees),
        "activeCount": sum(1 for e in employees if e.get("isActive", True)),
        "byRole": by_role,
        "totalSalary": total,
        "averageSalary": round(total / len(employees)) if employees else 0,
        "documentCount": db.documents.count_documents({"department_id": dept_id}),
        "confidentialCount": db.documents.count_documents({"department_id": dept_id, "classification": "confidential"}),
        "employees": employees,
    }
