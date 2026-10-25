/**
 * Captura de keystroke dynamics y cálculo de las 31 features del modelo.
 *
 * Contraseña objetivo (dataset CMU DSL-StrongPasswordData): ".tie5Roanl" + Return.
 * Teclas (en orden):
 *   .  t  i  e  5  Shift  R  o  a  n  l  Return
 *
 * Familias de features:
 *   H.X     (hold time)      = keyup(X)   - keydown(X)
 *   DD.X.Y  (down-down)      = keydown(Y) - keydown(X)
 *   UD.X.Y  (up-down)        = keydown(Y) - keyup(X)
 *
 * Las claves coinciden EXACTAMENTE con las columnas esperadas por el backend
 * (ver KeystrokeServiceImpl.EXPECTED_FEATURE_KEYS).
 */

// Etiquetas de teclas en el mismo orden que el modelo.
// "period" = tecla ".", "five" = "5", "Shift.r" = Shift para la R, "Return" = Enter.
export const TARGET_PASSWORD = '.tie5Roanl';

// Identificadores de tecla -> nombre usado por el modelo.
const KEY_TO_NAME = {
  '.': 'period',
  t: 't',
  i: 'i',
  e: 'e',
  '5': 'five',
  R: 'Shift.r', // la "R" mayúscula se obtiene con Shift; el modelo usa "Shift.r"
  r: 'Shift.r',
  o: 'o',
  a: 'a',
  n: 'n',
  l: 'l',
  Enter: 'Return',
};

// Orden de las teclas "base" (las que generan H, y las transiciones DD/UD).
const SEQUENCE = [
  'period', 't', 'i', 'e', 'five', 'Shift.r', 'o', 'a', 'n', 'l', 'Return',
];

/**
 * Clase que acumula eventos de teclado y calcula las features.
 * Uso:
 *   const cap = new KeystrokeCapture();
 *   cap.record(keydownEvent); ...
 *   const features = cap.compute();  // { 'H.period': ..., 'DD.period.t': ..., ... }
 */
export class KeystrokeCapture {
  constructor(sequence = SEQUENCE) {
    this.sequence = sequence;
    this.downTimes = {}; // name -> timestamp (ms)
    this.upTimes = {};   // name -> timestamp (ms)
  }

  /**
   * Registra un evento keydown/keyup.
   * @param {KeyboardEvent} event
   * @param {number} now performance.now() (ms)
   */
  record(event, now = performance.now()) {
    const name = this._resolveName(event);
    if (!name) return false;

    if (event.type === 'keydown') {
      // Solo guardar la primera pulsación (ignorar auto-repeat del SO).
      if (this.downTimes[name] === undefined) {
        this.downTimes[name] = now;
      }
    } else if (event.type === 'keyup') {
      this.upTimes[name] = now;
    }
    return true;
  }

  _resolveName(event) {
    const key = event.key;
    if (KEY_TO_NAME[key]) return KEY_TO_NAME[key];
    // Shift que acompaña a la R: no lo tratamos como tecla propia,
    // porque el modelo agrupa "R con Shift" como una sola tecla "Shift.r".
    return undefined;
  }

  reset() {
    this.downTimes = {};
    this.upTimes = {};
  }

  /**
   * Verifica que se hayan capturado todas las teclas necesarias.
   * @returns {{complete: boolean, missing: string[]}}
   */
  checkComplete() {
    const missing = this.sequence.filter((name) => this.downTimes[name] === undefined);
    return { complete: missing.length === 0, missing };
  }

  /**
   * Calcula las 31 features. Lanza error si faltan teclas.
   * @returns {Object<string, number>}
   */
  compute() {
    const { complete, missing } = this.checkComplete();
    if (!complete) {
      throw new Error(
        `No se capturaron todas las teclas. Faltan: ${missing.join(', ')}.`,
      );
    }

    const features = {};

    // H.* (hold time)
    for (const name of this.sequence) {
      const down = this.downTimes[name];
      const up = this.upTimes[name];
      if (up === undefined) {
        throw new Error(`No se registró el keyup de "${name}".`);
      }
      features[`H.${name}`] = round((up - down) / 1000); // a segundos
    }

    // DD.* y UD.* (transiciones entre teclas consecutivas)
    for (let i = 0; i < this.sequence.length - 1; i += 1) {
      const cur = this.sequence[i];
      const next = this.sequence[i + 1];
      const downCur = this.downTimes[cur];
      const upCur = this.upTimes[cur];
      const downNext = this.downTimes[next];

      features[`DD.${cur}.${next}`] = round((downNext - downCur) / 1000);
      features[`UD.${cur}.${next}`] = round((downNext - upCur) / 1000);
    }

    return features;
  }
}

function round(value) {
  return Math.round(value * 10000) / 10000; // 4 decimales como el dataset
}
