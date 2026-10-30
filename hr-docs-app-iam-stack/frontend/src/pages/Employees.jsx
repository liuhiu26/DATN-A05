import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';

export default function Employees() {
  const [list, setList] = useState([]);
  const [error, setError] = useState('');
  useEffect(() => { api('/employees').then(setList).catch((e) => setError(e.message)); }, []);

  return (
    <>
      <h2>Nhân viên</h2>
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>Họ tên</th><th>Email</th><th>Role</th><th>Phòng ban</th><th>Chức danh</th></tr></thead>
        <tbody>
          {list.map((e) => (
            <tr key={e._id}>
              <td><Link to={`/employees/${e._id}`}>{e.fullName}</Link></td>
              <td>{e.email}</td>
              <td>{e.role}</td>
              <td>{e.department?.code}</td>
              <td>{e.position}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
