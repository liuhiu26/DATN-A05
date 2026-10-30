from typing import Any

from fastapi import APIRouter, Body, Depends, Request, Response

from ..authz import authorize, record
from ..db import get_db, now
from ..errors import HttpError
from ..schemas import DocumentCreate, DocumentUpdate, parse
from ..security import Principal, current_principal
from ..serializers import document_out, parse_object_id

router = APIRouter(prefix="/api/documents", tags=["documents"])


def load(doc_id: str) -> dict:
    doc = get_db().documents.find_one({"_id": parse_object_id(doc_id)})
    if not doc:
        raise HttpError(404, "Document not found")
    return doc


def as_resource(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "owner_id": doc.get("owner_id"),
        "department": doc.get("department_id"),
        "classification": doc.get("classification", "internal"),
    }


@router.get("", summary="Danh sách tài liệu được xem (R1, R2; không có nội dung nên không áp R3)")
def list_documents(request: Request, p: Principal = Depends(current_principal)):
    authorize(request, p, "document:list")
    if p.role == "admin":
        flt = {}
    elif p.role == "manager" and p.department:
        flt = {"$or": [{"owner_id": p.id}, {"department_id": p.department}]}
    else:
        flt = {"owner_id": p.id}
    cache: dict = {}
    docs = get_db().documents.find(flt, {"content": 0}).sort("updatedAt", -1)
    return [document_out(d, with_content=False, cache=cache) for d in docs]


@router.post("", status_code=201, summary="Tạo tài liệu (chủ sở hữu = người tạo, phòng ban = phòng ban người tạo)")
def create_document(request: Request, body: Any = Body(..., examples=[{"title": "Ghi chú", "content": "...", "classification": "internal"}]), p: Principal = Depends(current_principal)):
    authorize(request, p, "document:create")
    data = parse(DocumentCreate, body)
    ts = now()
    # V-MASS-1: tin owner_id / department do client gửi trong body thay vì gán từ token.
    # Kẻ tấn công tạo tài liệu "thuộc về" người khác / gán nhầm phòng ban (giả mạo nguồn gốc dữ liệu).
    # Bản secure: owner_id luôn = p.id, department_id = p.department (không đọc từ body).
    raw = body if isinstance(body, dict) else {}
    doc = {**data.model_dump(), "owner_id": raw.get("owner_id", p.id),
           "department_id": raw.get("department", p.department or None), "createdAt": ts, "updatedAt": ts}
    doc["_id"] = get_db().documents.insert_one(doc).inserted_id
    request.state.authz.update(resource_id=str(doc["_id"]), resource_owner_id=p.id)
    return document_out(doc)


@router.get("/{doc_id}", summary="Xem tài liệu: chủ sở hữu (R1), manager cùng phòng (R2), admin; confidential chỉ trong giờ làm việc (R3)")
def get_document(doc_id: str, request: Request, p: Principal = Depends(current_principal)):
    doc = load(doc_id)
    # V-BOLA-1: bỏ authorize('document:read') → mất R1 (owner), R2 (manager cùng phòng) và R3 (giờ làm việc).
    # Chỉ cần đăng nhập + biết id là đọc được MỌI tài liệu, kể cả confidential của phòng khác, bất kể giờ.
    # Bản secure: authorize(request, p, "document:read", as_resource(doc), resource_owner_id=doc.get("owner_id")).
    record(request, True, "NO_CHECK", resource_id=str(doc["_id"]), resource_owner_id=doc.get("owner_id"))
    return document_out(doc)


@router.put("/{doc_id}", summary="Sửa tài liệu: chủ sở hữu (R1), admin")
def update_document(doc_id: str, request: Request, body: Any = Body(..., examples=[{"title": "Tiêu đề mới"}]), p: Principal = Depends(current_principal)):
    doc = load(doc_id)
    # V-BOLA-2: bỏ authorize('document:update') → mất R1. Ai cũng sửa/ghi đè tài liệu của người khác nếu biết id.
    # Bản secure: authorize(request, p, "document:update", as_resource(doc), resource_owner_id=doc.get("owner_id")).
    record(request, True, "NO_CHECK", resource_id=str(doc["_id"]), resource_owner_id=doc.get("owner_id"))
    changes = parse(DocumentUpdate, body).model_dump(exclude_none=True)
    if changes:
        changes["updatedAt"] = now()
        get_db().documents.update_one({"_id": doc["_id"]}, {"$set": changes})
        doc.update(changes)
    return document_out(doc)


@router.delete("/{doc_id}", status_code=204, summary="Xóa tài liệu: admin, chỉ từ IP nội bộ (R5)")
def delete_document(doc_id: str, request: Request, p: Principal = Depends(current_principal)):
    doc = load(doc_id)
    authorize(request, p, "document:delete", as_resource(doc), resource_owner_id=doc.get("owner_id"))
    get_db().documents.delete_one({"_id": doc["_id"]})
    return Response(status_code=204)
