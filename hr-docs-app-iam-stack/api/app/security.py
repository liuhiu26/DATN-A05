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
    return jwt.decode(
        token,
        _signing_key(token),
        algorithms=["RS256"],
        audience=config.JWT_AUDIENCE,
        issuer=config.KEYCLOAK_ISSUER,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        leeway=10,
    )


@dataclass(frozen=True)
class Principal:
    id: str  # Keycloak `sub` = _id của hồ sơ nhân viên trong Mongo
    username: str
    email: str
    role: str  # realm role của ứng dụng: admin | manager | employee | "" (không có)
    department: str  # mã phòng ban lấy từ group Keycloak (claim `department`)


def principal_from_claims(claims: dict) -> Principal:
    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    role = next((r for r in APP_ROLES if r in realm_roles), "")
    dept = claims.get("department") or ""
    if isinstance(dept, list):
        dept = dept[0] if dept else ""
    return Principal(
        id=str(claims["sub"]),
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
    except jwt.PyJWKClientError as exc:
        raise HttpError(503, "Cannot fetch Keycloak signing keys") from exc
    except jwt.PyJWTError as exc:
        raise HttpError(401, "Invalid or expired token") from exc

    principal = principal_from_claims(claims)
    # Tài khoản bị admin khóa trong hồ sơ (isActive=false) thì token còn hạn cũng không dùng được.
    profile = get_db().employees.find_one({"_id": principal.id}, {"isActive": 1})
    if profile is not None and not profile.get("isActive", True):
        raise HttpError(401, "Account disabled")

    request.state.principal = principal
    return principal
