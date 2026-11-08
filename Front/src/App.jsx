import { useEffect, useState } from 'react';
import { api } from './api/client.js';
import AuthScreen from './components/AuthScreen.jsx';
import KeystrokeTester from './components/KeystrokeTester.jsx';
import TrainingScreen from './components/TrainingScreen.jsx';
import MetricsDashboard from './components/MetricsDashboard.jsx';
import CursorScreen from './components/CursorScreen.jsx';

const TOKEN_KEY = 'ca_token';
const USER_KEY = 'ca_user';

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  });
  // Pantalla activa cuando hay sesión: 'verify' (probar) | 'train' (entrenar).
  const [screen, setScreen] = useState('verify');

  // Valida el token guardado al cargar y refresca los datos del usuario.
  useEffect(() => {
    if (!token) return;
    refreshUser();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-consulta el perfil para reflejar el modelo activo (propio vs dataset).
  async function refreshUser() {
    try {
      const me = await api.me(token);
      const currentUser = {
        username: me.username,
        keystrokeModelId: me.keystrokeModelId,
        trainedModelId: me.trainedModelId,
        trained: me.trained,
        activeModelId: me.activeModelId,
      };
      localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
      setUser(currentUser);
    } catch {
      handleLogout();
    }
  }

  function handleAuthenticated(auth, username) {
    const currentToken = auth.token;
    const currentUser = {
      username: auth.username || username,
      keystrokeModelId: auth.keystrokeModelId,
      activeModelId: auth.keystrokeModelId,
      trained: false,
    };
    localStorage.setItem(TOKEN_KEY, currentToken);
    localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
    setToken(currentToken);
    setUser(currentUser);
    // Refrescar el perfil para traer trained/activeModelId correctos.
    api
      .me(currentToken)
      .then((me) => {
        const u = {
          username: me.username,
          keystrokeModelId: me.keystrokeModelId,
          trainedModelId: me.trainedModelId,
          trained: me.trained,
          activeModelId: me.activeModelId,
        };
        localStorage.setItem(USER_KEY, JSON.stringify(u));
        setUser(u);
      })
      .catch(() => {});
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Autenticación Continua</h1>
        <p className="subtitle">Keystroke Dynamics · IsolationForest</p>
        {user && (
          <div className="session-bar">
            <span>
              Sesión: <strong>{user.username}</strong> · modelo activo{' '}
              <code>{user.activeModelId || user.keystrokeModelId}</code>
              {user.trained ? (
                <span className="badge ok" style={{ marginLeft: 8 }}>
                  propio
                </span>
              ) : (
                <span className="badge" style={{ marginLeft: 8, color: 'var(--muted)' }}>
                  dataset
                </span>
              )}
            </span>
            <button className="btn-ghost" onClick={handleLogout}>
              Cerrar sesión
            </button>
          </div>
        )}
      </header>

      <main className="app-main">
        {!token ? (
          <AuthScreen onAuthenticated={handleAuthenticated} />
        ) : (
          <>
            <nav className="mode-selector">
              <button
                className={screen === 'verify' ? 'mode-btn active' : 'mode-btn'}
                onClick={() => setScreen('verify')}
              >
                <span className="mode-title">Probar mi modelo</span>
                <span className="mode-desc">Verificar una muestra de tecleo</span>
              </button>
              <button
                className={screen === 'train' ? 'mode-btn active' : 'mode-btn'}
                onClick={() => setScreen('train')}
              >
                <span className="mode-title">Entrenar mi modelo</span>
                <span className="mode-desc">Escribir {10} veces y entrenar</span>
              </button>
              <button
                className={screen === 'metrics' ? 'mode-btn active' : 'mode-btn'}
                onClick={() => setScreen('metrics')}
              >
                <span className="mode-title">Rendimiento</span>
                <span className="mode-desc">EER, FAR/FRR y exactitud</span>
              </button>
              <button
                className={screen === 'cursor' ? 'mode-btn active' : 'mode-btn'}
                onClick={() => setScreen('cursor')}
              >
                <span className="mode-title">Dinámica del cursor</span>
                <span className="mode-desc">Mouse dynamics</span>
              </button>
            </nav>

            {screen === 'verify' && (
              <KeystrokeTester
                token={token}
                modelId={user?.activeModelId || user?.keystrokeModelId}
              />
            )}
            {screen === 'train' && (
              <TrainingScreen
                token={token}
                modelId={user?.keystrokeModelId}
                onTrained={refreshUser}
              />
            )}
            {screen === 'metrics' && <MetricsDashboard />}
            {screen === 'cursor' && (
              <CursorScreen userId={user?.keystrokeModelId || user?.username || 'demo'} />
            )}
          </>
        )}
      </main>
    </div>
  );
}
