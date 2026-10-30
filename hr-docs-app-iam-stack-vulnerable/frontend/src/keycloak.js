import Keycloak from 'keycloak-js';

// Đăng nhập OIDC Authorization Code + PKCE với Keycloak (realm hrdocs, client public hrdocs-web).
export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080',
  realm: 'hrdocs',
  clientId: 'hrdocs-web',
});

let initPromise;
/** keycloak-js chỉ cho init 1 lần (React StrictMode gọi effect 2 lần ở dev). */
export const initKeycloak = () =>
  (initPromise ??= keycloak.init({ onLoad: 'check-sso', pkceMethod: 'S256', checkLoginIframe: false }));
