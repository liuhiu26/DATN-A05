"""Gọi Keycloak Admin REST API bằng service account của client `hrdocs-backend`
(client credentials; realm-management: manage-users, view-users, query-groups, view-realm).

Dùng khi admin tạo tài khoản (POST /api/admin/users) hoặc đổi role / phòng ban / khóa tài khoản,
để Keycloak (nơi phát token) luôn khớp với hồ sơ trong Mongo.
"""
import time

import httpx

from . import config
from .errors import HttpError

APP_ROLES = ("admin", "manager", "employee")


class KeycloakAdmin:
    def __init__(self):
        self.base = f"{config.KEYCLOAK_URL}/admin/realms/{config.KEYCLOAK_REALM}"
        self.http = httpx.Client(timeout=10)
        self._token = None
        self._token_exp = 0.0

    def _auth(self) -> dict:
        if not self._token or time.time() > self._token_exp - 30:
            res = self.http.post(
                f"{config.KEYCLOAK_URL}/realms/{config.KEYCLOAK_REALM}/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": config.KEYCLOAK_ADMIN_CLIENT_ID,
                    "client_secret": config.KEYCLOAK_ADMIN_CLIENT_SECRET,
                },
            )
            self._check(res, "service account login")
            body = res.json()
            self._token, self._token_exp = body["access_token"], time.time() + body.get("expires_in", 60)
        return {"Authorization": f"Bearer {self._token}"}

    @staticmethod
    def _check(res: httpx.Response, what: str):
        if res.status_code == 409:
            raise HttpError(409, "User already exists in Keycloak")
        if res.status_code >= 400:
            raise HttpError(502, f"Keycloak {what} failed ({res.status_code})")

    def _req(self, method: str, path: str, what: str, **kw) -> httpx.Response:
        res = self.http.request(method, self.base + path, headers=self._auth(), **kw)
        self._check(res, what)
        return res

    @staticmethod
    def split_name(full_name: str) -> tuple[str, str]:
        """'Nguyễn Thị An' -> firstName 'An', lastName 'Nguyễn Thị' (Keycloak yêu cầu đủ 2 trường)."""
        parts = full_name.split()
        return (parts[-1], " ".join(parts[:-1]) or parts[-1]) if parts else ("-", "-")

    def create_user(self, *, email: str, password: str, full_name: str, role: str, department: str | None) -> str:
        first, last = self.split_name(full_name)
        rep = {
            "username": email, "email": email, "emailVerified": True, "enabled": True,
            "firstName": first, "lastName": last,
            "credentials": [{"type": "password", "value": password, "temporary": False}],
        }
        res = self._req("POST", "/users", "create user", json=rep)
        user_id = res.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        try:
            self.set_role(user_id, role)
            self.set_department(user_id, department)
        except HttpError:
            self.delete_user(user_id)
            raise
        return user_id

    def delete_user(self, user_id: str):
        self.http.delete(f"{self.base}/users/{user_id}", headers=self._auth())

    def set_role(self, user_id: str, role: str):
        current = self._req("GET", f"/users/{user_id}/role-mappings/realm", "read roles").json()
        stale = [r for r in current if r["name"] in APP_ROLES and r["name"] != role]
        if stale:
            self._req("DELETE", f"/users/{user_id}/role-mappings/realm", "remove role", json=stale)
        if not any(r["name"] == role for r in current):
            rep = self._req("GET", f"/roles/{role}", "read role").json()
            self._req("POST", f"/users/{user_id}/role-mappings/realm", "add role", json=[rep])

    def set_department(self, user_id: str, department: str | None):
        for g in self._req("GET", f"/users/{user_id}/groups", "read groups").json():
            if g["name"] != department:
                self._req("DELETE", f"/users/{user_id}/groups/{g['id']}", "leave group")
        if department:
            groups = self._req("GET", "/groups", "find group", params={"search": department, "exact": "true"}).json()
            group = next((g for g in groups if g["name"] == department), None)
            if group is None:
                raise HttpError(502, f"Keycloak group {department} not found")
            self._req("PUT", f"/users/{user_id}/groups/{group['id']}", "join group")

    def set_enabled(self, user_id: str, enabled: bool):
        rep = self._req("GET", f"/users/{user_id}", "read user").json()
        rep["enabled"] = enabled
        self._req("PUT", f"/users/{user_id}", "update user", json=rep)


_admin: KeycloakAdmin | None = None


def get_admin() -> KeycloakAdmin:
    global _admin
    if _admin is None:
        _admin = KeycloakAdmin()
    return _admin


def set_admin(admin) -> None:
    global _admin
    _admin = admin
