import { useEffect, useState } from 'react';
import { api } from '../api/client.js';

/** Formatea una fracción [0,1] como porcentaje. */
function pct(value, decimals = 2) {
  if (value == null || Number.isNaN(value)) return 'n/a';
  return `${(value * 100).toFixed(decimals)}%`;
}

function fmtThreshold(value) {
  if (value == null) return 'n/a';
  return `${value >= 0 ? '+' : ''}${value.toFixed(6)}`;
}

/**
 * Pantalla "Rendimiento del modelo".
 *
 * Materializa la evidencia de la pregunta de investigación: muestra el EER
 * (tasa de error igual) alcanzado por el modelo, junto con FAR/FRR/AUC y una
 * curva FAR vs FRR donde se ve el punto de equilibrio (EER).
 */
export default function MetricsDashboard() {
  const [summary, setSummary] = useState(null);
  const [curve, setCurve] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [s, c] = await Promise.all([api.metricsSummary(), api.metricsCurve()]);
        if (!active) return;
        setSummary(s);
        setCurve(c);
      } catch (err) {
        if (active) setError(err.message);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="card">
        <p className="hint">Cargando métricas…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <h2>Rendimiento del modelo</h2>
        <div className="alert error">{error}</div>
        <p className="hint">
          El benchmark se genera con{' '}
          <code>python manage.py benchmark_report</code> en el microservicio ML.
        </p>
      </div>
    );
  }

  const agg = summary?.aggregate ?? {};
  const eer = agg.eer ?? {};
  const auc = agg.auc ?? {};

  return (
    <div className="tester">
      <div className="card">
        <h2>Rendimiento del modelo</h2>
        <p className="hint">
          Exactitud del modelo IsolationForest medida sobre{' '}
          <strong>{summary?.n_subjects} sujetos</strong> del dataset{' '}
          <code>{summary?.dataset}</code>, con validación en sesiones no vistas
          (split por sesión: entrenamiento {summary?.train_sessions}, test = resto).
        </p>

        <div className="eer-hero">
          <span className="eer-hero-label">EER (tasa de error igual)</span>
          <span className="eer-hero-value">{pct(eer.mean)}</span>
          <span className="eer-hero-sub">
            mediana {pct(eer.median)} · rango {pct(eer.min)}–{pct(eer.max)}
          </span>
        </div>

        <div className="result-grid">
          <div className="metric">
            <span className="metric-label">AUC-ROC medio</span>
            <span className="metric-value ok">{pct(auc.mean)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">EER desviación</span>
            <span className="metric-value">{pct(eer.std)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">
              FAR @ umbral {fmtThreshold(summary?.reference_threshold)}
            </span>
            <span className="metric-value bad">{pct(agg.far_at_reference)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">
              FRR @ umbral {fmtThreshold(summary?.reference_threshold)}
            </span>
            <span className="metric-value">{pct(agg.frr_at_reference)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Accuracy de referencia</span>
            <span className="metric-value">{pct(agg.accuracy_at_reference)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Umbral óptimo recomendado</span>
            <span className="metric-value ok">{fmtThreshold(summary?.optimal_threshold)}</span>
          </div>
        </div>

        <p className="hint" style={{ marginTop: 16 }}>
          Un <strong>EER de {pct(eer.mean)}</strong> significa que, en el punto de
          equilibrio, el sistema falla aproximadamente 1 de cada{' '}
          {eer.mean ? Math.round(1 / eer.mean) : 'n/a'} decisiones, repartiendo el
          error por igual entre usuarios legítimos rechazados e impostores aceptados.
          El AUC de {pct(auc.mean)} indica una alta separación entre ambas clases.
        </p>
      </div>

      {curve && curve.points?.length > 0 && (
        <div className="card">
          <h3>Curva FAR vs FRR</h3>
          <p className="hint">
            El punto donde FAR y FRR se cruzan es el EER. Subir el umbral reduce
            falsas aceptaciones a costa de rechazar usuarios reales.
          </p>
          <FarFrrChart points={curve.points} eer={curve.eer} />
        </div>
      )}
    </div>
  );
}

/**
 * Gráfico SVG sencillo de FAR y FRR por umbral, sin dependencias externas.
 */
function FarFrrChart({ points, eer }) {
  const W = 640;
  const H = 260;
  const pad = { top: 20, right: 20, bottom: 40, left: 50 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  const xs = points.map((p) => p.threshold);
  const minX = Math.min(...xs, 0);
  const maxX = Math.max(...xs, 0.0001);
  const spanX = maxX - minX || 1;

  const xOf = (t) => pad.left + ((t - minX) / spanX) * innerW;
  const yOf = (v) => pad.top + innerH - (v ?? 0) * innerH;

  const farPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xOf(p.threshold)} ${yOf(p.far)}`).join(' ');
  const frrPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xOf(p.threshold)} ${yOf(p.frr)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="curve-chart" role="img" aria-label="Curva FAR vs FRR">
      {/* Rejilla horizontal */}
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <g key={g}>
          <line x1={pad.left} x2={W - pad.right} y1={yOf(g)} y2={yOf(g)} stroke="#2c3355" strokeWidth="1" />
          <text x={pad.left - 8} y={yOf(g) + 4} textAnchor="end" fontSize="11" fill="#97a0bf">
            {(g * 100).toFixed(0)}%
          </text>
        </g>
      ))}
      {/* Far */}
      <path d={farPath} fill="none" stroke="#f87171" strokeWidth="2.5" />
      {/* Frr */}
      <path d={frrPath} fill="none" stroke="#5b8cff" strokeWidth="2.5" />
      {/* Punto EER */}
      {eer != null && (
        <line
          x1={xOf(points[points.length - 1].threshold)}
          x2={xOf(points[points.length - 1].threshold)}
          y1={pad.top}
          y2={pad.top + innerH}
          stroke="#34d399"
          strokeDasharray="4 4"
          strokeWidth="1.5"
        />
      )}
      {/* Puntos */}
      {points.map((p, i) => (
        <g key={i}>
          <circle cx={xOf(p.threshold)} cy={yOf(p.far)} r="4" fill="#f87171" />
          <circle cx={xOf(p.threshold)} cy={yOf(p.frr)} r="4" fill="#5b8cff" />
        </g>
      ))}
      {/* Leyenda */}
      <g fontSize="12" fill="#e8ecf7">
        <rect x={pad.left} y={H - 24} width="12" height="12" fill="#f87171" />
        <text x={pad.left + 18} y={H - 13}>FAR (impostores aceptados)</text>
        <rect x={pad.left + 220} y={H - 24} width="12" height="12" fill="#5b8cff" />
        <text x={pad.left + 238} y={H - 13}>FRR (legítimos rechazados)</text>
        <rect x={pad.left + 440} y={H - 24} width="12" height="12" fill="#34d399" />
        <text x={pad.left + 458} y={H - 13}>EER</text>
      </g>
    </svg>
  );
}
