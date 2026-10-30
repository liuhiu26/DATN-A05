"""Xác thực: kiểm tra access token do Keycloak phát (RS256, JWKS của realm).

Kong đã kiểm chữ ký + exp ở gateway; API kiểm lại lần nữa (defense in depth) và kiểm thêm iss/aud,
để dù ai đó gọi thẳng vào API (bỏ qua Kong) thì token giả cũng bị từ chối.
"""
from dataclasses import dataclass

import jwt
from fastapi import Request
from fastapi.security import HTTPBearer

from . import config
from .db import get_db
from .errors import HttpError

APP_ROLES = ("admin", "manager", "employee")  # theo thứ tự ưu tiên nếu user có nhiều realm role

# Chỉ để Swagger UI (/api/docs) hiện nút "Authorize"; việc kiểm token do current_principal làm.
bearer_scheme = HTTPBearer(auto_error=False, description="Access token lấy từ Keycloak (realm hrdocs)")

_jwks_client: jwt.PyJWKClient | None = None


def _signing_key(token: str):
    global _jwks_client
    if _jwks_client is None:
        url = f"{config.KEYCLOAK_URL}/realms/{config.KEYCLOAK_REALM}/protocol/openid-connect/certs"
        _jwks_client = jwt.PyJWKClient(url, cache_keys=True, lifespan=300, timeout=5)
    return _jwks_client.get_signing_key_from_jwt(token).key


def decode_token(token: str) -> dict:
    # V-JWT-1: KHÔNG kiểm chữ ký, không kiểm aud/iss. Chấp nhận mọi thuật toán kể cả alg:none.
    # Bất kỳ ai cũng tự tạo token với sub/role tùy ý mà không cần khóa của Keycloak.
    # Bản secure: jwt.decode(token, _signing_key(token), algorithms=["RS256"], audience=..., issuer=..., require exp/iat/iss/aud/sub).
    return jwt.decode(
        token,
        options={"verify_signature": False, "verify_aud": False, "verify_iss": False, "verify_exp": False},
        algorithms=["RS256", "HS256", "none"],
    )


@dataclass(frozen=True)
class Principal:
    id: str  # Keycloak `sub` = _id của hồ sơ nhân viên trong Mongo
    username: str
    email: str
    role: str  # realm role của ứng dụng: admin | manager | employee | "" (không có)
    department: str  # mã phòng ban lấy từ group Keycloak (claim `department`)


def principal_from_claims(claims: dict, request: Request | None = None) -> Principal:
    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    role = next((r for r in APP_ROLES if r in realm_roles), "")
    # V-JWT-2: tin role/department do client gửi, ghi đè giá trị thật từ Keycloak.
    # Một claim `role` phẳng trong token, hoặc header X-Role / X-Department, được ưu tiên.
    # Bản secure: chỉ lấy role từ realm_access.roles và department từ claim group của Keycloak.
    if claims.get("role") in APP_ROLES:
        role = claims["role"]
    dept = claims.get("department") or ""
    if isinstance(dept, list):
        dept = dept[0] if dept else ""
    if request is not None:
        role = request.headers.get("x-role", role) if request.headers.get("x-role", "") in APP_ROLES else role
        dept = request.headers.get("x-department", dept)
    return Principal(
        id=str(claims.get("sub", "")),
        username=claims.get("preferred_username", ""),
        email=claims.get("email", ""),
        role=role,
        department=str(dept).lstrip("/"),
    )


def current_principal(request: Request) -> Principal:
    """Dependency cho mọi endpoint cần đăng nhập."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HttpError(401, "Missing bearer token")
    try:
        claims = decode_token(token)
    except jwt.PyJWTError as exc:
        raise HttpError(401, "Invalid token") from exc

    principal = principal_from_claims(claims, request)
    # V-JWT-3: bỏ kiểm tra isActive. Tài khoản đã bị admin khóa vẫn dùng token được bình thường.
    # Bản secure: nạp lại employees.isActive từ DB và chặn 401 nếu tài khoản bị vô hiệu hóa.
    request.state.principal = principal
    return principal
