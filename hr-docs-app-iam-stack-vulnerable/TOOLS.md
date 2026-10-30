> ⚠️ **BẢN VULNERABLE.** Tài liệu này mô tả KIẾN TRÚC (giống bản secure). Trong bản này một số chốt
> kiểm soát R1–R6/JWT đã bị cố ý làm yếu — xem [VULNERABILITIES.md](VULNERABILITIES.md) để biết chỗ nào.

# Công cụ nằm ở đâu trong ứng dụng

Bảng này ánh xạ từng lựa chọn trong bảng "So sánh lựa chọn công nghệ" sang file/cấu hình cụ thể trong
thư mục `hr-docs-app-iam-stack/`, kèm cách tận mắt thấy công cụ đó làm việc khi stack đang chạy.

## Đường đi của một request

```
Trình duyệt (React, :5173)
   │ 1. Đăng nhập OIDC Authorization Code + PKCE ───────────────► Keycloak (:8080)  realm hrdocs
   │ ◄─────────────────────── access token RS256 (realm role + claim department)
   │ 2. GET /api/documents/{id}  Authorization: Bearer <token>
   ▼
Kong (:8000)  plugin jwt (chữ ký, exp) · ip-restriction (R5) · correlation-id · rate-limiting · file-log
   │ 3. proxy, thêm X-Request-Id + X-Forwarded-For
   ▼
FastAPI (api:8000, không mở ra ngoài)  kiểm token lần 2 (iss, aud) → nạp tài nguyên từ MongoDB
   │ 4. POST /v1/data/hrdocs/authz/decision  {action, subject, resource, fields, env}
   ▼
OPA (:8181)  authz.rego → {"allow": false, "rule": "R2_DEPT_MANAGER"}   (+ decision log)
   │ 5. 200 / 403 + ghi 1 bản ghi log theo schema (Mongo audit_logs + access.jsonl)
   ▼
Grafana Alloy ── log FastAPI (file) + log Kong, OPA (stdout container) ──► Loki (:3100) ──► Grafana (:3000)
```

## Bảng tổng hợp

| Thành phần | Công cụ | Nằm ở đâu | Vai trò trong app |
|---|---|---|---|
| Ứng dụng mẫu | **FastAPI** | `api/app/` (vào: `api/app/main.py`), `api/Dockerfile`, service `api` trong `docker-compose.yml:70` | 8 endpoint của thiết kế API, gọi OPA để phân quyền, ghi log theo schema, tự sinh OpenAPI ở `/api/docs` |
| Identity Provider | **Keycloak** | `keycloak/realm-hrdocs.json`, service `keycloak` (`docker-compose.yml:14`), phía app: `api/app/security.py`, `api/app/keycloak_admin.py`, phía web: `frontend/src/keycloak.js` | Đăng nhập, phát JWT RS256 chứa realm role (admin/manager/employee) và phòng ban (group) |
| Policy Engine | **OPA (Rego)** | `policies/opa/hrdocs/authz.rego` + `authz_test.rego`, service `opa` (`docker-compose.yml:45`), phía app: `api/app/authz/opa_engine.py` | Ra quyết định RBAC + ABAC R1–R6, trả mã quy tắc cho `policy_rule`, ghi decision log |
| (dự phòng) | **Casbin** | `api/app/authz/casbin/model.conf`, `policy.csv`, `api/app/authz/casbin_engine.py`; bật bằng `POLICY_ENGINE=casbin` | Cùng input, cùng mã quy tắc; `api/tests/test_policy_parity.py` chứng minh hai engine cho kết quả giống hệt |
| API Gateway | **Kong** | `kong/kong.template.yml` → `config-init/render.py` sinh `kong.yml`; service `kong` (`docker-compose.yml:95`) | Cửa vào duy nhất: kiểm JWT, chặn IP ngoài cho xóa/admin (R5), gắn X-Request-Id, giới hạn tốc độ, ghi log HTTP JSON |
| Kho log | **Loki + Grafana** (thu bằng **Grafana Alloy**) | `observability/loki/loki-config.yml`, `observability/alloy/config.alloy`, `observability/grafana/…`, `scripts/export_logs.py` | Gom log 3 tầng (app, Kong, OPA), dashboard phân tích allow/deny theo quy tắc, xuất file JSON cho TV3 |

