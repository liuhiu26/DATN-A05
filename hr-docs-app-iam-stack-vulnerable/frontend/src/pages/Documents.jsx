import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ title: '', content: '', classification: 'internal' });

  const load = () => api('/documents').then(setDocs).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api('/documents', { method: 'POST', body: form });
      setForm({ title: '', content: '', classification: 'internal' });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <h2>Tài liệu</h2>
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>Tiêu đề</th><th>Chủ sở hữu</th><th>Phòng ban</th><th>Phân loại</th><th>Cập nhật</th></tr></thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d._id}>
              <td><Link to={`/documents/${d._id}`}>{d.title}</Link></td>
              <td>{d.owner?.fullName}</td>
              <td>{d.department?.code}</td>
              <td>{d.classification}</td>
              <td>{new Date(d.updatedAt).toLocaleString('vi-VN')}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="card" onSubmit={create}>
        <h3>Tạo tài liệu mới</h3>
        <label>Tiêu đề<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        <label>Nội dung<textarea rows={4} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} /></label>
        <label>Phân loại
          <select value={form.classification} onChange={(e) => setForm({ ...form, classification: e.target.value })}>
            <option value="internal">internal</option>
            <option value="confidential">confidential</option>
          </select>
        </label>
        <button type="submit">Tạo</button>
      </form>
    </>
  );
}
