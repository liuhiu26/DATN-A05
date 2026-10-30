"""Cấu hình đọc từ biến môi trường (.env ở thư mục gốc khi chạy docker compose, hoặc api/.env khi chạy tay)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _list(name: str, default: str) -> list[str]:
    return [s.strip() for s in os.getenv(name, default).split(",") if s.strip()]


PRIVATE_CIDRS = "127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

# MongoDB (Hiếu dùng Mongo server riêng: chỉ cần trỏ MONGO_URI)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "hr_docs_iam")

# Keycloak (Identity Provider)
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")  # địa chỉ API gọi tới (mạng nội bộ docker)
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "hrdocs")
# `iss` trong token: phải khớp KC_HOSTNAME mà trình duyệt dùng để đăng nhập.
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER", "http://localhost:8080/realms/hrdocs")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "hrdocs-api")
KEYCLOAK_ADMIN_CLIENT_ID = os.getenv("KEYCLOAK_ADMIN_CLIENT_ID", "hrdocs-backend")
KEYCLOAK_ADMIN_CLIENT_SECRET = os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET", "")

# Policy engine: "opa" (mặc định) hoặc "casbin" (phương án dự phòng)
POLICY_ENGINE = os.getenv("POLICY_ENGINE", "opa").lower()
OPA_URL = os.getenv("OPA_URL", "http://opa:8181/v1/data/hrdocs/authz/decision")
OPA_TIMEOUT_S = float(os.getenv("OPA_TIMEOUT_S", "2"))

# Tham số ABAC – Casbin dùng trực tiếp; OPA nhận cùng giá trị qua data.json do config-init sinh.
WORK_HOURS_START = os.getenv("WORK_HOURS_START", "08:00")
WORK_HOURS_END = os.getenv("WORK_HOURS_END", "18:00")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh")
INTERNAL_CIDRS = _list("INTERNAL_CIDRS", PRIVATE_CIDRS)

# Chỉ tin X-Forwarded-For / X-Request-Id khi kết nối đến từ các địa chỉ này (Kong).
TRUSTED_PROXY_CIDRS = _list("TRUSTED_PROXY_CIDRS", "127.0.0.1/32")

# Log theo schema: ghi Mongo (collection audit_logs, phục vụ GET /admin/audit) + file JSON Lines (Alloy đẩy sang Loki).
ACCESS_LOG_FILE = os.getenv("ACCESS_LOG_FILE", "./logs/access.jsonl")