---

## 1. FastAPI – ứng dụng mẫu

| File | Nội dung |
|---|---|
| `api/app/main.py` | Tạo app, gắn middleware log, các router, handler lỗi `{error}`; `docs_url="/api/docs"`, `openapi_url="/api/openapi.json"` (dòng 41–42): OpenAPI tự sinh |
| `api/app/routers/documents.py` | `GET/PUT/DELETE /api/documents/{id}` (+ list, create). Mỗi handler gọi `authorize(...)` (dòng 59, 66, 78) |
| `api/app/routers/employees.py` | `GET/PATCH /api/employees/{id}`; PATCH gửi danh sách trường cho OPA (R4) rồi đồng bộ role/phòng ban sang Keycloak |
| `api/app/routers/departments.py` | `GET /api/departments/{id}/reports` (R6) |
| `api/app/routers/admin.py` | `POST /api/admin/users`, `GET /api/admin/audit`; `admin_guard` (dòng 16) áp `admin:access` (RBAC + R5) cho cả router |
| `api/app/authz/__init__.py` | **PEP** (điểm thực thi chính sách): `build_input` (dòng 23) dựng input cho OPA, `authorize` (dòng 64) gọi engine, ghi quyết định, trả 403/503 (fail closed) |
| `api/app/net.py` | Lấy IP client thật cho R5: chỉ tin `X-Forwarded-For` khi kết nối đến từ Kong (`TRUSTED_PROXY_CIDRS`) |
| `api/app/request_log.py` | Middleware ghi **log schema** (16 trường) vào Mongo `audit_logs` + `/var/log/hrdocs/access.jsonl` |
| `api/app/db_schema.py` | Lược đồ MongoDB: validator `$jsonSchema` + index cho 4 collection (thiết kế: [DATABASE.md](DATABASE.md)) |
| `api/app/seed.py`, `seed_data.py` | Dữ liệu mẫu; ID nhân viên = ID user Keycloak (`sub`) |
| `api/tests/` | 20 test pytest không cần Docker (mongomock + token tự ký) |

Xem tận mắt: http://localhost:8000/api/docs (Swagger UI qua Kong; bấm **Authorize**, dán access token).

## 2. Keycloak – Identity Provider

| File / chỗ | Nội dung |
|---|---|
| `keycloak/realm-hrdocs.json` | Realm `hrdocs` được import khi khởi động (`start-dev --import-realm`) |
| ↳ `"roles"` (dòng 19) | 3 **realm role**: `admin`, `manager`, `employee` → claim `realm_access.roles` |
| ↳ `"groups"` (dòng 35) | Group `IT`, `HR`, `SALES` = phòng ban → mapper `department (group)` (dòng 101) đưa vào claim `department` (thuộc tính ABAC) |
| ↳ mapper `audience hrdocs-api` (dòng 89) | Thêm `aud: hrdocs-api`; FastAPI từ chối token không dành cho API |
| ↳ client `hrdocs-web` (dòng 66) | Public client cho React, Authorization Code + PKCE S256 |
| ↳ client `hrdocs-cli` (dòng 118) | Password grant cho script kiểm thử / công cụ pentest (chỉ dùng trong lab) |
| ↳ client `hrdocs-backend` | Service account (realm-management: manage-users…) để API tạo user, đổi role/group |
| ↳ `bruteForceProtected`, `passwordPolicy`, `accessTokenLifespan: 300` | Khóa tạm khi đoán mật khẩu, mật khẩu ≥ 8 ký tự, token sống 5 phút |
| `api/app/security.py` | `decode_token` (dòng 32): kiểm RS256 bằng JWKS của realm + `iss` + `aud`; `principal_from_claims` (dòng 53) lấy role/phòng ban từ token |
| `api/app/keycloak_admin.py` | Gọi Keycloak Admin REST API: `create_user`, `set_role`, `set_department`, `set_enabled` |
| `frontend/src/keycloak.js`, `auth.jsx`, `api.js` | `keycloak-js`: đăng nhập/đăng xuất, tự làm mới token, gắn `Authorization: Bearer` |

