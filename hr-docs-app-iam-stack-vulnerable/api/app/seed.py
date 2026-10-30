"""Xóa sạch DB rồi nạp dữ liệu mẫu.  Chạy:  docker compose run --rm api python -m app.seed
(hoặc trong thư mục api/:  python -m app.seed)"""
import random

from .db import apply_validators, ensure_indexes, get_db, now
from .seed_data import DEPARTMENTS, DOCUMENTS, PASSWORD, USERS


def seed():
    db = get_db()
    for name in ("departments", "employees", "documents", "audit_logs"):
        db[name].delete_many({})
    apply_validators(db)
    ensure_indexes(db)

    ids = {u[0]: u[1] for u in USERS}
    ts = now()
    db.departments.insert_many(
        [{"_id": d["_id"], "code": d["code"], "name": d["name"], "manager_id": ids[d["manager"]]} for d in DEPARTMENTS]
    )
    db.employees.insert_many([
        {
            "_id": uid, "username": username, "email": f"{username}@corp.local", "fullName": name, "role": role,
            "department_id": dept, "position": pos, "salary": salary, "isActive": True,
            "phone": "09" + str(random.randint(10_000_000, 99_999_999)), "address": "Hà Nội",
            "createdAt": ts, "updatedAt": ts,
        }
        for username, uid, name, role, dept, pos, salary in USERS
    ])
    dept_of = {u[0]: u[4] for u in USERS}
    db.documents.insert_many([
        {"title": t, "content": c, "classification": cl, "owner_id": ids[o], "department_id": dept_of[o],
         "createdAt": ts, "updatedAt": ts}
        for o, t, c, cl in DOCUMENTS
    ])

    print(f"Seed xong DB '{db.name}'. Đăng nhập qua Keycloak, mật khẩu chung: {PASSWORD}")
    for username, uid, _, role, dept, *_ in USERS:
        print(f"  {username + '@corp.local':28} {role:9} {dept or '-':6} {uid}")


if __name__ == "__main__":
    seed()
