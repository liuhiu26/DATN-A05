# Thiết kế cơ sở dữ liệu – HR Docs (stack FastAPI · Keycloak · OPA)

Cơ sở dữ liệu nghiệp vụ là **MongoDB** (database mặc định `hr_docs_iam`, đặt bằng `MONGO_DB`), chạy trên
Mongo server riêng của bạn. Thông tin đăng nhập **không** nằm trong Mongo mà ở **Keycloak**. Log thì có
hai bản: Mongo `audit_logs` (cho trang Audit log) và **Loki** (cho phân tích, xuất JSON).

| Collection | Vai trò | Khóa chính | Số bản ghi mẫu |
|---|---|---|---|
| `departments` | Phòng ban (thuộc tính ABAC của subject và resource) | `_id` = mã phòng ban `IT`, `HR`, `SALES` | 3 |
| `employees` | Hồ sơ nhân viên (= user của ứng dụng) | `_id` = Keycloak user id (`sub`) | 8 |
| `documents` | Tài liệu nội bộ | `_id` = ObjectId | 8 |
| `audit_logs` | Log mỗi request theo schema chốt với TV3 | `_id` = ObjectId | tăng theo request |

Code: lược đồ (validator + index) ở `api/app/db_schema.py`; quyền user DB ở `scripts/mongo-init.js`;
kiểm thử trên Mongo thật ở `api/tests/test_db_schema.py`.

## 1. Sơ đồ quan hệ

```mermaid
erDiagram
    KEYCLOAK_USER ||--|| employees : "sub = _id"
    KEYCLOAK_GROUP ||--|| departments : "tên group = _id"
    departments ||--o{ employees : "department_id"
    employees |o--o| departments : "manager_id (trưởng phòng)"
    employees ||--o{ documents : "owner_id"
    departments ||--o{ documents : "department_id"
    employees ||--o{ audit_logs : "user_id (không ràng buộc)"

    departments { string _id PK "IT" string code string name string manager_id FK }
    employees { string _id PK "Keycloak sub" string email UK string username UK string fullName string role string department_id FK long salary bool isActive }
    documents { ObjectId _id PK string title string content string classification string owner_id FK string department_id FK }
    audit_logs { ObjectId _id PK date timestamp string request_id string user_id string decision string policy_rule }
```

```
 Keycloak (realm hrdocs)                         MongoDB (hr_docs_iam)
 ┌─────────────────────┐   sub = _id        ┌──────────────────────┐  department_id  ┌──────────────┐
 │ user                │───────────────────►│ employees            │────────────────►│ departments  │
 │  realm role         │  (bản sao: role)   │  role, department_id │◄────────────────│  manager_id  │
 │  group IT/HR/SALES  │  (bản sao: dept)   │  salary, isActive    │   manager_id     └──────────────┘
 │  enabled            │  (bản sao: active) └──────────┬───────────┘                        ▲
 └─────────────────────┘                     owner_id  │                                    │ department_id
                                                       ▼                                    │
                                            ┌──────────────────────┐────────────────────────┘
                                            │ documents            │
                                            └──────────────────────┘
                                            ┌──────────────────────┐  user_id, resource_id, resource_owner_id
                                            │ audit_logs           │  chỉ là giá trị ghi lại, không ràng buộc
                                            └──────────────────────┘
```

Vì sao dùng chuỗi (`"IT"`, UUID của Keycloak) làm `_id` thay vì ObjectId: chính các giá trị này nằm trong token
(`sub`, claim `department`) và trong input gửi OPA, nên app so sánh thẳng `subject.id == resource.owner_id`,
`subject.department == resource.department` mà không cần tra bảng ánh xạ.

## 2. Chi tiết từng collection

Ký hiệu: **B** = bắt buộc · **KC** = bản sao từ Keycloak (Keycloak là nguồn sự thật) · **ABAC** = được dùng làm
thuộc tính trong chính sách OPA.

### 2.1 `departments`

| Trường | Kiểu | B | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `_id` | string | ✓ | `^[A-Z][A-Z0-9_]{1,15}$` | Mã phòng ban, trùng tên group Keycloak. **ABAC**: `resource.department` của báo cáo (R6) |
| `code` | string | ✓ | như `_id` | Hiển thị |
| `name` | string | ✓ | 1–120 ký tự | "Công nghệ thông tin" |
| `manager_id` | string \| null | | UUID → `employees._id` | Trưởng phòng. **ABAC** R6: manager chỉ xem báo cáo khi đúng là `manager_id` |
| `createdAt`, `updatedAt` | date | | | |

