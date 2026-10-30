import { useEffect, useState } from 'react';
import { api } from '../api';

const FILTERS = [
  ['decision', 'decision (allow/deny)'],
  ['policy_rule', 'policy_rule (vd: R3_CONFIDENTIAL_HOURS)'],
  ['user_id', 'user_id'],
  ['scenario_id', 'scenario_id'],
];

export default function AdminAudit() {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    const qs = new URLSearchParams({ page, limit: 50 });
    for (const [k, v] of Object.entries(filters)) if (v) qs.set(k, v);
    api(`/admin/audit?${qs}`).then(setData).catch((e) => setError(e.message));
  }, [page, filters]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p>Đang tải...</p>;
  const pages = Math.max(1, Math.ceil(data.total / data.limit));

  return (
    <>
      <h2>Audit log</h2>
      <p>
        {FILTERS.map(([k, ph]) => (
          <input key={k} placeholder={ph} value={filters[k] || ''} style={{ marginRight: 6 }}
            onChange={(e) => { setPage(1); setFilters({ ...filters, [k]: e.target.value.trim() }); }} />
        ))}
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th>timestamp</th><th>user / role / dept</th><th>ip</th><th>request</th><th>status</th>
              <th>decision</th><th>policy_rule</th><th>resource / owner</th><th>latency</th><th>scenario</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((l) => (
              <tr key={l._id} className={l.decision === 'deny' ? 'warn' : ''} title={`request_id: ${l.request_id}\nuser_agent: ${l.user_agent}`}>
                <td>{new Date(l.timestamp).toLocaleString('vi-VN')}</td>
                <td><code>{l.user_id || '—'}</code><br />{l.role || ''} {l.department ? <code>{l.department}</code> : ''}</td>
                <td>{l.ip}</td>
                <td>{l.method} <code>{l.endpoint}</code></td>
                <td>{l.http_status}</td>
                <td>{l.decision}</td>
                <td>{l.policy_rule}</td>
                <td><code>{l.resource_id || ''}</code><br /><code>{l.resource_owner_id || ''}</code></td>
                <td>{l.latency_ms} ms</td>
                <td>{l.scenario_id || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button> Trang {page}/{pages} ({data.total} bản ghi){' '}
        <button disabled={page >= pages} onClick={() => setPage(page + 1)}>›</button>
      </p>
    </>
  );
}
