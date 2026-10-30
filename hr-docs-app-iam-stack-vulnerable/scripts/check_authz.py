#!/usr/bin/env python3
"""Kiểm tra ma trận phân quyền end-to-end qua Kong (sau khi seed).

    python scripts/check_authz.py            # chỉ cần Python 3.10+, không cần cài thêm thư viện

Lấy token từ Keycloak (client hrdocs-cli, password grant – chỉ dùng trong lab), gọi API qua Kong
(http://localhost:8000/api) và so mã HTTP với ma trận quyền R1–R6. Script tạo/sửa/xóa dữ liệu thật;
chạy lại seed để reset. Khi bạn cố ý cài lỗ hổng, các dòng tương ứng sẽ chuyển sang FAIL.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.getenv("API_URL", "http://localhost:8000/api")
KC = os.getenv("KEYCLOAK_URL", "http://localhost:8080") + "/realms/hrdocs/protocol/openid-connect/token"
PASSWORD = "Password123!"
passed = failed = 0


def call(token, method, path, body=None, headers=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as res:
            raw = res.read()
            return res.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            return err.code, json.loads(raw) if raw else None
        except ValueError:
            return err.code, raw.decode(errors="replace")


def status(*args, **kw):
    return call(*args, **kw)[0]


def expect(label, actual, expected):
    global passed, failed
    ok = actual == expected
    passed, failed = passed + ok, failed + (not ok)
    print(f"{'PASS' if ok else 'FAIL'}  {label}  (got {actual}, expected {expected})")


def login(username):
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": "hrdocs-cli", "username": username, "password": PASSWORD}).encode()
    with urllib.request.urlopen(urllib.request.Request(KC, data=data)) as res:
        return json.load(res)["access_token"]


def tamper(token):
    """Đổi realm role trong payload nhưng giữ chữ ký cũ -> chữ ký sai."""
    h, p, s = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
    claims["realm_access"] = {"roles": ["admin"]}
    p2 = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{h}.{p2}.{s}"


def main():
    names = ["admin", "it.manager", "alice", "bob", "hr.manager", "carol"]
    T = {n: login(n) for n in names}
    ID = {n: call(T[n], "GET", "/auth/me")[1]["_id"] for n in names}

    docs = call(T["admin"], "GET", "/documents")[1]
    doc_by = lambda n, cls: next(d["_id"] for d in docs if d["owner"]["_id"] == ID[n] and d["classification"] == cls)
    try:
        alice_doc, alice_secret, carol_doc = doc_by("alice", "internal"), doc_by("alice", "confidential"), doc_by("carol", "internal")
    except StopIteration:
        sys.exit("Thiếu dữ liệu mẫu (lần chạy trước đã xóa tài liệu) – chạy lại seed: docker compose run --rm api python -m app.seed")
    health = call(None, "GET", "/health")[1]
    R3 = 200 if health["working_hours"] else 403
    print(f"(policy engine: {health['policy_engine']}; đang {'TRONG' if health['working_hours'] else 'NGOÀI'} giờ làm việc -> R3 kỳ vọng {R3}.")
    print(" R5 chỉ kiểm tra được nhánh IP nội bộ khi chạy trên cùng máy; nhánh IP ngoài có trong unit test OPA.)")

    print("\n# Kong (gateway) + Keycloak (token)")
    expect("không token -> Kong chặn", status(None, "GET", "/documents"), 401)
    expect("token bị sửa payload (chữ ký sai) -> Kong chặn", status(tamper(T["alice"]), "GET", "/documents"), 401)
    expect("health không cần token", status(None, "GET", "/health"), 200)

    print("\n# GET /documents/{id}")
    expect("R1 owner alice", status(T["alice"], "GET", f"/documents/{alice_doc}"), 200)
    expect("R2 IT manager (cùng phòng)", status(T["it.manager"], "GET", f"/documents/{alice_doc}"), 200)
    expect("admin", status(T["admin"], "GET", f"/documents/{alice_doc}"), 200)
    expect("bob (cùng phòng, không phải manager)", status(T["bob"], "GET", f"/documents/{alice_doc}"), 403)
    expect("R2 HR manager (khác phòng)", status(T["hr.manager"], "GET", f"/documents/{alice_doc}"), 403)
    expect("R3 owner đọc confidential", status(T["alice"], "GET", f"/documents/{alice_secret}"), R3)
    expect("R3 IT manager đọc confidential", status(T["it.manager"], "GET", f"/documents/{alice_secret}"), R3)
    expect("R3 admin đọc confidential", status(T["admin"], "GET", f"/documents/{alice_secret}"), R3)
    expect("bob đọc confidential của alice", status(T["bob"], "GET", f"/documents/{alice_secret}"), 403)

    print("\n# PUT /documents/{id}")
    expect("R1 owner alice", status(T["alice"], "PUT", f"/documents/{alice_doc}", {"title": "Alice edit"}), 200)
    expect("admin", status(T["admin"], "PUT", f"/documents/{alice_doc}", {"title": "Admin edit"}), 200)
    expect("IT manager", status(T["it.manager"], "PUT", f"/documents/{alice_doc}", {"title": "x"}), 403)
    expect("bob", status(T["bob"], "PUT", f"/documents/{alice_doc}", {"title": "x"}), 403)
    expect("owner đổi owner_id (mass assignment)", status(T["alice"], "PUT", f"/documents/{alice_doc}", {"owner_id": ID["bob"]}), 400)

    print("\n# DELETE /documents/{id}")
    expect("owner carol", status(T["carol"], "DELETE", f"/documents/{carol_doc}"), 403)
    expect("HR manager", status(T["hr.manager"], "DELETE", f"/documents/{carol_doc}"), 403)
    expect("R5 admin từ IP nội bộ", status(T["admin"], "DELETE", f"/documents/{carol_doc}"), 204)

    print("\n# GET /employees/{id}")
    expect("bản thân", status(T["alice"], "GET", f"/employees/{ID['alice']}"), 200)
    expect("IT manager xem alice", status(T["it.manager"], "GET", f"/employees/{ID['alice']}"), 200)
    expect("admin", status(T["admin"], "GET", f"/employees/{ID['alice']}"), 200)
    expect("bob xem alice", status(T["bob"], "GET", f"/employees/{ID['alice']}"), 403)
    expect("HR manager xem alice", status(T["hr.manager"], "GET", f"/employees/{ID['alice']}"), 403)

    print("\n# PATCH /employees/{id}")
    me = f"/employees/{ID['alice']}"
    expect("bản thân sửa phone", status(T["alice"], "PATCH", me, {"phone": "0900000000"}), 200)
    expect("R4 bản thân sửa role", status(T["alice"], "PATCH", me, {"role": "admin"}), 403)
    expect("R4 bản thân sửa salary", status(T["alice"], "PATCH", me, {"salary": 10**9}), 403)
    expect("bản thân sửa department", status(T["alice"], "PATCH", me, {"department": "HR"}), 403)
    expect("bản thân sửa trường lạ", status(T["alice"], "PATCH", me, {"isAdmin": True}), 403)
    expect("IT manager sửa alice", status(T["it.manager"], "PATCH", me, {"phone": "1"}), 403)
    expect("bob sửa alice", status(T["bob"], "PATCH", me, {"phone": "1"}), 403)
    expect("admin sửa salary của alice", status(T["admin"], "PATCH", me, {"salary": 26_000_000}), 200)
    expect("admin sửa role của alice (đồng bộ Keycloak)", status(T["admin"], "PATCH", me, {"role": "employee"}), 200)
    expect("R4 admin tự sửa salary", status(T["admin"], "PATCH", f"/employees/{ID['admin']}", {"salary": 1}), 403)
    expect("R4 admin tự sửa role", status(T["admin"], "PATCH", f"/employees/{ID['admin']}", {"role": "employee"}), 403)
    expect("R4 manager tự sửa salary", status(T["it.manager"], "PATCH", f"/employees/{ID['it.manager']}", {"salary": 1}), 403)

    print("\n# GET /departments/{id}/reports")
    expect("R6 IT manager - IT", status(T["it.manager"], "GET", "/departments/IT/reports"), 200)
    expect("R6 IT manager - HR", status(T["it.manager"], "GET", "/departments/HR/reports"), 403)
    expect("alice - IT", status(T["alice"], "GET", "/departments/IT/reports"), 403)
    expect("admin - HR", status(T["admin"], "GET", "/departments/HR/reports"), 200)

    print("\n# POST /admin/users")
    new_user = {"email": f"tmp{int(time.time())}@corp.local", "password": "Password123!", "fullName": "Người Dùng Tạm", "department": "IT"}
    expect("IT manager", status(T["it.manager"], "POST", "/admin/users", new_user), 403)
    expect("alice", status(T["alice"], "POST", "/admin/users", new_user), 403)
    expect("admin (tạo user trong Keycloak + Mongo)", status(T["admin"], "POST", "/admin/users", new_user), 201)
    try:
        new_token = login(new_user["email"])
        expect("user mới đăng nhập Keycloak được", status(new_token, "GET", "/auth/me"), 200)
    except Exception as exc:
        expect(f"user mới đăng nhập Keycloak được ({exc})", "error", 200)

    print("\n# GET /admin/audit")
    expect("IT manager", status(T["it.manager"], "GET", "/admin/audit"), 403)
    expect("alice", status(T["alice"], "GET", "/admin/audit"), 403)
    expect("admin", status(T["admin"], "GET", "/admin/audit"), 200)

    print("\n# Log schema")
    scenario = f"check-authz-{int(time.time())}"
    call(T["bob"], "GET", f"/documents/{alice_doc}", headers={"X-Scenario-Id": scenario})
    time.sleep(0.5)
    items = call(T["admin"], "GET", f"/admin/audit?scenario_id={scenario}")[1]["items"]
    log = items[0] if items else {}
    fields = ["timestamp", "request_id", "user_id", "role", "department", "ip", "method", "endpoint", "resource_id",
              "resource_owner_id", "http_status", "decision", "policy_rule", "latency_ms", "user_agent", "scenario_id"]
    expect("có đúng 1 bản ghi cho scenario_id", len(items), 1)
    expect("đủ trường", ",".join(f for f in fields if f not in log) or "đủ", "đủ")
    expect("decision", log.get("decision"), "deny")
    expect("policy_rule", log.get("policy_rule"), "DEFAULT_DENY")
    expect("http_status", log.get("http_status"), 403)
    expect("user_id = bob", log.get("user_id"), ID["bob"])
    expect("resource_owner_id = alice", log.get("resource_owner_id"), ID["alice"])

    print(f"\n{passed} PASS, {failed} FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