```json
{ "_id": "IT", "code": "IT", "name": "Công nghệ thông tin", "manager_id": "a0000000-0000-4000-8000-000000000002" }
```

### 2.2 `employees`

| Trường | Kiểu | B | Ràng buộc | Ai được sửa (R4) | Ghi chú |
|---|---|---|---|---|---|
| `_id` | string | ✓ | UUID Keycloak | – | = `sub` trong token. **ABAC** `subject.id`, `resource.id` |
| `username` | string | | duy nhất (nếu có) | – | Username Keycloak (user tạo qua admin: = email) |
| `email` | string | ✓ | duy nhất, có `@` | – | KC |
| `fullName` | string | ✓ | 1–120 | bản thân, admin | |
| `role` | `employee`\|`manager`\|`admin` | ✓ | enum | **chỉ admin, không tự sửa** | KC (realm role). Hiển thị; quyết định phân quyền lấy role từ token |
| `department_id` | string \| null | | → `departments._id` | chỉ admin | KC (group). **ABAC** `resource.department` khi manager xem hồ sơ |
| `position` | string \| null | | ≤ 120 | chỉ admin | |
| `phone`, `address` | string \| null | | ≤ 30 / ≤ 300 | bản thân, admin | |
| `salary` | int/long | | ≥ 0, VNĐ | **chỉ admin, không tự sửa** | Dữ liệu nhạy cảm nhất; lộ qua `GET /employees/{id}` và báo cáo phòng ban |
| `isActive` | bool | ✓ | | chỉ admin | KC (`enabled`). `false` thì token còn hạn cũng bị từ chối |
| `createdAt`, `updatedAt` | date | ✓ | | – | |

`additionalProperties: false`: trường lạ như `isAdmin`, `passwordHash` bị chính MongoDB từ chối, kể cả khi
lớp phân quyền của app có lỗ hổng mass assignment.

### 2.3 `documents`

| Trường | Kiểu | B | Ràng buộc | Ghi chú |
|---|---|---|---|---|
| `_id` | ObjectId | ✓ | | Lộ trên URL `/api/documents/{id}` (đối tượng thử IDOR) |
| `title` | string | ✓ | 1–200 | |
| `content` | string | | ≤ 100 000 | Không trả trong danh sách, chỉ trả ở `GET /documents/{id}` |
| `classification` | `internal`\|`confidential` | ✓ | enum | **ABAC** R3 |
| `owner_id` | string | ✓ | UUID → `employees._id` | **ABAC** R1. Gán = người tạo; client không sửa được |
| `department_id` | string \| null | | → `departments._id` | **ABAC** R2. Chụp phòng ban của chủ sở hữu **lúc tạo**; nhân viên chuyển phòng thì tài liệu cũ vẫn thuộc phòng cũ |
| `createdAt`, `updatedAt` | date | ✓ | | |

### 2.4 `audit_logs`

Đúng log schema đã chốt: `timestamp, request_id, user_id, role, department, ip, method, endpoint, resource_id,
resource_owner_id, http_status, decision, policy_rule, latency_ms, user_agent, scenario_id`.

| Trường | Kiểu | Nguồn giá trị |
|---|---|---|
| `timestamp` | date (UTC) | FastAPI |
| `request_id` | string | `X-Request-Id` do Kong sinh (nối với log Kong trong Loki) |
| `user_id`, `role`, `department` | string \| null | Token Keycloak |
| `ip` | string | Kong (`X-Forwarded-For` phần tử cuối) |
| `method`, `endpoint`, `http_status`, `latency_ms`, `user_agent` | | FastAPI |
| `resource_id`, `resource_owner_id` | string \| null | Tài nguyên app nạp từ Mongo |
| `decision` | `allow`\|`deny` | OPA |
| `policy_rule` | string \| null | OPA (`R1_OWNER`, `R3_CONFIDENTIAL_HOURS`, …) |
| `scenario_id` | string (≤128) | Header `X-Scenario-Id`; **chỉ có ở log tấn công** (không có trường khi không gửi) |

Các id trong log chỉ là giá trị ghi lại, không ràng buộc khóa ngoại: log phải giữ nguyên kể cả khi tài liệu
đã bị xóa.

## 3. Toàn vẹn tham chiếu

MongoDB không có khóa ngoại, nên app tự kiểm:

