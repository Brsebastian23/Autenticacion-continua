/**
 * Captura de dinámica del cursor (mouse dynamics) y cálculo de 12 features.
 *
 * Diseño aditivo: NO toca la captura de tecleo. Se activa solo dentro de una
 * zona designada (un área de la pantalla) y registra movimientos y clics del
 * usuario, de los que deriva un conjunto de features genéricas e independientes
 * de la resolución.
 *
 * Las claves coinciden EXACTAMENTE con CURSOR_FEATURE_COLUMNS del backend
 * (authentication_api/cursor_service.py).
 */

export const CURSOR_FEATURE_COLUMNS = [
  'M.speed_mean',
  'M.speed_std',
  'M.speed_max',
  'M.accel_mean',
  'M.jitter',
  'M.curvature_mean',
  'M.straightness',
  'M.pause_ratio',
  'M.pause_count',
  'M.click_rate',
  'M.interclick_mean',
  'M.path_efficiency',
];

const PAUSE_MS = 100; // > 100 ms sin movimiento = pausa

/**
 * Acumula eventos de movimiento y clic y calcula las features.
 *
 * Uso:
 *   const cap = new CursorCapture();
 *   cap.addMove(x, y, now);    // mousemove dentro del área
 *   cap.addClick(now);         // mousedown
 *   const features = cap.compute();
 */
export class CursorCapture {
  constructor() {
    this.points = []; // { x, y, t }
    this.clicks = []; // timestamps
  }

  reset() {
    this.points = [];
    this.clicks = [];
  }

  addMove(x, y, now = performance.now()) {
    // Ignorar duplicados muy cercanos en el tiempo (ruido de alta frecuencia).
    const last = this.points[this.points.length - 1];
    if (last && now - last.t < 4) return;
    this.points.push({ x, y, t: now });
  }

  addClick(now = performance.now()) {
    this.clicks.push(now);
  }

  get sampleCount() {
    return this.points.length;
  }

  /** ¿Hay suficiente movimiento para calcular features fiables? */
  isReady(minPoints = 20) {
    return this.points.length >= minPoints;
  }

  compute() {
    if (this.points.length < 2) {
      throw new Error('Se necesita más movimiento del cursor para calcular las métricas.');
    }
    const pts = this.points;
    const speeds = [];
    const accels = [];
    const headings = [];
    let pathLength = 0;
    let pauseTime = 0;
    let pauseCount = 0;

    for (let i = 1; i < pts.length; i += 1) {
      const dx = pts[i].x - pts[i - 1].x;
      const dy = pts[i].y - pts[i - 1].y;
      const dt = Math.max(pts[i].t - pts[i - 1].t, 1); // ms
      const dist = Math.hypot(dx, dy);
      pathLength += dist;

      const speed = dist / dt; // px/ms
      speeds.push(speed);

      if (i >= 2) {
        accels.push(Math.abs(speeds[speeds.length - 1] - speeds[speeds.length - 2]));
      }

      headings.push(Math.atan2(dy, dx));
      if (dt > PAUSE_MS) {
        pauseTime += dt;
        pauseCount += 1;
      }
    }

    const totalTime = Math.max(pts[pts.length - 1].t - pts[0].t, 1);
    const netDist = Math.hypot(
      pts[pts.length - 1].x - pts[0].x,
      pts[pts.length - 1].y - pts[0].y,
    );

    // Jitter: variación de dirección (desvío circular de los cambios de rumbo).
    const turning = [];
    for (let i = 1; i < headings.length; i += 1) {
      let d = headings[i] - headings[i - 1];
      d = Math.atan2(Math.sin(d), Math.cos(d)); // normalizar a [-π, π]
      turning.push(Math.abs(d));
    }
    const jitter = mean(turning);
    const curvature = mean(turning);

    // Clics.
    let interclickMean = 0;
    if (this.clicks.length >= 2) {
      const gaps = [];
      for (let i = 1; i < this.clicks.length; i += 1) {
        gaps.push(this.clicks[i] - this.clicks[i - 1]);
      }
      interclickMean = mean(gaps);
    }
    const clickRate = this.clicks.length / (totalTime / 1000);

    return {
      'M.speed_mean': round(mean(speeds)),
      'M.speed_std': round(std(speeds)),
      'M.speed_max': round(Math.max(...speeds, 0)),
      'M.accel_mean': round(mean(accels)),
      'M.jitter': round(jitter),
      'M.curvature_mean': round(curvature),
      'M.straightness': round(pathLength > 0 ? clamp01(netDist / pathLength) : 0),
      'M.pause_ratio': round(clamp01(pauseTime / totalTime)),
      'M.pause_count': pauseCount,
      'M.click_rate': round(clickRate),
      'M.interclick_mean': round(interclickMean),
      'M.path_efficiency': round(pathLength > 0 ? clamp01(netDist / pathLength) : 0),
    };
  }
}

function mean(arr) {
  if (!arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function std(arr) {
  if (arr.length < 2) return 0;
  const m = mean(arr);
  const variance = mean(arr.map((v) => (v - m) ** 2));
  return Math.sqrt(variance);
}

function clamp01(v) {
  return Math.max(0, Math.min(1, v));
}

function round(v) {
  return Math.round(v * 1e6) / 1e6;
}
