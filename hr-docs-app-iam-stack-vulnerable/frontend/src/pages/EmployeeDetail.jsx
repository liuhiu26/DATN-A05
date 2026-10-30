import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth.jsx';

const SELF_FIELDS = ['fullName', 'phone', 'address'];
const ADMIN_FIELDS = ['fullName', 'phone', 'address', 'position', 'role', 'salary', 'department', 'isActive'];

export default function EmployeeDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [emp, setEmp] = useState(null);
  const [form, setForm] = useState({});
  const [depts, setDepts] = useState([]);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  const isAdmin = user.role === 'admin';
  const isSelf = user._id === id;
  const fields = isAdmin ? ADMIN_FIELDS : isSelf ? SELF_FIELDS : [];

  useEffect(() => {
    setEmp(null); setError(''); setMsg('');
    api(`/employees/${id}`)
      .then((e) => {
        setEmp(e);
        setForm(Object.fromEntries(ADMIN_FIELDS.map((f) => [f, f === 'department' ? e.department?._id || '' : e[f]])));
      })
      .catch((e) => setError(e.message));
    if (isAdmin) api('/departments').then(setDepts).catch(() => {});
  }, [id, isAdmin]);

  if (error && !emp) return <p className="error">{error}</p>;
  if (!emp) return <p>Đang tải...</p>;

  const save = async (e) => {
    e.preventDefault();
    setError(''); setMsg('');
    const body = Object.fromEntries(fields.map((f) => [f, form[f]]));
    if ('salary' in body) body.salary = Number(body.salary);
    if (body.department === '') body.department = null;
    try {
      const updated = await api(`/employees/${id}`, { method: 'PATCH', body });
      setEmp({ ...emp, ...updated, department: depts.find((d) => d._id === updated.department) || emp.department });
      setMsg('Đã cập nhật.');
    } catch (err) { setError(err.message); }
  };

  const input = (f) => {
    if (f === 'role') return (
      <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
        {['employee', 'manager', 'admin'].map((r) => <option key={r}>{r}</option>)}
      </select>
    );
    if (f === 'department') return (
      <select value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}>
        <option value="">—</option>
        {depts.map((d) => <option key={d._id} value={d._id}>{d.code}</option>)}
      </select>
    );
    if (f === 'isActive') return <input type="checkbox" checked={!!form.isActive} onChange={(e) => setForm({ ...form, isActive: e.target.checked })} />;
    return <input type={f === 'salary' ? 'number' : 'text'} value={form[f] ?? ''} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />;
  };

  return (
    <>
      <h2>Hồ sơ: {emp.fullName}</h2>
      <table className="kv">
        <tbody>
          <tr><th>Email</th><td>{emp.email}</td></tr>
          <tr><th>Role</th><td>{emp.role}</td></tr>
          <tr><th>Phòng ban</th><td>{emp.department ? `${emp.department.code} - ${emp.department.name}` : '—'}</td></tr>
          <tr><th>Chức danh</th><td>{emp.position}</td></tr>
          <tr><th>Điện thoại</th><td>{emp.phone}</td></tr>
          <tr><th>Địa chỉ</th><td>{emp.address}</td></tr>
          <tr><th>Lương</th><td>{emp.salary?.toLocaleString('vi-VN')} ₫</td></tr>
        </tbody>
      </table>

      {fields.length > 0 && (
        <form className="card" onSubmit={save}>
          <h3>Cập nhật hồ sơ</h3>
          {fields.map((f) => <label key={f}>{f}{input(f)}</label>)}
          <button type="submit">Lưu</button>
        </form>
      )}
      {msg && <p className="ok">{msg}</p>}
      {error && <p className="error">{error}</p>}
    </>
  );
}
