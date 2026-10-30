from fastapi import APIRouter, Depends, Request

from ..authz import authorize
from ..db import get_db
from ..security import Principal, current_principal
from ..serializers import dept_brief, employee_out

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", summary="Thông tin người đang đăng nhập (từ token Keycloak + hồ sơ Mongo)")
def me(request: Request, p: Principal = Depends(current_principal)):
    authorize(request, p, "profile:read", {"id": p.id, "owner_id": p.id}, resource_owner_id=p.id)
    profile = get_db().employees.find_one({"_id": p.id})
    out = employee_out(profile) if profile else {"_id": p.id, "email": p.email, "fullName": p.username}
    # role / phòng ban dùng để phân quyền lấy từ token (Keycloak là nguồn sự thật)
    out.update(role=p.role, department=dept_brief(p.department), username=p.username)
    return out
