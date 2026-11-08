import { useRef, useState, useCallback } from 'react';
import { api } from '../api/client.js';
import { CursorCapture, CURSOR_FEATURE_COLUMNS } from '../services/cursor.js';

const SESSIONS_REQUIRED = 10;

/**
 * Pantalla "Dinámica del cursor" (mouse dynamics).
 *
 * El usuario mueve el mouse y hace clic dentro de la zona delimitada; cada
 * "sesión" captura una ráfaga de movimiento y calcula las 12 features. Tras
 * acumular suficientes sesiones se entrena el modelo de cursor y luego se
 * puede verificar una nueva sesión contra él.
 *
 * Totalmente independiente del flujo de tecleo.
 */
export default function CursorScreen({ userId = 'demo' }) {
  const captureRef = useRef(new CursorCapture());
  const [samples, setSamples] = useState([]);
  const [live, setLive] = useState(0); // nº de puntos de la sesión en curso
  const [trained, setTrained] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [lastResult, setLastResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const onMouseMove = useCallback((e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    captureRef.current.addMove(e.clientX - rect.left, e.clientY - rect.top);
    setLive(captureRef.current.sampleCount);
  }, []);

  const onMouseDown = useCallback(() => {
    captureRef.current.addClick();
  }, []);

  // Cierra una sesión: calcula features y acumula.
  const finishSession = useCallback(() => {
    setError('');
    try {
      if (!captureRef.current.isReady(15)) {
        setError('Mueve el cursor un poco más antes de cerrar la sesión.');
        return;
      }
      const features = captureRef.current.compute();
      setSamples((prev) => [...prev, features]);
      captureRef.current.reset();
      setLive(0);
      setStatus(`Sesión capturada (${samples.length + 1}/${SESSIONS_REQUIRED}).`);
    } catch (err) {
      setError(err.message);
    }
  }, [samples.length]);

  const train = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await api.cursorRetrain({ userId, records: samples });
      setTrained(true);
      setStatus(`Modelo de cursor entrenado con ${res.samples} sesiones.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const useSynthetic = async () => {
    setBusy(true);
    setError('');
    try {
      const res = await api.cursorRetrain({ userId, synthetic: true, n: 40 });
      setTrained(true);
      setStatus(`Modelo de cursor entrenado con datos sintéticos (${res.samples} muestras).`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  // Verifica una nueva sesión contra el modelo entrenado.
  const verify = useCallback(async () => {
    setError('');
    setLastResult(null);
    try {
      if (!captureRef.current.isReady(15)) {
        setError('Mueve el cursor un poco más antes de verificar.');
        return;
      }
      const features = captureRef.current.compute();
      const res = await api.cursorPredict({ userId, record: features });
      setLastResult(res);
      captureRef.current.reset();
      setLive(0);
    } catch (err) {
      setError(err.message);
    }
  }, [userId]);

  return (
    <div className="tester">
      <div className="card">
        <h2>Dinámica del cursor</h2>
        <p className="hint">
          Esta pantalla demuestra el modelo de <strong>mouse dynamics</strong>: la forma en que
          mueves y haces clic es tan personal como tu forma de teclear. Mueve el cursor y haz clic
          dentro de la zona; cada ráfaga es una <em>sesión</em> con 12 métricas de movimiento.
        </p>

        <div
          className="cursor-zone"
          onMouseMove={onMouseMove}
          onMouseDown={onMouseDown}
        >
          <div className="cursor-zone-inner">
            <p>Mueve el cursor aquí y haz clic</p>
            <small>{live} puntos capturados en esta sesión</small>
          </div>
        </div>

        <div className="cursor-actions">
          <button className="btn secondary" onClick={finishSession} disabled={busy}>
            Cerrar sesión ({samples.length}/{SESSIONS_REQUIRED})
          </button>
          <button
            className="btn"
            onClick={train}
            disabled={busy || samples.length < 3}
          >
            Entrenar con mis {samples.length} sesiones
          </button>
          <button className="btn secondary" onClick={useSynthetic} disabled={busy}>
            Usar datos sintéticos
          </button>
        </div>

        <div className="cursor-actions">
          <button className="btn" onClick={verify} disabled={busy || !trained}>
            Verificar esta sesión
          </button>
          <button
            className="btn secondary"
            onClick={() => {
              setSamples([]);
              captureRef.current.reset();
              setLive(0);
              setStatus('');
              setLastResult(null);
            }}
            disabled={busy}
          >
            Limpiar
          </button>
        </div>

        {status && <div className="alert info">{status}</div>}
        {error && <div className="alert error">{error}</div>}

        {samples.length >= SESSIONS_REQUIRED && !trained && (
          <p className="hint">Ya tienes suficientes sesiones; pulsa «Entrenar».</p>
        )}

        {lastResult && (
          <div className="result-grid" style={{ marginTop: 16 }}>
            <div className="metric">
              <span className="metric-label">Decisión</span>
              <span className={`metric-value ${lastResult.is_legitimate ? 'ok' : 'bad'}`}>
                {lastResult.is_legitimate ? 'Legítimo' : 'Anómalo'}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Score</span>
              <span className="metric-value">{lastResult.confidence_score}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Umbral</span>
              <span className="metric-value">{lastResult.threshold}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Latencia</span>
              <span className="metric-value">{lastResult.latency_ms} ms</span>
            </div>
          </div>
        )}

        {samples.length > 0 && (
          <details style={{ marginTop: 16 }}>
            <summary className="hint">Ver métricas de la última sesión ({CURSOR_FEATURE_COLUMNS.length} features)</summary>
            <pre className="features-json">
              {JSON.stringify(samples[samples.length - 1], null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
}
