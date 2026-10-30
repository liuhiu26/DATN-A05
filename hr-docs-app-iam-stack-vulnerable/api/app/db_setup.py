"""Tạo/cập nhật validator và index mà KHÔNG xóa dữ liệu (dùng khi nâng cấp DB đang có dữ liệu).
Chạy bằng tài khoản có quyền collMod (vd. tài khoản quản trị):
    MONGO_URI=mongodb://admin:...@host:27017/?authSource=admin python -m app.db_setup"""
from .db import apply_validators, ensure_indexes, get_db

if __name__ == "__main__":
    db = get_db()
    apply_validators(db)
    ensure_indexes(db)
    for name in ("departments", "employees", "documents", "audit_logs"):
        print(f"{name:12} {db[name].estimated_document_count():6} docs  indexes: {', '.join(sorted(db[name].index_information()))}")
