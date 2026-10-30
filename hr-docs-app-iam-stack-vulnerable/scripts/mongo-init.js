// Tạo role + user tối thiểu quyền cho API trên MongoDB của bạn. Chạy bằng tài khoản quản trị:
//   mongosh "mongodb://<admin>:<pass>@<host>:27017/admin" --file scripts/mongo-init.js
// Đổi tên DB / mật khẩu bằng biến môi trường: MONGO_DB, HRDOCS_DB_PASSWORD.
// Sau đó trong .env:  MONGO_URI=mongodb://hrdocs_app:<pass>@<host>:27017/hr_docs_iam?authSource=hr_docs_iam
// Seed / db_setup (cần xóa dữ liệu, collMod) vẫn chạy bằng tài khoản quản trị.
const dbName = process.env.MONGO_DB || 'hr_docs_iam';
const password = process.env.HRDOCS_DB_PASSWORD || 'change-me-app-password';
const target = db.getSiblingDB(dbName);
const on = (collection, actions) => ({ resource: { db: dbName, collection }, actions });

const privileges = [
  on('departments', ['find']),                              // app chỉ đọc phòng ban
  on('employees', ['find', 'insert', 'update']),            // không có endpoint xóa nhân viên
  on('documents', ['find', 'insert', 'update', 'remove']),
  on('audit_logs', ['find', 'insert']),                     // append-only: không sửa/xóa được log
  on('', ['createIndex', 'listIndexes', 'listCollections']), // ensure_indexes lúc khởi động
];

if (target.getRole('hrdocsApp')) target.updateRole('hrdocsApp', { privileges, roles: [] });
else target.createRole({ role: 'hrdocsApp', privileges, roles: [] });

if (target.getUser('hrdocs_app')) target.updateUser('hrdocs_app', { pwd: password, roles: ['hrdocsApp'] });
else target.createUser({ user: 'hrdocs_app', pwd: password, roles: ['hrdocsApp'] });

print(`OK: role hrdocsApp + user hrdocs_app trên DB ${dbName}`);
