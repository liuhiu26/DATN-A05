import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api';

export default function DepartmentReport() {
  const { id } = useParams();
  const [depts, setDepts] = useState([]);
  const [report, setReport] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => { api('/departments').then(setDepts).catch(() => {}); }, []);
  useEffect(() => {
    setReport(null); setError('');
    if (id) api(`/departments/${id}/reports`).then(setReport).catch((e) => setError(e.message));
  }, [id]);

  return (
    <>
      <h2>Báo cáo phòng ban</h2>
      <p>{depts.map((d) => <Link key={d._id} to={`/departments/${d._id}/reports`} className="pill">{d.code}</Link>)}</p>
      {error && <p className="error">{error}</p>}
      {report && (
        <>
          <h3>{report.department.code} - {report.department.name}</h3>
          <p className="muted">Manager: {report.department.manager?.fullName || '—'} · Tạo lúc {new Date(report.generatedAt).toLocaleString('vi-VN')}</p>
          <table className="kv">
            <tbody>
              <tr><th>Số nhân viên</th><td>{report.headcount} (đang hoạt động: {report.activeCount})</td></tr>
              <tr><th>Theo role</th><td>{Object.entries(report.byRole).map(([r, n]) => `${r}: ${n}`).join(', ')}</td></tr>
              <tr><th>Tổng lương</th><td>{report.totalSalary.toLocaleString('vi-VN')} ₫</td></tr>
              <tr><th>Lương trung bình</th><td>{report.averageSalary.toLocaleString('vi-VN')} ₫</td></tr>
              <tr><th>Tài liệu</th><td>{report.documentCount} (mật: {report.confidentialCount})</td></tr>
            </tbody>
          </table>
          <table>
            <thead><tr><th>Họ tên</th><th>Role</th><th>Chức danh</th><th>Lương</th></tr></thead>
            <tbody>
              {report.employees.map((e) => (
                <tr key={e._id}><td>{e.fullName}</td><td>{e.role}</td><td>{e.position}</td><td>{e.salary.toLocaleString('vi-VN')}</td></tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
