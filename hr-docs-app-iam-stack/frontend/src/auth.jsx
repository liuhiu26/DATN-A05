import { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';
import { initKeycloak, keycloak } from './keycloak';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    initKeycloak()
      .then((authenticated) => (authenticated ? api('/auth/me').then(setUser) : null))
      .catch((e) => setError(e?.message || 'Không kết nối được Keycloak (http://localhost:8080)'))
      .finally(() => setLoading(false));
  }, []);

  const login = () => keycloak.login();
  const logout = () => keycloak.logout({ redirectUri: window.location.origin });

  return <AuthContext.Provider value={{ user, loading, error, login, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
