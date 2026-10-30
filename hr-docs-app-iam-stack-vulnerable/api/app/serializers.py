"""Chuyển document Mongo sang JSON trả cho frontend (giữ cùng dạng với bản Express: `_id`, owner/department lồng)."""
from bson import ObjectId

from .db import get_db
from .errors import HttpError

EMPLOYEE_PUBLIC = ("email", "fullName", "role", "position", "phone", "address", "salary", "isActive", "createdAt", "updatedAt")


def parse_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HttpError(400, "Invalid id")
    return ObjectId(value)


def dept_brief(dept_id: str | None, cache: dict | None = None) -> dict | None:
    if not dept_id:
        return None
    if cache is not None and dept_id in cache:
        return cache[dept_id]
    d = get_db().departments.find_one({"_id": dept_id})
    out = {"_id": d["_id"], "code": d["code"], "name": d["name"]} if d else {"_id": dept_id, "code": dept_id, "name": ""}
    if cache is not None:
        cache[dept_id] = out
    return out


def person_brief(user_id: str | None) -> dict | None:
    if not user_id:
        return None
    u = get_db().employees.find_one({"_id": user_id}, {"fullName": 1, "email": 1})
    return {"_id": user_id, "fullName": u.get("fullName"), "email": u.get("email")} if u else {"_id": user_id}


def employee_out(e: dict, cache: dict | None = None, fields=EMPLOYEE_PUBLIC) -> dict:
    out = {"_id": e["_id"], **{k: e.get(k) for k in fields}}
    out["department"] = dept_brief(e.get("department_id"), cache)
    return out


def document_out(d: dict, with_content: bool = True, cache: dict | None = None) -> dict:
    out = {
        "_id": str(d["_id"]),
        "title": d["title"],
        "classification": d.get("classification", "internal"),
        "owner": person_brief(d.get("owner_id")),
        "department": dept_brief(d.get("department_id"), cache),
        "createdAt": d.get("createdAt"),
        "updatedAt": d.get("updatedAt"),
    }
    if with_content:
        out["content"] = d.get("content", "")
    return out
