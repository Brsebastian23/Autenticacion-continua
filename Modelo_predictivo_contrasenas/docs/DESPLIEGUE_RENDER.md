# Despliegue en Render — guía completa y correcciones aprendidas

> **Contexto.** Este documento recoge el proceso real de despliegue del sistema completo
> (Front + Backend + ML) en Render, **incluyendo los problemas encontrados y cómo se corrigieron**.
> Sirve como guía reproducible y como registro de decisiones. Complementa la §11 del README.

---

## 18.1. Arquitectura de despliegue

```
                         ┌───────────────────────────────┐
                         │   Render (3 Web Services + 1 DB) │
                         └───────────────────────────────┘
    ┌──────────────────┐   ┌──────────────────────────┐   ┌────────────────────────────┐
    │ continuous-auth- │   │ continuous-auth-backend   │   │ continuous-auth-ml          │
    │ front (static)   │──►│ (Docker, Spring Boot)     │──►│ (Docker, Django)            │
    │ React build      │   │ JWT, orquestación          │   │ IsolationForest + auditoría │
    └──────────────────┘   └──────────────────────────┘   └────────────────────────────┘
              │                        │                              │
              │ VITE_API_URL           │ ML_BASE_URL                  │ DATABASE_URL
              └──── (URL backend+/api) ─┘──── (URL ML) ───────────────┘
                                                     │
                                          ┌──────────▼──────────┐
                                          │ continuous-auth-db  │  (PostgreSQL)
                                          └─────────────────────┘
```

Tres servicios independientes que se comunican por **HTTP/JSON**, con una base PostgreSQL
compartida por backend y ML (tablas disjuntas).

---

## 18.2. Cómo desplegar (Blueprint)

### Paso 1 — Subir el código
```bash
git add -A
git commit -m "Preparación de despliegue: render.yaml, persistencia, cursor, métricas, umbral"
git push origin main
```

### Paso 2 — Crear el Blueprint
1. Render → **New** → **Blueprint** → conectar el repositorio.
2. Render detecta `render.yaml` en la raíz → crea 3 servicios + 1 base de datos.

### Paso 3 — Variables a añadir a mano (las únicas 2)
| Servicio | Key | Valor | Nota |
|---|---|---|---|
| `continuous-auth-backend` | `ML_BASE_URL` | `https://continuous-auth-ml.onrender.com` | **sin** `/api`, **con** `https://` |
| `continuous-auth-front` | `VITE_API_URL` | `https://continuous-auth-backend.onrender.com/api` | **con** `/api`, **con** `https://` |

> ⚠️ Usa las URLs **reales** que Render asigne (cópialas del panel). Si el nombre se repite,
> Render añade un sufijo.

### Paso 4 — Redeploy con las variables
- **Backend**: `Restart`/redeploy (lee env al arrancar).
- **Front**: **obligatorio `Clear build cache & deploy`**. Vite **incrusta** `VITE_API_URL` en el
  build; un simple restart NO la actualiza.

### Paso 5 — Verificación
```bash
# ML vivo (JSON)
curl https://continuous-auth-ml.onrender.com/api/metrics/summary/
# Backend vivo (JSON)
curl https://continuous-auth-backend.onrender.com/api/metrics/summary
# Front
# abrir https://continuous-auth-front.onrender.com  -> registro/login
```

---

## 18.3. Problemas encontrados y correcciones (registro)

Estas son las incidencias reales durante el despliegue y su resolución. **Es la parte más
importante de este documento**: documenta el aprendizaje.

### 18.3.1. `render.yaml` en `runtime: python` ignoraba el entrypoint
- **Síntoma**: el contenedor no hacía migrate/seed/benchmark; Dependencia del `build.sh`.
- **Causa**: con `runtime: python` Render **no ejecuta** el `docker-entrypoint.sh` del Dockerfile.
- **Corrección**: pasar a **`runtime: docker`**, de modo que el `ENTRYPOINT` sí se ejecuta (migra,
  siembra modelos faltantes y genera benchmark).

