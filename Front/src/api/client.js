/**
 * Cliente HTTP hacia el backend Spring Boot.
 *
 * La URL base se configura con la variable de entorno {@code VITE_API_URL}.
 * - En desarrollo (proxy de Vite) puede quedar como "/api".
 * - En producción: URL absoluta del backend, p. ej.
 *   VITE_API_URL=https://backend-java.fly.dev/api
 */

const BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

async function request(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const message = data?.detail || data?.message || `Error ${response.status}`;
    throw new Error(message);
  }
  return data;
}

export const api = {
  register: ({ username, password, keystrokeModelId }) =>
    request('/auth/register', {
      method: 'POST',
      body: { username, password, keystrokeModelId },
    }),

  login: ({ username, password }) =>
    request('/auth/login', {
      method: 'POST',
      body: { username, password },
    }),

  me: (token) => request('/auth/me', { token }),

  verify: ({ token, features }) =>
    request('/keystroke/verify', {
      method: 'POST',
      token,
      body: { features },
    }),

  train: ({ token, samples }) =>
    request('/keystroke/train', {
      method: 'POST',
      token,
      body: { samples },
    }),
};
