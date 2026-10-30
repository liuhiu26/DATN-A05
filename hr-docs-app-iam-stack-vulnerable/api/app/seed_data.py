"""Dữ liệu mẫu dùng chung cho seed Mongo. ID nhân viên = ID user trong keycloak/realm-hrdocs.json
(Keycloak `sub`), nên token của ai thì khớp đúng hồ sơ người đó. Mật khẩu chung: Password123!"""

DEPARTMENTS = [
    {"_id": "IT", "code": "IT", "name": "Công nghệ thông tin", "manager": "it.manager"},
    {"_id": "HR", "code": "HR", "name": "Nhân sự", "manager": "hr.manager"},
    {"_id": "SALES", "code": "SALES", "name": "Kinh doanh", "manager": "sales.manager"},
]

# username, keycloak id, họ tên, role, phòng ban, chức danh, lương
USERS = [
    ("admin", "a0000000-0000-4000-8000-000000000001", "Quản Trị Viên", "admin", None, "System Administrator", 50_000_000),
    ("it.manager", "a0000000-0000-4000-8000-000000000002", "Trần Văn Minh", "manager", "IT", "IT Manager", 40_000_000),
    ("alice", "a0000000-0000-4000-8000-000000000003", "Nguyễn Thị An", "employee", "IT", "Backend Developer", 25_000_000),
    ("bob", "a0000000-0000-4000-8000-000000000004", "Lê Văn Bình", "employee", "IT", "Frontend Developer", 22_000_000),
    ("hr.manager", "a0000000-0000-4000-8000-000000000005", "Phạm Thu Hà", "manager", "HR", "HR Manager", 38_000_000),
    ("carol", "a0000000-0000-4000-8000-000000000006", "Hoàng Minh Châu", "employee", "HR", "HR Specialist", 18_000_000),
    ("sales.manager", "a0000000-0000-4000-8000-000000000007", "Đỗ Quang Dũng", "manager", "SALES", "Sales Manager", 42_000_000),
    ("dave", "a0000000-0000-4000-8000-000000000008", "Vũ Đức Duy", "employee", "SALES", "Sales Executive", 15_000_000),
]

# owner username, tiêu đề, nội dung, phân loại
DOCUMENTS = [
    ("alice", "Kiến trúc hệ thống thanh toán", "Sơ đồ service, DB, queue...", "internal"),
    ("alice", "Đánh giá hiệu suất Q3 - Alice", "Tự đánh giá: hoàn thành 95% KPI.", "confidential"),
    ("bob", "Hướng dẫn build frontend", "npm ci && npm run build", "internal"),
    ("it.manager", "Kế hoạch tuyển dụng IT 2026", "Tuyển 3 backend, 1 devops.", "confidential"),
    ("carol", "Quy trình onboarding", "Ngày 1: nhận thiết bị, ký hợp đồng...", "internal"),
    ("hr.manager", "Bảng lương tháng 9", "Chi tiết lương toàn công ty.", "confidential"),
    ("dave", "Danh sách khách hàng tiềm năng", "Công ty A, B, C...", "confidential"),
    ("admin", "Chính sách bảo mật nội bộ", "Mật khẩu tối thiểu 12 ký tự...", "internal"),
]

PASSWORD = "Password123!"