### 18.3.2. URL del modelo sin esquema rompía el cliente Java
- **Síntoma**: al usar `fromService ... property: hostport`, el backend recibía `host:puerto`
  **sin** `http://`.
- **Causa**: `WebClient.baseUrl(...)` (Spring) y el front necesitan una **URL completa con esquema**.
- **Corrección**: dejar `ML_BASE_URL` y `VITE_API_URL` como **`sync: false`** (se rellenan a mano con
  `https://...`), en lugar de resolverlas con `fromService`.

### 18.3.3. Login devolvía error confuso (`can't access property "token", … is null`) en el front
- **Síntoma**: al hacer login, el navegador lanzaba un TypeError en `auth.token`.
- **Diagnóstico**: en `client.js`, si la respuesta no es JSON parseable, `request()` devuelve `null`;
  `App.handleAuthenticated(auth)` hacía `auth.token` → excepción. Ocurría cuando el front llamaba a
  una URL sin `/api` o sin desplegar la variable (petición al propio origen / HTML de error).
- **Corrección (despliegue)**: asegurar `VITE_API_URL=.../api` + **rebuild** del front.
- **Corrección (robustez, recomendada)**: en `App.handleAuthenticated`, **validar** `auth` y
  mostrar un error legible en vez de lanzar. *(Ver §18.5, mejora pendiente).*

### 18.3.4. «El usuario s002 no existe» al verificar contra el modelo del dataset
- **Síntoma**: `POST /api/predict/` devolvía `404 El usuario "s002" no existe. Invoca primero
  /api/retrain/.`
- **Causa raíz**: **no es que falte el `.joblib`**; los `.joblib` del dataset **sí** están en la
  imagen. Lo que faltaba era la fila **`UserProfile('s002')`** en la base de datos de Render (base
  nueva y vacía). `PredictAuthView` exige `UserProfile` **antes** de mirar el modelo.
- **Decisión de producto**: **no** sembrar `UserProfile` del dataset; en su lugar, el flujo correcto
  es que **cada usuario entrene su propio modelo** (§6.3), que crea su `UserProfile('user-<name>')`
  y su `.joblib`, y verifique contra él. Así se evita depender de perfiles de dataset en producción.
- **Verificación**: el flujo —registrarse → entrenar → verificar— **no toca `s002`** y funciona de
  extremo a extremo.

### 18.3.5. Modelo de usuario se pierde en plan gratuito → error al verificar
- **Síntoma (latente)**: tras redeploy o "dormir" el servicio (plan free), el `.joblib` de usuario
  desaparece, pero `UserProfile` y `trainedModelId` siguen en la BD → verificación falla con
  «No existe un modelo entrenado…».
- **Causa**: plan free **no tiene Disco**; el filesystem del contenedor es efímero.
- **Mitigación actual**: documentar la limitación; el modelo se regenera al **re-entrenar**.
- **Mejora recomendada (§18.5)**: si el ML responde 404 por modelo ausente, el backend debe
  **marcar `trained=false`** y devolver un mensaje claro «vuelve a entrenar».

### 18.3.6. `.dockerignore` copiaba `.venv` a la imagen del ML
- **Síntoma**: builds lentos y enormes.
- **Causa**: el `.dockerignore` excluía `venv/` pero el entorno local se llama **`.venv/`**.
- **Corrección**: añadir `.venv/` al `.dockerignore`.

### 18.3.7. Modelos de cursor (`cursor_iforest_*.joblib`) se colaban en git
- **Síntoma**: `git status` mostraba un `.joblib` de cursor en `Modelo_predictivo_contrasenas/ml_models/`.
- **Causa**: el `.gitignore` tenía `ml_models/cursor_iforest_*.joblib` (relativo a la raíz); en la
  subcarpeta **no aplicaba**.
