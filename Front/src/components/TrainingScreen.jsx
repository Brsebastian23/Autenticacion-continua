import { useRef, useState } from 'react';
import { api } from '../api/client.js';
import { KeystrokeCapture, TARGET_PASSWORD } from '../services/keystroke.js';

const EXPECTED = TARGET_PASSWORD;
const REQUIRED_REPS = 10;

/**
 * Pantalla de entrenamiento: el usuario teclea la contraseña varias veces
 * (por defecto 10). Cada repetición se convierte en una muestra (31 features)
 * y, al completar las requeridas, se entrena el modelo del usuario.
 */
export default function TrainingScreen({ token, modelId, onTrained }) {
  const captureRef = useRef(null);
  const [value, setValue] = useState('');
  const [samples, setSamples] = useState([]); // muestras (features) capturadas
  const [status, setStatus] = useState('idle'); // idle | error | success | info
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  function ensureCapture() {
    if (!captureRef.current) captureRef.current = new KeystrokeCapture();
    return captureRef.current;
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter') event.preventDefault();
    ensureCapture().record(event);
  }

  function handleKeyUp(event) {
    ensureCapture().record(event);
  }

  function resetCapture() {
    setValue('');
    ensureCapture().reset();
  }

  // Captura una repetición completa y la añade a las muestras.
  function handleAddRep(event) {
    event.preventDefault();
    setResult(null);

    const capture = ensureCapture();
    const typed = value.trim();

    if (typed !== EXPECTED) {
      setStatus('error');
      setMessage(
        `La contraseña debe ser exactamente "${EXPECTED}". Escribiste "${typed}".`,
      );
      return;
    }

    const completeness = capture.checkComplete();
    if (!completeness.complete) {
      setStatus('error');
      setMessage(
        `Faltan teclas por capturar: ${completeness.missing.join(', ')}. Intenta de nuevo.`,
      );
      resetCapture();
      return;
    }

    let features;
    try {
      features = capture.compute();
    } catch (err) {
      setStatus('error');
      setMessage(err.message);
      resetCapture();
      return;
    }

    const next = [...samples, features];
    setSamples(next);
    resetCapture();
    setStatus('info');
    setMessage(
      `Repetición ${next.length}/${REQUIRED_REPS} capturada. ` +
        (next.length < REQUIRED_REPS
          ? 'Sigue escribiendo la contraseña.'
          : '¡Listo! Ya puedes entrenar tu modelo.'),
    );
  }

  async function handleTrain() {
    if (samples.length < REQUIRED_REPS) {
      setStatus('error');
      setMessage(`Necesitas ${REQUIRED_REPS} repeticiones; llevas ${samples.length}.`);
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await api.train({ token, samples });
      setResult(res);
      setStatus('success');
      setMessage(`Modelo entrenado con ${res.samples} muestras.`);
      if (onTrained) onTrained(res);
    } catch (err) {
      setStatus('error');
      setMessage(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setSamples([]);
    setResult(null);
    resetCapture();
    setStatus('idle');
    setMessage('');
  }

  const progressPct = Math.min(100, (samples.length / REQUIRED_REPS) * 100);

  return (
    <div className="tester">
      <div className="card">
        <h2>Entrenar mi modelo</h2>
        <p className="hint">
          Escribe la contraseña objetivo y pulsa <kbd>Enter</kbd> para capturar
          cada repetición. Necesitas <strong>{REQUIRED_REPS}</strong> repeticiones
          para entrenar <strong>tu propio modelo</strong> con tus tiempos de tecleo
          reales. El modelo del dataset (<code>{modelId}</code>) no se modifica.
        </p>

        <div className="target">
          Contraseña objetivo: <code>{EXPECTED}</code>
        </div>

        <div className="progress-wrap">
          <div className="progress-bar" style={{ width: `${progressPct}%` }} />
          <span className="progress-label">
            {samples.length} / {REQUIRED_REPS} repeticiones
          </span>
        </div>

        <form onSubmit={handleAddRep} className="form">
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
            disabled={samples.length >= REQUIRED_REPS}
          />
          <div className="actions">
            <button
              className="btn-primary"
              type="submit"
              disabled={samples.length >= REQUIRED_REPS}
            >
              Capturar repetición ({samples.length}/{REQUIRED_REPS})
            </button>
            <button className="btn-ghost" type="button" onClick={handleReset}>
              Reiniciar
            </button>
          </div>
        </form>

        {message && <div className={`alert ${status}`}>{message}</div>}

        <div className="actions" style={{ marginTop: '16px' }}>
          <button
            className="btn-primary"
            type="button"
            onClick={handleTrain}
            disabled={loading || samples.length < REQUIRED_REPS}
          >
            {loading ? 'Entrenando…' : `Entrenar modelo (${samples.length}/${REQUIRED_REPS})`}
          </button>
        </div>

        {result && (
          <div className="result-grid">
            <div className="metric">
              <span className="metric-label">Estado</span>
              <span className="metric-value ok">ENTRENADO</span>
            </div>
            <div className="metric">
              <span className="metric-label">Muestras</span>
              <span className="metric-value">{result.samples}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Modelo</span>
              <span className="metric-value">{result.keystrokeModelId}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Latencia</span>
              <span className="metric-value">
                {result.latencyMs != null ? `${result.latencyMs.toFixed(1)} ms` : '—'}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
