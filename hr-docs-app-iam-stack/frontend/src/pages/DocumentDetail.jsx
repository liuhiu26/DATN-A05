import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../api';
import { useAuth } from '../auth.jsx';

export default function DocumentDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [form, setForm] = useState(null);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api(`/documents/${id}`)
      .then((d) => { setDoc(d); setForm({ title: d.title, content: d.content, classification: d.classification }); })
      .catch((e) => setError(e.message));
  }, [id]);

  if (error && !doc) return <p className="error">{error}</p>;
  if (!doc) return <p>Đang tải...</p>;

  const canEdit = user.role === 'admin' || doc.owner?._id === user._id;

  const save = async (e) => {
    e.preventDefault();
    setError(''); setMsg('');
    try {
      setDoc({ ...doc, ...(await api(`/documents/${id}`, { method: 'PUT', body: form })) });
      setMsg('Đã lưu.');
    } catch (err) { setError(err.message); }
  };

  const remove = async () => {
    if (!confirm('Xóa tài liệu này?')) return;
    try {
      await api(`/documents/${id}`, { method: 'DELETE' });
      navigate('/documents');
    } catch (err) { setError(err.message); }
  };

  return (
    <>
      <h2>{doc.title}</h2>
      <p className="muted">
        Chủ sở hữu: {doc.owner?.fullName} ({doc.owner?.email}) · Phòng ban: {doc.department?.code || '—'} · {doc.classification}
      </p>
      {canEdit ? (
        <form className="card" onSubmit={save}>
          <label>Tiêu đề<input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
          <label>Nội dung<textarea rows={8} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} /></label>
          <label>Phân loại
            <select value={form.classification} onChange={(e) => setForm({ ...form, classification: e.target.value })}>
              <option value="internal">internal</option>
              <option value="confidential">confidential</option>
            </select>
          </label>
          <button type="submit">Lưu</button>
        </form>
      ) : (
        <pre className="card">{doc.content}</pre>
      )}
      {user.role === 'admin' && <button className="danger" onClick={remove}>Xóa tài liệu</button>}
      {msg && <p className="ok">{msg}</p>}
      {error && <p className="error">{error}</p>}
    </>
  );
}