Xem tận mắt: http://localhost:8080/admin (admin/admin) → realm **hrdocs** → Users / Realm roles / Groups / Clients.
Giải mã một token: `curl -s localhost:8080/realms/hrdocs/protocol/openid-connect/token -d grant_type=password -d client_id=hrdocs-cli -d username=alice -d password=Password123!` rồi dán vào jwt.io.

## 3. OPA – Policy Engine

| File / chỗ | Nội dung |
|---|---|
| `policies/opa/hrdocs/authz.rego` | Toàn bộ chính sách, tách khỏi mã nguồn app. Điểm vào: rule `decision` (dòng 109–149) |
| ↳ `document_read` (dòng 154) | R3 (confidential ngoài giờ → deny), admin, **R1** owner, **R2** manager cùng phòng |
| ↳ `document_update` (166) / `document_delete` (173) | R1 owner/admin; xóa: chỉ admin + **R5** IP nội bộ |
| ↳ `employee_read` (180) / `employee_update` (189) | Bản thân / manager cùng phòng / admin; **R4** không tự sửa role, salary; allowlist trường |
| ↳ `department_report` (205) | **R6** manager chỉ xem phòng ban mình quản lý |
| ↳ `admin_access` (215) | Admin + **R5** |
| ↳ `working_hours` (83), `internal_ip` (89) | Thuộc tính môi trường: `time.clock` theo múi giờ, `net.cidr_contains` |
| `policies/opa/hrdocs/authz_test.rego` | 26 unit test (`opa test policies/opa -v`), gồm cả nhánh ngoài giờ và IP ngoài |
| `/generated/opa/data.json` (volume, do `config-init/render.py` sinh) | `data.hrdocs.config`: giờ làm việc, múi giờ, dải IP nội bộ lấy từ `.env` |
| `docker-compose.yml:45` service `opa` | `--set=decision_logs.console=true` (**decision log**), `--watch` (sửa .rego là nạp lại ngay) |
| `api/app/authz/opa_engine.py` | Client gọi `POST /v1/data/hrdocs/authz/decision` |

Xem tận mắt:
```bash
curl -s localhost:8181/v1/data/hrdocs/authz/decision -d '{"input":{"action":"department:report","subject":{"id":"m1","role":"manager","department":"IT"},"resource":{"id":"HR","department":"HR","manager_id":"m2"},"fields":[],"env":{"ip":"10.0.0.1","now_ns":0}}}'
# {"decision_id":"…","result":{"allow":false,"rule":"R6_DEPT_REPORT"}}
docker compose logs -f opa      # decision log: input, result, decision_id
```

## 4. Kong – API Gateway

| File / chỗ | Nội dung |
|---|---|
| `kong/kong.template.yml` | Cấu hình khai báo (DB-less). `config-init` điền public key realm + dải IP rồi ghi `kong.yml` |
| ↳ route `api-public` | `/api/health`, `/api/docs`, `/api/openapi.json` không cần token |
| ↳ route `api` + plugin **jwt** (dòng 22) | Mọi `/api/*` khác: kiểm chữ ký RS256 bằng public key Keycloak, kiểm `exp`; consumer `keycloak-realm-hrdocs` (`jwt_secrets`, dòng 52) có `key` = issuer |
| ↳ route `api-admin` (dòng 32), `api-document-delete` (dòng 44) + plugin **ip-restriction** (dòng 39) | R5 ở tầng gateway (lớp phòng thủ thứ nhất; OPA là lớp thứ hai) |
| ↳ plugin **correlation-id** (dòng 60) | Sinh `X-Request-Id`; FastAPI dùng lại làm `request_id` để nối log Kong ↔ log app |
| ↳ plugin **file-log** (dòng 67) | Log HTTP dạng JSON ra stdout (bỏ header Authorization/Cookie) → Alloy → Loki |
| ↳ plugin **rate-limiting** (dòng 75) | 600 request/phút/IP |
| `config-init/render.py` | Chờ Keycloak, lấy `public_key` của realm, sinh `kong.yml` và `opa/data.json` |
| `docker-compose.yml:95` service `kong` | `KONG_DATABASE=off`, mạng cố định `172.30.0.10` (API chỉ tin XFF từ IP này), Admin API chỉ ở `127.0.0.1:8001` |

