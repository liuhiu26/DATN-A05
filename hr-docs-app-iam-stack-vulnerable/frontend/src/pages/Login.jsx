import { useAuth } from '../auth.jsx';

const ACCOUNTS = [
  ['admin', 'admin', '—'],
  ['it.manager', 'manager', 'IT'],
  ['alice', 'employee', 'IT'],
  ['bob', 'employee', 'IT'],
  ['hr.manager', 'manager', 'HR'],
  ['carol', 'employee', 'HR'],
  ['sales.manager', 'manager', 'SALES'],
  ['dave', 'employee', 'SALES'],
];

export default function Login() {
  const { login, error } = useAuth();
  return (
    <div className="card login">
      <h2>HR Docs</h2>
      <p className="muted">Đăng nhập do Keycloak (realm <code>hrdocs</code>) xử lý; ứng dụng không giữ mật khẩu.</p>
      <button onClick={login}>Đăng nhập bằng Keycloak</button>
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>Tài khoản mẫu</th><th>Realm role</th><th>Group (phòng ban)</th></tr></thead>
        <tbody>
          {ACCOUNTS.map(([u, r, d]) => <tr key={u}><td><code>{u}</code></td><td>{r}</td><td>{d}</td></tr>)}
        </tbody>
      </table>
      <p className="muted">Mật khẩu chung: <code>Password123!</code> (đăng nhập bằng username hoặc email <code>…@corp.local</code>)</p>
    </div>
  );
}
