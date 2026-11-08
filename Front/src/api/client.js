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

  // Métricas de exactitud (EER/FAR/FRR/AUC). El backend hace de fachada hacia
  // el microservicio ML, así el front siempre habla un único origen.
  metricsSummary: () => request('/metrics/summary'),
  metricsCurve: () => request('/metrics/curve'),

  // Dinámica del cursor (mouse dynamics). Fachada al microservicio ML.
  cursorRetrain: ({ userId, records, synthetic, n }) =>
    request('/cursor/retrain', {
      method: 'POST',
      body: { user_id: userId, records, synthetic, n },
    }),
  cursorPredict: ({ userId, record }) =>
    request('/cursor/predict', {
      method: 'POST',
      body: { user_id: userId, record },
    }),
};
