import { useRef, useState } from 'react';
import { api } from '../api/client.js';
import { KeystrokeCapture, TARGET_PASSWORD } from '../services/keystroke.js';

const EXPECTED = TARGET_PASSWORD;

export default function KeystrokeTester({ token, modelId }) {
  const captureRef = useRef(null);
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('idle'); // idle | error | success
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  function ensureCapture() {
    if (!captureRef.current) captureRef.current = new KeystrokeCapture();
    return captureRef.current;
  }

  function handleKeyDown(event) {
    // Evitar que Enter envíe formularios / recargue.
    if (event.key === 'Enter') event.preventDefault();
    ensureCapture().record(event);
  }

  function handleKeyUp(event) {
    ensureCapture().record(event);
  }

  function resetPad() {
    setValue('');
    ensureCapture().reset();
    setStatus('idle');
    setMessage('');
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setResult(null);

    const capture = ensureCapture();
    const typed = value.trim();

    // Validación 1: contraseña correcta.
    if (typed !== EXPECTED) {
      setStatus('error');
      setMessage(
        `La contraseña debe ser exactamente "${EXPECTED}". Escribiste "${typed}".`,
      );
      return;
    }

    // Validación 2: todas las teclas capturadas.
    const completeness = capture.checkComplete();
    if (!completeness.complete) {
      setStatus('error');
      setMessage(
        `Faltan teclas por capturar: ${completeness.missing.join(', ')}. Intenta de nuevo.`,
      );
      return;
    }

    let features;
    try {
      features = capture.compute();
    } catch (err) {
      setStatus('error');
      setMessage(err.message);
      return;
    }

    setLoading(true);
    try {
      const res = await api.verify({ token, features });
      setResult({ ...res, features });
      setStatus(res.legitimate ? 'success' : 'warn');
      setMessage(
        res.legitimate
          ? 'Muestra reconocida como el usuario legítimo.'
          : 'Muestra clasificada como anomalía (posible impostor).',
      );
      setHistory((prev) => [
        {
          id: prev.length + 1,
          at: new Date().toLocaleTimeString(),
          legitimate: res.legitimate,
          score: res.confidenceScore,
          latency: res.latencyMs,
          model: res.keystrokeModelId,
        },
        ...prev,
      ]);
      resetPad();
    } catch (err) {
      setStatus('error');
      setMessage(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="tester">
      <div className="card">
        <h2>Prueba de escritura</h2>
        <p className="hint">
          Escribe la contraseña objetivo y pulsa <kbd>Enter</kbd>. Se registrarán
          los tiempos de tecleo (hold / down-down / up-down) para compararlos con
          el modelo activo <code>{modelId}</code>. Si aún no has entrenado tu
          modelo propio, se comparará contra el modelo del dataset.
        </p>

        <div className="target">
          Contraseña objetivo: <code>{EXPECTED}</code>
        </div>

        <form onSubmit={handleSubmit} className="form">
          <input
            className="keystroke-input"
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onKeyUp={handleKeyUp}
            placeholder={EXPECTED}
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            autoFocus
          />
          <div className="actions">
            <button className="btn-primary" type="submit" disabled={loading}>
              {loading ? 'Verificando…' : 'Verificar muestra'}
            </button>
            <button className="btn-ghost" type="button" onClick={resetPad}>
              Limpiar
            </button>
          </div>
        </form>

        {message && <div className={`alert ${status}`}>{message}</div>}

        {result && (
          <div className="result-grid">
            <div className="metric">
              <span className="metric-label">Decisión</span>
              <span className={`metric-value ${result.legitimate ? 'ok' : 'bad'}`}>
                {result.legitimate ? 'LEGÍTIMO' : 'ANOMALÍA'}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Score</span>
              <span className="metric-value">{result.confidenceScore.toFixed(4)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Latencia modelo</span>
              <span className="metric-value">
                {result.latencyMs != null ? `${result.latencyMs.toFixed(1)} ms` : '—'}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Estado</span>
              <span className="metric-value">{result.statusCode}</span>
            </div>
          </div>
        )}
      </div>

      {history.length > 0 && (
        <div className="card">
          <h3>Historial de esta sesión</h3>
          <table className="history-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Hora</th>
                <th>Modelo</th>
                <th>Decisión</th>
                <th>Score</th>
                <th>Latencia</th>
              </tr>
            </thead>
            <tbody>
              {history.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>{row.at}</td>
                  <td><code>{row.model}</code></td>
                  <td>
                    <span className={row.legitimate ? 'badge ok' : 'badge bad'}>
                      {row.legitimate ? 'Legítimo' : 'Anomalía'}
                    </span>
                  </td>
                  <td>{row.score.toFixed(4)}</td>
                  <td>{row.latency != null ? `${row.latency.toFixed(1)} ms` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