- **Corrección**: cambiar a `**/ml_models/cursor_iforest_*.joblib` y `**/ml_models/iforest_user-*.joblib`.
  Los modelos del **dataset** (`iforest_sXXX.joblib`) **sí** se versionan (van en la imagen).

### 18.3.8. `.vscode/` con posible configuración local
- **Corrección**: añadir `.vscode/` al `.gitignore` y `git rm --cached .vscode/settings.json`
  (archivo local intacto, dejó de versionarse).

### 18.3.9. Desarrollo local: `VITE_API_URL` mal configurada → 404 en login
- **Síntoma**: en local, login daba 404 porque el front pedía `/auth/login` (sin `/api`).
- **Causa**: `VITE_API_URL` quedó con un valor que no incluía `/api`.
- **Corrección**: `VITE_API_URL=/api` (relativa) + el **proxy de Vite** (`vite.config.js`) hacia
  `http://localhost:8080`. Es la forma correcta en desarrollo.

---

## 18.4. Tabla de variables de entorno por servicio (referencia rápida)

### ML (`continuous-auth-ml`)
| Key | Valor | Origen |
|---|---|---|
| `DJANGO_DEBUG` | `false` | yaml |
| `DJANGO_SECRET_KEY` | *(generada)* | `generateValue` |
| `WEB_CONCURRENCY` | `2` | yaml |
| `ML_DECISION_THRESHOLD` | `0.021328` | yaml |
| `ML_USER_MODELS_DIR` | `/data/user_models` | **solo con Disco (plan pago)** |
| `DATABASE_URL` | *(Postgres)* | `fromDatabase` |

### Backend (`continuous-auth-backend`)
| Key | Valor | Origen |
|---|---|---|
| `APP_JWT_SECRET` | *(generada)* | `generateValue` |
| `CORS_ALLOWED_ORIGINS` | `*` | yaml |
| **`ML_BASE_URL`** | `https://...-ml.onrender.com` | **manual** |
| `DATABASE_URL` | *(Postgres)* | `fromDatabase` |

### Front (`continuous-auth-front`)
| Key | Valor | Origen |
|---|---|---|
| **`VITE_API_URL`** | `https://...-backend.onrender.com/api` | **manual** |

---

## 18.5. Mejoras pendientes (recomendadas, no implementadas aún)

1. **Robustez del front ante login sin JSON**: validar `auth` en `App.handleAuthenticated`.
2. **Detección de modelo ausente**: si el ML responde 404, el backend marca `trained=false` y pide
   re-entrenar (resuelve §18.3.5 de forma elegante).
3. **Persistencia real en free**: `ML_USER_MODELS_DIR` solo persiste con Disco (plan pago). Alternativa
   gratuita: almacenamiento de objetos (Supabase Storage / S3 / R2).
4. **CORS**: fijar `CORS_ALLOWED_ORIGINS` al dominio del front en producción en lugar de `*`.

---

## 18.6. Plan gratuito vs plan pago (impacto en el sistema)

| Aspecto | Plan Free | Plan Starter (+ Disco) |
|---|---|---|
| Discos persistentes | ❌ | ✅ |
| Modelos de usuario/cursor | Se pierden al redeploy/dormir | Persisten en `/data/user_models` |
| Modelos del dataset | ✅ (en imagen) | ✅ (en imagen) |
| Servicio se "duerme" (15 min) | ✅ (cold start ~50 s) | Configurable |
| PostgreSQL | Expira a los 30 días | Persistente |

**Conclusión para el alcance académico**: el plan free permite **demostrar** el sistema completo
(registro, entrenamiento, verificación de tecleo y cursor, métricas EER), aceptando que los modelos
**propios** se regeneran con el re-entrenamiento tras cada redeploy. La persistencia permanente se
declara como requisito de producción (plan pago o almacenamiento de objetos).