| Tham chiếu | Kiểm ở đâu |
|---|---|
| `employees.department_id → departments` | `routers/employees.py` (PATCH) và `routers/admin.py` (tạo user): phòng ban phải tồn tại, nếu không thì 400 |
| `documents.owner_id → employees` | Luôn gán từ token của người tạo (`routers/documents.py`); không có endpoint đổi owner |
| `documents.department_id → departments` | Lấy từ token người tạo |
| `departments.manager_id → employees` | Chỉ do seed gán; chưa có endpoint đổi trưởng phòng |
| Xóa nhân viên | Không có endpoint; khóa bằng `isActive=false` để giữ lịch sử tài liệu và log |

## 4. Đồng bộ với Keycloak

| Dữ liệu | Nguồn sự thật | Bản sao trong Mongo | Khi nào đồng bộ |
|---|---|---|---|
| Mật khẩu, MFA, khóa do brute force | Keycloak | – | Không bao giờ vào Mongo |
| User id | Keycloak (`id`/`sub`) | `employees._id` | Lúc tạo |
| Realm role | Keycloak | `employees.role` | Admin PATCH `role` → `KeycloakAdmin.set_role` rồi mới ghi Mongo |
| Phòng ban | Keycloak group | `employees.department_id` | Admin PATCH `department` → `set_department` |
| Kích hoạt | Keycloak `enabled` | `employees.isActive` | Admin PATCH `isActive` → `set_enabled` |
| Hồ sơ, lương, tài liệu | Mongo | – | – |

Các luồng chính:

1. **Seed** (`python -m app.seed`): `keycloak/realm-hrdocs.json` khai báo user với id cố định
   `a0000000-…-0001` → `…-0008`; `app/seed_data.py` dùng đúng các id đó.
2. **Admin tạo user** (`POST /api/admin/users`): tạo trong Keycloak trước (user, mật khẩu, realm role, group) và
   lấy id. Sau đó insert `employees` với `_id` = id đó. Nếu insert Mongo lỗi thì xóa user Keycloak (bù trừ).
3. **Admin đổi role/phòng ban/khóa**: Keycloak trước, Mongo sau. Keycloak lỗi thì trả 502 và Mongo không đổi.
4. **Khi phân quyền**: role và phòng ban lấy từ **token**, không lấy từ Mongo. Token sống 5 phút nên role mới có
   hiệu lực chậm tối đa 5 phút; riêng `isActive=false` được kiểm trên Mongo ở mỗi request nên có hiệu lực ngay.

Lệch dữ liệu có thể xảy ra nếu ai đó sửa thẳng trong Keycloak admin console. Khi đó quyền theo Keycloak (token),
còn Mongo chỉ hiển thị sai. Đây cũng là một tình huống đáng thử trong lab.

## 5. Index

Mỗi index phục vụ một truy vấn cụ thể. `api/tests/test_db_schema.py` dùng `explain()` để chứng minh truy vấn
chạy bằng đúng index (không COLLSCAN).

| Collection | Index | Truy vấn / endpoint | Quy tắc |
|---|---|---|---|
| employees | `email_unique` `{email:1}` unique | Chống trùng email khi tạo user | |
| employees | `username_unique` `{username:1}` unique, partial | Chống trùng username | |
| employees | `department_fullName` `{department_id:1, fullName:1}` | `GET /employees` của manager; báo cáo phòng ban | R2/R6 |
| employees | `fullName` `{fullName:1}` | `GET /employees` của admin (sắp xếp) | |
| documents | `owner_updatedAt` `{owner_id:1, updatedAt:-1}` | `GET /documents` của employee | R1 |
| documents | `department_updatedAt` `{department_id:1, updatedAt:-1}` | `GET /documents` của manager (`$or` owner/department dùng cả hai index) | R2 |
| documents | `department_classification` `{department_id:1, classification:1}` | Đếm tài liệu / tài liệu mật trong báo cáo | R3/R6 |
| departments | `manager_id` `{manager_id:1}` | Tra phòng ban của một trưởng phòng | R6 |
| audit_logs | `timestamp` `{timestamp:-1}` | `GET /admin/audit` không lọc | |
| audit_logs | `user_timestamp` `{user_id:1, timestamp:-1}` | Lọc theo user | |
| audit_logs | `decision_rule_timestamp` `{decision:1, policy_rule:1, timestamp:-1}` | Lọc deny theo quy tắc | R1–R6 |
| audit_logs | `scenario_timestamp` `{scenario_id:1, timestamp:-1}` partial (chỉ bản ghi có scenario_id) | Lọc log tấn công | |
| audit_logs | `request_id` `{request_id:1}` | Nối với log Kong / OPA | |

