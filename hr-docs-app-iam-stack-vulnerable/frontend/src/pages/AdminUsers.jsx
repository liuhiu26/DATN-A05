import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

const EMPTY = { email: '', password: '', fullName: '', role: 'employee', department: '', position: '', salary: 0 };

export default function AdminUsers() {
  const [form, setForm] = useState(EMPTY);
  const [depts, setDepts] = useState([]);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => { api('/departments').then(setDepts).catch(() => {}); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError(''); setCreated(null);
    const body = { ...form, salary: Number(form.salary) };
    if (!body.department) delete body.department;
    try {
      setCreated(await api('/admin/users', { method: 'POST', body }));
      setForm(EMPTY);
    } catch (err) { setError(err.message); }
  };

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <form className="card" onSubmit={submit}>
      <h2>Tạo tài khoản</h2>
      <label>Email<input required type="email" value={form.email} onChange={set('email')} /></label>
      <label>Mật khẩu<input required type="password" minLength={8} value={form.password} onChange={set('password')} /></label>
      <label>Họ tên<input required value={form.fullName} onChange={set('fullName')} /></label>
      <label>Role
        <select value={form.role} onChange={set('role')}>{['employee', 'manager', 'admin'].map((r) => <option key={r}>{r}</option>)}</select>
      </label>
      <label>Phòng ban
        <select value={form.department} onChange={set('department')}>
          <option value="">—</option>
          {depts.map((d) => <option key={d._id} value={d._id}>{d.code}</option>)}
        </select>
      </label>
      <label>Chức danh<input value={form.position} onChange={set('position')} /></label>
      <label>Lương<input type="number" value={form.salary} onChange={set('salary')} /></label>
      <button type="submit">Tạo</button>
      {error && <p className="error">{error}</p>}
      {created && <p className="ok">Đã tạo <Link to={`/employees/${created._id}`}>{created.email}</Link></p>}
    </form>
  );
}
