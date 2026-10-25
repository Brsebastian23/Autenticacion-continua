import { useState } from 'react';
import { api } from '../api/client.js';

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [form, setForm] = useState({
    username: '',
    password: '',
    keystrokeModelId: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'register') {
        await api.register(form);
      }
      const auth = await api.login({
        username: form.username,
        password: form.password,
      });
      onAuthenticated(auth, form.username);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card auth-card">
      <div className="tabs">
        <button
          className={mode === 'login' ? 'tab active' : 'tab'}
          onClick={() => {
            setMode('login');
            setError('');
          }}
        >
          Iniciar sesión
        </button>
        <button
          className={mode === 'register' ? 'tab active' : 'tab'}
          onClick={() => {
            setMode('register');
            setError('');
          }}
        >
          Registrarse
        </button>
      </div>

      <form onSubmit={handleSubmit} className="form">
        <label>
          Usuario
          <input
            type="text"
            value={form.username}
            onChange={(e) => update('username', e.target.value)}
            placeholder="diego"
            autoComplete="username"
            required
          />
        </label>

        <label>
          Contraseña
          <input
            type="password"
            value={form.password}
            onChange={(e) => update('password', e.target.value)}
            placeholder="••••••••"
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            required
          />
        </label>

        {mode === 'register' && (
          <label>
            ID del modelo de tecleo
            <input
              type="text"
              value={form.keystrokeModelId}
              onChange={(e) => update('keystrokeModelId', e.target.value)}
              placeholder="s002"
              required
            />
            <small className="hint">
              Identificador del modelo entrenado (p. ej. s002, s003…).
            </small>
          </label>
        )}

        {error && <div className="alert error">{error}</div>}

        <button className="btn-primary" type="submit" disabled={loading}>
          {loading
            ? 'Procesando…'
            : mode === 'login'
              ? 'Entrar'
              : 'Registrarme y entrar'}
        </button>
      </form>
    </div>
  );
}
