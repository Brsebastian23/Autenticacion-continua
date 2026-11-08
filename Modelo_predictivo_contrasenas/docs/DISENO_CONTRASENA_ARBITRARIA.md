# Diseño: soporte de contraseña arbitraria

> **Estado:** propuesta de diseño. **No se ha modificado** el flujo actual.
> La funcionalidad existente (contraseña fija `.tie5Roanl` + `Return`, 31
> features CMU) permanece intacta y es la que usan el dataset y los modelos
> entrenados hoy.

## 1. Motivación

El sistema actual está acoplado a la secuencia fija `.tie5Roanl` + `Return`
porque el dataset público CMU DSL-StrongPasswordData solo contiene esa
contraseña, y las 31 features (`H.*`, `DD.*`, `UD.*`) se calculan sobre sus
teclas.

Esto es una **limitación cultural**: el modelo asume una contraseña concreta en
un teclado QWERTY en inglés. Un usuario real elige su propia contraseña, que
puede contener teclas distintas, otra longitud u otro idioma de teclado.

## 2. Objetivo

Permitir que un usuario entrene y verifique con **su propia contraseña**,
manteniendo el esquema actual como caso particular (retrocompatible).

## 3. Principio de diseño

No se cambia nada del flujo actual. Se añade una **capa de generalización**
opcional seleccionada por configuración (`password_mode`):

| `password_mode` | Descripción | Estado |
|---|---|---|
| `fixed` (por defecto) | Secuencia `.tie5Roanl` + Return, 31 features CMU. | **Actual, sin cambios** |
| `arbitrary` | Cualquier secuencia; features derivadas dinámicamente. | Propuesta |

## 4. Esquema de features para contraseña arbitraria

### 4.1. Features por tecla (dinámicas)

Para una secuencia de `n` teclas se generan:

- `n` features `H.<key_i>` (hold time de cada pulsación).
- `(n-1)` features `DD.<key_i>.<key_{i+1}>` (down-down entre consecutivas).
- `(n-1)` features `UD.<key_i>.<key_{i+1}>` (up-down entre consecutivas).

Total: `3n - 2` features. Para `.tie5Roanl` + Return (`n = 12`) son `34`, pero
el dataset no incluye las 3 asociadas a transiciones que el CMU omite; el
esquema actual (31) se conserva en `fixed`.

### 4.2. Normalización de nombres de tecla

Se usa una función canónica `key_label(event)`:

- Letras: `event.code` (físico, `KeyT`) para ser independiente de mayúsculas.
- Números: `Digit5`.
- Signos: `Period`, `Comma`, ...
- Modificadores: se combinan con la tecla base igual que hoy (`Shift.r`).
- Retorno: `Return`.

Los nombres se derivan del **código físico** de la tecla, no del carácter, para
que un teclado en español (donde `;` está en otra posición) no rompa el mapeo.

### 4.3. Features agregadas (independientes de la longitud)

Para comparar contraseñas de distinta longitud entre sí y dar robustez:

- `A.n_keys`, `A.hold_mean`, `A.hold_std`, `A.dd_mean`, `A.dd_std`,
  `A.ud_mean`, `A.ud_std`, `A.total_duration`, `A.typing_speed`.

Estas 9 features agregadas permiten reutilizar el modelo cuando cambia la
longitud de la contraseña entre sesiones.

## 5. Persistencia del esquema

El modelo `.joblib` guarda, junto al estimator, el **esquema concreto** con el
que fue entrenado:

```python
bundle = {
    'model': model,
    'features': feature_list,        # nombres en orden
    'password_mode': 'arbitrary',
    'sequence': ['Period', 'KeyT', ...],  # secuencia canónica usada
    'user_id': user_id,
}
```

Así la inferencia valida que el record trae exactamente las features del
esquema guardado, sin asumir las 31 del CMU.

## 6. Cambios necesarios (cuando se implemente)

1. **Front** (`keystroke.js`): capturar la secuencia tecleada en lugar de la
   fija; generar features con `3n - 2 + agregadas`.
2. **ml_service**: `record_to_vector` acepta el esquema del bundle y valida
   contra él en vez de contra `FEATURE_COLUMNS` global.
3. **views/contrato**: `POST /api/retrain/` acepta opcionalmente
   `password_mode` y `sequence`. Si se omite, se comporta como hoy (`fixed`).
4. **Backend Java**: `User` gana `passwordMode` (por defecto `fixed`); el
   validador de features se parametriza por modo.

## 7. Retrocompatibilidad

- Con `password_mode = fixed` (valor por defecto) **el sistema se comporta
  exactamente igual que hoy**, incluidos los 51 modelos del dataset.
- Los modelos existentes guardan implícitamente el esquema CMU; al cargarlos,
  si el bundle no trae `password_mode`, se asume `fixed`.

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Features con distinta longitud entre sesiones | Features agregadas (4.3) permiten comparar. |
| Teclados de distintos idiomas | Nombres por `event.code`, no por carácter. |
| Datos insuficientes para contraseñas largas | Reentrenar por sesión; mínimo de muestras configurable. |
| Regresión del flujo fijo | `password_mode` por defecto `fixed` + tests de regresión. |
