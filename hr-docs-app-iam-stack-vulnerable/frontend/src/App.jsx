import { Link, Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './auth.jsx';
import Login from './pages/Login.jsx';
import Documents from './pages/Documents.jsx';
import DocumentDetail from './pages/DocumentDetail.jsx';
import Employees from './pages/Employees.jsx';
import EmployeeDetail from './pages/EmployeeDetail.jsx';
import DepartmentReport from './pages/DepartmentReport.jsx';
import AdminUsers from './pages/AdminUsers.jsx';
import AdminAudit from './pages/AdminAudit.jsx';

function Layout({ children }) {
  const { user, logout } = useAuth();
  const deptId = user.department?._id;
  return (
    <>
      <nav className="nav">
        <strong>HR Docs</strong>
        <Link to="/documents">Tài liệu</Link>
        <Link to="/employees">Nhân viên</Link>
        <Link to={`/employees/${user._id}`}>Hồ sơ của tôi</Link>
        {(user.role === 'manager' || user.role === 'admin') && <Link to={deptId ? `/departments/${deptId}/reports` : '/departments'}>Báo cáo</Link>}
        {user.role === 'admin' && (
          <>
            <Link to="/admin/users">Tạo tài khoản</Link>
            <Link to="/admin/audit">Audit log</Link>
          </>
        )}
        <a href="/api/docs" target="_blank" rel="noreferrer">API docs</a>
        <span className="spacer" />
        <span className="muted">
          {user.fullName} · {user.role}
          {user.department ? ` · ${user.department.code}` : ''}
        </span>
        <button onClick={logout}>Đăng xuất</button>
      </nav>
      <main>{children}</main>
    </>
  );
}

export default function App() {
  const { user, loading } = useAuth();
  if (loading) return <p style={{ padding: 24 }}>Đang tải...</p>;
  if (!user) return <Login />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/documents" />} />
        <Route path="/documents" element={<Documents />} />
        <Route path="/documents/:id" element={<DocumentDetail />} />
        <Route path="/employees" element={<Employees />} />
        <Route path="/employees/:id" element={<EmployeeDetail />} />
        <Route path="/departments" element={<DepartmentReport />} />
        <Route path="/departments/:id/reports" element={<DepartmentReport />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/audit" element={<AdminAudit />} />
        <Route path="*" element={<p>Không tìm thấy trang.</p>} />
      </Routes>
    </Layout>
  );
}