`_id` của mọi collection đã có index sẵn (tra `GET /…/{id}`). API tự tạo index khi khởi động
(`ensure_indexes`) và xóa index cũ của bản trước (`owner_id_1`, `department_id_1`, …).

## 6. Validator (`$jsonSchema`)

`api/app/db_schema.py` → `VALIDATORS`, áp với `validationLevel: strict`, `validationAction: error`. Đây là lớp
phòng thủ cuối cùng sau Kong → OPA → Pydantic. Validator chặn:

- Giá trị ngoài enum: `role: "superadmin"`, `classification: "secret"`, `decision: "maybe"`.
- Trường lạ: `isAdmin`, `owner`, `passwordHash` (`additionalProperties: false`).
- Sai định dạng: `_id` không phải UUID, mã phòng ban viết thường, email không có `@`, `salary < 0`.

Validator cần quyền `collMod`, nên được áp bằng tài khoản quản trị qua `python -m app.seed` (xóa và nạp lại dữ
liệu) hoặc `python -m app.db_setup` (giữ dữ liệu, chỉ áp validator và index).

## 7. Tài khoản DB tối thiểu quyền

`scripts/mongo-init.js` tạo role `hrdocsApp` và user `hrdocs_app` cho API:

| Collection | find | insert | update | remove |
|---|:-:|:-:|:-:|:-:|
| departments | ✓ | | | |
| employees | ✓ | ✓ | ✓ | |
| documents | ✓ | ✓ | ✓ | ✓ |
| audit_logs | ✓ | ✓ | | |

Ngoài ra có `createIndex`, `listIndexes`, `listCollections`. API **không** có quyền `collMod`, `dropCollection`,
xóa nhân viên hay sửa/xóa log. Vì vậy dù có NoSQL injection hay RCE trong API, kẻ tấn công cũng không xóa được
dấu vết trong `audit_logs` (đã kiểm: update/delete log, xóa nhân viên, drop collection, gỡ validator đều bị
Mongo từ chối).

## 8. Cài đặt trên Mongo server của bạn

```bash
# 1. Tạo role + user cho API (chạy bằng tài khoản admin của Mongo)
HRDOCS_DB_PASSWORD='mat-khau-manh' mongosh "mongodb://<admin>:<pass>@<host>:27017/admin" --file scripts/mongo-init.js

# 2. .env – API dùng user tối thiểu quyền
MONGO_URI=mongodb://hrdocs_app:mat-khau-manh@host.docker.internal:27017/hr_docs_iam?authSource=hr_docs_iam

# 3. Áp validator + index và nạp dữ liệu mẫu bằng tài khoản admin (seed XÓA dữ liệu cũ)
docker compose run --rm -e MONGO_URI="mongodb://<admin>:<pass>@host.docker.internal:27017/?authSource=admin" api python -m app.seed
#    hoặc chỉ áp validator + index, giữ dữ liệu:
docker compose run --rm -e MONGO_URI="mongodb://<admin>:<pass>@host.docker.internal:27017/?authSource=admin" api python -m app.db_setup
```

Mongo không bật xác thực (lab nhanh) vẫn chạy được với `MONGO_URI=mongodb://host.docker.internal:27017`, nhưng
khi đó mất lớp bảo vệ ở mục 7.

## 9. Vòng đời dữ liệu

- `audit_logs` tăng theo mỗi request. Loki giữ 30 ngày cho phân tích. Muốn Mongo tự xóa log cũ thì thêm TTL
  (ví dụ 90 ngày): `db.audit_logs.createIndex({timestamp: 1}, {expireAfterSeconds: 7776000, name: "timestamp_ttl"})`.
- Sao lưu: `mongodump --uri "<admin uri>" --db hr_docs_iam --out backup/`. Keycloak sao lưu riêng bằng
  `kc.sh export` (dữ liệu dev của Keycloak nằm trong container).
- Reset lab: chạy lại seed (xóa `departments`, `employees`, `documents`, `audit_logs` rồi nạp lại).

## 10. Kiểm thử

```bash
cd api
MONGO_TEST_URI=mongodb://localhost:27017 pytest tests/test_db_schema.py   # 22 test: validator, unique, index (explain)
```
