import { keycloak } from './keycloak';

/** Gọi API qua Kong; access token Keycloak gắn vào header Authorization, tự làm mới khi sắp hết hạn. */
export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (keycloak.authenticated) {
    await keycloak.updateToken(30).catch(() => keycloak.login());
    headers.Authorization = `Bearer ${keycloak.token}`;
  }

  const res = await fetch(`/api${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // FastAPI trả {error}, Kong trả {message}
    const err = new Error(data.error || data.message || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}