Xem tận mắt: `curl localhost:8001/routes`, `curl localhost:8001/plugins`; gọi `curl -i localhost:8000/api/documents` không token → `401 Unauthorized` do Kong trả (chưa tới FastAPI).

## 5. Loki + Grafana – kho log

| File / chỗ | Nội dung |
|---|---|
| `observability/alloy/config.alloy` | **Grafana Alloy** (bộ thu log): `job="hrdocs-api"` đọc `access.jsonl`, gắn nhãn `decision`, `policy_rule`, `method`; `job="kong"`, `job="opa"` đọc stdout container có label `hrdocs.logs=true` |
| `observability/loki/loki-config.yml` | Loki single-binary, lưu filesystem, giữ 30 ngày |
| `observability/grafana/provisioning/datasources/loki.yml` | Datasource Loki tự cấu hình |
| `observability/grafana/dashboards/hrdocs-authz.json` | Dashboard **HR Docs – AuthZ & Access Logs**: allow/deny theo thời gian, số lần deny theo `policy_rule`, mã HTTP tại Kong, quyết định OPA, log theo `scenario_id` |
| `scripts/export_logs.py` | **Xuất file JSON cho TV3** từ Loki: `--scenario S1 --out s1.json`, `--job kong|opa`, `--jsonl` |
| `api/app/request_log.py` | Nơi sinh bản ghi log đúng schema (nguồn của `job="hrdocs-api"`) |

Xem tận mắt: http://localhost:3000 (admin/admin) → Dashboards → HR Docs → **HR Docs – AuthZ & Access Logs**;
hoặc Explore với `{job="hrdocs-api", decision="deny"} | json | scenario_id="S1"`.

---

## 6 quy tắc ABAC được thực thi ở đâu

| Quy tắc | OPA (`authz.rego`) | Casbin (`policy.csv`) | Kong | Endpoint gọi |
|---|---|---|---|---|
| R1 owner đọc/sửa tài liệu của mình | `document_read`, `document_update` (`is_owner`) | dòng `R1_OWNER` | – | `documents.py` GET/PUT |
| R2 manager đọc tài liệu cùng phòng | `document_read` (`dept_manager`) | `R2_DEPT_MANAGER` | – | `documents.py` GET |
| R3 confidential chỉ trong 08:00–18:00 | `document_read` (`working_hours`) | `R3_CONFIDENTIAL_HOURS` | – | `documents.py` GET |
| R4 không tự sửa role/salary | `employee_update` (`touches_protected`) | `R4_NO_SELF_ROLE_SALARY` | – | `employees.py` PATCH |
| R5 xóa + quản trị chỉ từ IP nội bộ | `document_delete`, `admin_access` (`internal_ip`) | `R5_INTERNAL_IP` | `ip-restriction` trên `api-admin`, `api-document-delete` | `documents.py` DELETE, `admin.py` |
| R6 manager không xem báo cáo phòng khác | `department_report` | `R6_DEPT_REPORT` | – | `departments.py` |

Thuộc tính lấy từ đâu: **subject** (id, role, department) từ token Keycloak · **resource** (owner_id, department,
classification, manager_id) từ MongoDB · **environment** (ip từ Kong, giờ hiện tại) do FastAPI đo; tham số
(giờ làm việc, múi giờ, dải IP) từ `.env` qua `config-init`.

## Log schema được ghi ở đâu

`api/app/request_log.py` ghi đúng các trường đã chốt: `timestamp, request_id, user_id, role, department, ip,
method, endpoint, resource_id, resource_owner_id, http_status, decision, policy_rule, latency_ms, user_agent,
scenario_id` (chỉ khi request có header `X-Scenario-Id`). Nguồn giá trị: `user_id/role/department` từ token
Keycloak, `request_id` từ Kong, `decision/policy_rule` từ OPA, `ip` từ Kong (`X-Forwarded-For`).
