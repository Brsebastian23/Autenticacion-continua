# Autenticación Continua por Dinámica de Teclado y Cursor (Keystroke + Mouse Dynamics)

Sistema de autenticación que no solo verifica **qué** contraseña se escribe, sino **cómo** se
escribe y **cómo** se mueve el cursor. A partir de la dinámica de tecleo (31 features) y de la
dinámica del cursor (12 features), modelos de *machine learning* (`IsolationForest`, uno por
usuario y por modalidad) deciden si la persona que está frente al equipo es realmente quien dice
ser o un impostor.

Este repositorio implementa el sistema completo en tres piezas independientes:

| Componente | Tecnología | Rol |
|---|---|---|
| **Front/** | React + Vite | Captura los tiempos de tecleo y el movimiento del cursor; calcula las features. |
| **Backend/** | Spring Boot (Java 17) | Autenticación con contraseña, usuarios, JWT y orquestación con los modelos. |
| **Modelo_predictivo_contrasenas/** | Django + DRF + scikit-learn | Microservicio de ML: entrena, evalúa y audita los modelos IsolationForest (tecleo y cursor). |

> Este README documenta **todo** el sistema: por qué existe, para qué sirve, cómo fluye una
> petición de principio a fin, **cómo se calculan las anomalías** y **cómo se mide su exactitud
> (EER/FAR/FRR/AUC)**. Los documentos de `Modelo_predictivo_contrasenas/docs/` profundizan en
> despliegue, perspectivas éticas/sociales y la evaluación por criterios.

---

## Índice

1. [¿Por qué y para qué existe este sistema?](#1-por-qué-y-para-qué-existe-este-sistema)
2. [Concepto: dinámica de teclado](#2-concepto-dinámica-de-teclado)
3. [Arquitectura general](#3-arquitectura-general)
4. [Las 31 features de tecleo: cómo se calculan](#4-las-31-features-de-tecleo-cómo-se-calculan)
5. [Cómo se calculan las anomalías (el núcleo)](#5-cómo-se-calculan-las-anomalías-el-núcleo)
6. [Flujo completo de usuario y de datos](#6-flujo-completo-de-usuario-y-de-datos)
7. [Frontend: captura de tecleo y cursor](#7-frontend-captura-de-tecleo-y-cursor)
8. [Backend: autenticación y orquestación](#8-backend-autenticación-y-orquestación)
9. [Microservicio de ML: entrenamiento, inferencia y auditoría](#9-microservicio-de-ml-entrenamiento-inferencia-y-auditoría)
10. [Métricas de evaluación (FAR, FRR, EER, AUC)](#10-métricas-de-evaluación-far-frr-eer-auc)
11. [Despliegue y ejecución](#11-despliegue-y-ejecución)
12. [Variables de entorno](#12-variables-de-entorno)
13. [Estructura del repositorio](#13-estructura-del-repositorio)
14. [Estado actual y limitaciones conocidas](#14-estado-actual-y-limitaciones-conocidas)
15. [Dinámica del cursor (mouse dynamics)](#15-dinámica-del-cursor-mouse-dynamics)
16. [Medición de exactitud: benchmark EER](#16-medición-de-exactitud-benchmark-eer)
17. [Pruebas automatizadas](#17-pruebas-automatizadas)
18. [Despliegue en Render (guía y correcciones)](#18-despliegue-en-render-guía-y-correcciones)
19. [Perspectivas éticas, sociales y humanas](#19-perspectivas-éticas-sociales-y-humanas)
20. [Referencias](#20-referencias)

---

## 1. ¿Por qué y para qué existe este sistema?

### 1.1. El problema

La autenticación tradicional valida **un secreto** (una contraseña). Una vez que ese secreto se
filtra o se comparte, la barrera desaparece: cualquiera que conozca la contraseña puede pasar. No
hay forma de saber si la persona del teclado es el dueño legítimo. Además, la contraseña solo
protege el momento del login; una vez iniciada la sesión, no hay verificación continua.

### 1.2. La idea

Añadir una **segunda señal biométrica pasiva**: el *cómo* se teclea. Cada persona tiene un patrón
motor de escritura difícil de imitar conscientemente —cuánto mantiene pulsada cada tecla, cuánto
tarda el dedo en saltar de una tecla a otra—. Estos tiempos son consistentes para un usuario e
inconscientes de falsificar para un impostor.

### 1.3. Para qué sirve (casos de uso)

- **Refuerzo del login**: además de la contraseña correcta, comprobar que el patrón de tecleo
  coincide con el del usuario registrado.
- **Autenticación continua**: verificar muestras de tecleo durante la sesión para detectar si un
  tercero tomó el control (de ahí el nombre del proyecto).
- **Detección de suplantación**: marcar como *anomalía* los intentos que se escriben con la
  contraseña correcta pero con un ritmo de tecleo ajeno.

### 1.4. Por qué esta arquitectura

- **Microservicios**: la inteligencia biométrica (Python + scikit-learn) vive separada del backend
  de negocio (Java). Así el modelo se puede reentrenar, versionar y escalar sin tocar la
  autenticación.
- **Sin interferir con el flujo normal**: la contraseña sigue siendo la barrera principal; el
  tecleo actúa como señal adicional y auditable.

---

## 2. Concepto: dinámica de teclado

Cada pulsación de tecla genera dos eventos: **keydown** (cuando el dedo baja) y **keyup** (cuando
sube). De sus marcas de tiempo se derivan tres familias de métricas:

| Familia | Nombre | Fórmula | Qué mide |
|---|---|---|---|
| **H** | *Hold time* | `keyup(X) − keydown(X)` | Cuánto tiempo se mantiene pulsada una tecla. |
| **DD** | *Down-down latency* | `keydown(Y) − keydown(X)` | Tiempo entre pulsar dos teclas consecutivas. |
| **UD** | *Up-down latency* | `keydown(Y) − keyup(X)` | Tiempo de "vuelo" entre soltar una tecla y pulsar la siguiente. |

El sistema usa como contraseña objetivo la del dataset público **CMU DSL-StrongPasswordData**:

```
.  t  i  e  5  R  o  a  n  l   →   cadena ".tie5Roanl" + Return (Enter)
```

Esa secuencia tiene **11 teclas** (incluyendo `Shift.r` como la "R" mayúscula y `Return` como
Enter), lo que produce exactamente las **31 features** que veremos en la §4.

---

## 3. Arquitectura general

```
┌──────────────────────┐   HTTP/JSON (JWT)   ┌────────────────────────┐   HTTP/JSON   ┌──────────────────────────────┐
│        Front         │ ──────────────────► │        Backend         │ ────────────► │     Microservicio ML         │
│  React + Vite        │                     │  Spring Boot (Java 17) │               │  Django + DRF + scikit-learn │
│                      │                     │                        │               │                              │
│ • Captura keydown/up │                     │ • /api/auth/*          │               │ • /api/retrain/              │
│ • Calcula 31 features│                     │ • /api/keystroke/train │               │ • /api/predict/              │
│ • Muestra resultado  │                     │ • /api/keystroke/verify│               │ • /api/cursor/*  • metrics/* │
└──────────────────────┘                     └───────────┬────────────┘               └──────────────┬───────────────┘
                                                         │                                            │
                                                   ┌─────▼──────┐                        ┌────────────┼────────────┐
                                                   │ H2/Postgres│                        ▼            ▼            ▼
                                                   │ (usuarios) │                 ┌──────────────┐ ┌──────────┐ ┌──────────┐
                                                   └────────────┘                 │ ml_service   │ │ ml_models│ │ DB       │
                                                                                  │ Isolation-   │ │ *.joblib │ │ auditoría│
                                                                                  │ Forest       │ │ por user │ │ (SQLite/ │
                                                                                  └──────────────┘ └──────────┘ │Postgres) │
                                                                                                                 └──────────┘
```

**Responsabilidad de cada capa:**

1. **Front** — No tiene lógica biométrica. Solo *mide* tiempos del teclado, los convierte en el
   diccionario de 31 features y muestra el veredicto.
2. **Backend** — Es el guardián de la identidad. Gestiona usuarios, hashea contraseñas (BCrypt),
   emite y valida JWT, y **decide qué modelo usar** (el propio del usuario o el del dataset). Delega
   la inferencia al servicio Python y nunca habla directamente con scikit-learn.
3. **Microservicio ML** — Es el cerebro. Contiene el modelo IsolationForest, entrena, predice y deja
   **auditoría** de cada inferencia en base de datos.

Una decisión clave de diseño es que el **backend nunca confía** en features no validadas: exige
exactamente las 31 claves antes de llamar al modelo (`KeystrokeFeatureValidator`). Esto da errores
claros y tempranos en lugar de fallos crípticos del servicio Python.

---

## 4. Las 31 features de tecleo: cómo se calculan

Las 31 features se derivan de las 11 teclas de `.tie5Roanl` + Return. Se calculan **en el
navegador** (`Front/src/services/keystroke.js`) y su *nombre* coincide exactamente con la columna
del CSV CMU, para que el modelo Python las entienda sin traducción.

### 4.1. Las teclas (en orden)

```
period, t, i, e, five, Shift.r, o, a, n, l, Return
    .    t  i  e   5     R        o  a  n  l   Enter
```

### 4.2. Familia H — Hold time (11 features)

Una por tecla: cuánto se mantuvo pulsada.

```
H.period  H.t  H.i  H.e  H.five  H.Shift.r  H.o  H.a  H.n  H.l  H.Return
```

Para cada tecla `X`: **`H.X = keyup(X) − keydown(X)`**.

### 4.3. Familias DD y UD — Transiciones (10 + 10 features)

Para cada par de teclas consecutivas `(X → Y)`:

```
DD.X.Y = keydown(Y) − keydown(X)   (10 features: DD.period.t ... DD.l.Return)
UD.X.Y = keydown(Y) − keyup(X)     (10 features: UD.period.t ... UD.l.Return)
```

### 4.4. Detalles de implementación

- **Unidades**: el navegador mide en milisegundos con `performance.now()`; se dividen entre 1000
  para expresar en **segundos** (como el dataset CMU) y se redondean a **4 decimales**.
- **Auto-repeat**: solo se guarda la **primera** pulsación de cada tecla (se ignora la repetición
  automática del sistema operativo).
- **Shift de la R**: `Shift` acompañando a la `R` **no** se cuenta como tecla independiente; la
  mayúscula `R` se registra como una única tecla `Shift.r`.
- **Validación previa**: antes de calcular, se comprueba que se hayan capturado todas las teclas
  (`checkComplete()`); si falta alguna, se rechaza la muestra localmente.

Resultado final: un diccionario JSON con **31 claves numéricas** iguales a las columnas del CSV:

```json
{
  "H.period": 0.1491, "H.t": 0.0455, "H.i": 0.0932, "...": "...",
  "DD.period.t": 0.3979, "DD.t.i": 0.1152, "...": "...",
  "UD.period.t": 0.2488, "UD.t.i": 0.0697, "...": "..."
}
```

---

## 5. Cómo se calculan las anomalías (el núcleo)

Esta es la parte central del sistema. La pregunta que responde es:

> *Dado un patrón de tecleo, ¿pertenece al usuario del modelo o es de otra persona?*

### 5.1. El tipo de problema manda: autenticación de una sola clase

Un clasificador supervisado clásico ("legítimo vs impostor") **no es viable aquí**, porque en
producción **solo tenemos muestras del usuario legítimo**. Cuando alguien se registra, escribe su
contraseña unas cuantas veces; no existe un conjunto de "intentos de impostores contra este usuario
concreto". El espacio de "no-X" es enorme e inabarcable.

Por eso el sistema usa **detección de anomalías**: se aprende la *forma* del tecleo legítimo y se
marca como sospechoso lo que se aleja de ella. Un modelo **por usuario**.

### 5.2. El algoritmo: IsolationForest (scikit-learn)

**Configuración** (`Modelo_predictivo_contrasenas/authentication_api/ml_service.py`):

```python
IFOREST_PARAMS = {
    'n_estimators': 200,      # 200 árboles -> score estable y poco ruidoso
    'max_samples': 'auto',    # submuestras (mejora la separación por diseño)
    'contamination': 0.1,     # asume ~10% de muestras atípicas
    'random_state': 42,       # reproducibilidad
    'n_jobs': -1,             # paraleliza
}
MIN_TRAINING_SAMPLES = 3
```

**Cómo funciona IsolationForest, en una idea:** construye 200 árboles; en cada uno, "aísla" puntos
cortando el espacio aleatoriamente (elige una feature, un valor de corte, divide) hasta dejar cada
punto solo.

- Un **punto normal** (rodeado de vecinos parecidos) necesita **muchos cortes** para aislarse.
- Un **punto anómalo** (lejos de la nube) se aísla con **pocos cortes**.

La **profundidad media del camino** es el score: camino corto -> anómalo; camino largo -> normal.
Es justo lo que devuelve `decision_function`.

### 5.3. La fórmula de decisión

Para cada muestra se llama a `model.decision_function(vector)`, que devuelve un **score continuo**:

- `score >= 0` -> el punto es "normal" respecto a la nube de entrenamiento -> **LEGITIMATE**.
- `score < 0`  -> el punto es atípico -> **ANOMALY**.

En código (`ml_service.predict`):

```python
score = float(model.decision_function(vector)[0])
is_legitimate = score >= float(settings.ML_DECISION_THRESHOLD)   # umbral configurable
```

Donde `ML_DECISION_THRESHOLD` es configurable por entorno. Por defecto se usa el
**umbral óptimo calibrado `+0.021328`** (minimiza |FAR − FRR|), quedando `0.0` (la frontera
natural del algoritmo) como **línea base** documentada. **Subir el umbral** endurece la
verificación (menos impostores aceptados, más usuarios legítimos rechazados); bajarlo hace lo
contrario. Es la palanca de política de riesgo FAR vs FRR.

El score se devuelve tal cual al frontend como `confidence_score`, junto con la decisión y la
latencia. La decisión queda además clasificada como `LEGITIMATE`, `ANOMALY` o `ERROR` en la tabla de
auditoría.

### 5.4. Intuición aplicada a keystroke dynamics

- Un **usuario legítimo** teclea con un ritmo consistente: sus `H`, `DD`, `UD` caen siempre en la
  misma región del espacio de 31 dimensiones -> caminos largos -> score alto.
- Un **impostor** teclea diferente: sus tiempos se salen de esa región -> se aísla rápido -> score
  bajo.

No hace falta modelar la distribución exacta del usuario; basta con detectar cuándo un punto está
**lejos y aislado** de la nube legítima.

### 5.5. Por qué IsolationForest y no otras alternativas

| Alternativa | Por qué se descartó |
|---|---|
| One-Class SVM | Exige normalización, ajuste de kernel y de `nu`; coste O(n²)-O(n³), sensible a escala. |
| LOF | Transductivo; sin `predict` limpio sobre muestras nuevas. |
| Autoencoder | Sobredimensionado para 31 features tabulares; más infraestructura y ajuste. |
| Gaussian / Elliptic Envelope | Asume forma gaussiana/esférica que el tecleo no cumple. |
| **IsolationForest** | Escala bien, no asume distribución, sin normalización obligatoria, `predict`/`decision_function` estables sobre muestras nuevas, baja latencia (~10-20 ms) y reproducible. |

### 5.6. La debilidad que reconocemos

IsolationForest aprende "no parecerse a nadie del entrenamiento", no "ser el usuario X". Un impostor
que teclea de forma *rara pero globalmente normal* puede quedar cerca del umbral y pasar. Esto se
refleja en un **FAR relativamente alto (~27 %)** con el umbral por defecto. Se gestiona con el
umbral y está documentado como el punto a mejorar con un enfoque híbrido (ver §14).

### 5.7. Entrenamiento por usuario y persistencia

- Cada usuario tiene **su propio** modelo: `ml_models/iforest_<user_id>.joblib`.
- El entrenamiento se dispara desde `/api/retrain/` con las muestras capturadas.
- La escritura es **atómica** (archivo temporal + `os.replace`) para no dejar modelos corruptos.
- Se valida que haya >= 3 muestras y que cada vector tenga exactamente 31 valores finitos.

---

## 6. Flujo completo de usuario y de datos

### 6.1. Registro + login

```
Front (AuthScreen) -> POST /api/auth/register {username, password, keystrokeModelId}
                   -> POST /api/auth/login    {username, password}
                              |
                              v
   Backend crea usuario (password BCrypt), guarda keystrokeModelId
   (modelo del dataset elegido, p. ej. "s002") y devuelve un JWT.
```

El `keystrokeModelId` permite **probar** con un modelo preentrenado del dataset mientras el usuario
aún no ha entrenado el suyo.

### 6.2. Verificación (probar el modelo)

```
Front (KeystrokeTester)
  |  Usuario escribe ".tie5Roanl" + Enter
  |  KeystrokeCapture.record() en keydown/keyup -> compute() -> 31 features
  v
POST /api/keystroke/verify  (JWT)  {features}
  |
  v
Backend:
  - Resuelve usuario desde el JWT
  - Valida las 31 claves (KeystrokeFeatureValidator)
  - Elige modelo activo: trainedModelId (propio) o keystrokeModelId (dataset)
  |
  v
POST http://ml/api/predict/  {user_id, record}
  |
  v
Microservicio ML:
  - load_model(user_id)
  - record_to_vector(record) -> [1,31]
  - score = decision_function(...)
  - is_legitimate = score >= threshold
  - GUARDA en AuthInferenceLog (score, decisión, estado, latencia, timestamp)
  |
  v
Respuesta {is_legitimate, confidence_score, status_code, latency_ms, ...}
  -> Front muestra LEGÍTIMO / ANOMALÍA + score + latencia + historial
```

### 6.3. Entrenamiento del modelo propio

```
Front (TrainingScreen)
  |  Usuario repite la contraseña N veces (por defecto 10)
  |  Cada repetición -> 31 features (samples[])
  v
POST /api/keystroke/train  (JWT)  {samples: [ {31 features}, ... ]}
  |
  v
Backend:
  - Valida cada muestra (31 claves; mínimo 3)
  - userModelId = "user-<username>"   (NUNCA toca el modelo del dataset)
  |
  v
POST http://ml/api/retrain/  {user_id: userModelId, records: samples}
  |
  v
Microservicio ML: IsolationForest.fit(matrix) -> joblib atómico -> UserProfile actualizado
  |
  v
Backend guarda trainedModelId = userModelId en el usuario
  -> Desde ahora la verificación usa el modelo PROPIO
```

### 6.4. Qué modelo se usa al verificar

```
activeModelId = trainedModelId (si existe)  O  keystrokeModelId (modelo del dataset)
```

- Si el usuario **no** ha entrenado: se compara contra un modelo del dataset (`sXXX`), útil para
  demostrar el sistema sin entrenamiento previo.
- Si el usuario **sí** ha entrenado: se compara contra `user-<username>`, su patrón real.

Esta lógica vive en la entidad `User` del backend (`activeModelId()`), de modo que el modelo del
dataset es de **solo lectura** y nunca se sobrescribe.

---

## 7. Frontend: captura de tecleo y cursor

**Stack**: React 18 + Vite. Sin dependencias de ML en el cliente.

| Archivo | Responsabilidad |
|---|---|
| `src/services/keystroke.js` | Clase `KeystrokeCapture`: registra keydown/keyup y calcula las 31 features. |
| `src/api/client.js` | Cliente HTTP hacia el backend (`VITE_API_URL`). Envía JWT en `Authorization`. |
| `src/components/AuthScreen.jsx` | Login / registro. |
| `src/components/KeystrokeTester.jsx` | Escribe la contraseña, verifica y muestra decisión/score/latencia + historial. |
| `src/components/TrainingScreen.jsx` | Captura 10 repeticiones y entrena el modelo propio. |
| `src/App.jsx` | Estado de sesión, guarda JWT en `localStorage`, alterna entre ver/entrenar. |

Un punto importante: **el front no decide nada**. Mide y envía; el veredicto siempre viene del
modelo a través del backend.

---

## 8. Backend: autenticación y orquestación

**Stack**: Spring Boot 3, Java 17, Spring Security (JWT stateless), JPA/Hibernate.

### 8.1. Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/api/auth/register` | No | Crea usuario (BCrypt) con su `keystrokeModelId`. |
| POST | `/api/auth/login` | No | Valida credenciales y emite JWT. |
| GET  | `/api/auth/me` | Si | Perfil del usuario (incluye `trained` y `activeModelId`). |
| POST | `/api/keystroke/verify` | Si | Verifica una muestra de 31 features. |
| POST | `/api/keystroke/train` | Si | Entrena el modelo propio con N muestras. |

### 8.2. Seguridad

- **Contraseñas**: hash BCrypt (`PasswordEncoder`), nunca en claro.
- **JWT**: firmado HMAC; el `JwtAuthenticationFilter` valida el token en cada petición.
- **Stateless**: `SessionCreationPolicy.STATELESS`; no hay sesión de servidor.
- **Endpoints protegidos**: todo excepto `/api/auth/**` y la consola H2.

### 8.3. Piezas clave

| Clase | Rol |
|---|---|
| `AuthServiceImpl` | Registro/login, BCrypt, emisión de JWT, perfil. |
| `KeystrokeServiceImpl` | Verificación: valida features, resuelve modelo activo, llama al cliente ML. |
| `KeystrokeTrainingServiceImpl` | Entrena el modelo `user-<username>` y persiste `trainedModelId`. |
| `KeystrokeFeatureValidator` | Exige exactamente las 31 claves esperadas. |
| `WebClientKeystrokeModelClient` | Cliente HTTP hacia `/api/predict/` y `/api/retrain/`, con timeout y reintento. |
| `User` (dominio) | `keystrokeModelId` (dataset, solo lectura) + `trainedModelId` (propio). |

### 8.4. Resiliencia del cliente ML

`WebClientKeystrokeModelClient` aplica timeouts (`read-timeout-ms`), **un reintento** ante fallos
transitorios de red y normaliza la respuesta del modelo Python a los DTO de dominio
(`ModelPrediction`, `TrainingResult`).

---

## 9. Microservicio de ML: entrenamiento, inferencia y auditoría

**Stack**: Django + Django REST Framework + scikit-learn + joblib.

### 9.1. Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/retrain/` | Entrena y persiste un IsolationForest por usuario. |
| POST | `/api/predict/` | Infiere y **audita siempre** el resultado. |

**`POST /api/retrain/`** -> `201 Created`

```json
{ "status": "trained", "user_id": "s002", "samples": 2400,
  "model_file": "iforest_s002.joblib", "features": 31,
  "training_latency_ms": 1180.4, "trained_at": "2026-10-23T01:51:31+00:00" }
```

**`POST /api/predict/`** -> `200 OK`

```json
{ "user_id": "s002", "is_legitimate": true, "confidence_score": 0.058321,
  "status_code": "LEGITIMATE", "latency_ms": 12.4, "log_id": 42,
  "timestamp": "2026-10-23T01:52:10+00:00" }
```

**Códigos de error**: `400` payload inválido · `404` usuario sin modelo · `422` datos no
procesables (features faltantes, no numéricos, NaN/infinito, menos de 3 muestras) · `500` fallo
interno (también se audita como `ERROR`).

### 9.2. Capa de servicio ML (`ml_service.py`)

| Función | Propósito |
|---|---|
| `FEATURE_COLUMNS` | Lista canónica de las 31 features. |
| `record_to_vector(record)` | Convierte dict/lista a vector float64 `[1,31]`; valida forma y finitud. |
| `build_matrix(records)` | Valida mínimo de muestras y apila vectores. |
| `train_model(user_id, records)` | `IsolationForest.fit` + persistencia atómica con joblib. |
| `load_model(user_id)` | Carga el `.joblib` o lanza error controlado. |
| `predict(user_id, record)` | `decision_function` + comparación con umbral + latencia. |
| `evaluate_model(...)` | FAR / FRR / accuracy sobre datos no vistos. |

### 9.3. Modelo de datos (auditoría)

**`UserProfile`** — perfil biométrico por usuario (`user_id` PK, `training_samples`,
`model_trained_at` y timestamps).

**`AuthInferenceLog`** — una fila por cada inferencia (incluidos errores):

| Campo | Descripción |
|---|---|
| `user` | FK a UserProfile (CASCADE). |
| `confidence_score` | Score crudo de `decision_function`. |
| `is_legitimate` | Decisión binaria. |
| `status_code` | `LEGITIMATE` / `ANOMALY` / `ERROR`. |
| `latency_ms` | Latencia de la inferencia. |
| `detail` | Detalle del error (si aplica). |
| `created_at` | Timestamp indexado. |

Índices: `(user, -created_at)` y `status_code` para consultas de auditoría rápidas.

### 9.4. Comandos de gestión

| Comando | Qué hace |
|---|---|
| `python manage.py train_from_csv` | Importa el CSV CMU, entrena 1 modelo por sujeto con **split por sesión** (train 1-6, eval 7-8) y reporta FAR/FRR/ACC. |
| `python manage.py evaluate_models` | Compara datos vistos (train) vs no vistos (test), calcula FAR/FRR/accuracy/**EER/AUC-ROC** y diagnostica overfitting. |

El **split por sesión** es clave: se entrena con sesiones 1-6 y se evalúa con sesiones 7-8 (que el
modelo nunca vio) más impostores de otros sujetos. Sin este split los números serían engañosos
(puntuar sobre los mismos datos de entrenamiento siempre sale bien).

---

## 10. Métricas de evaluación (FAR, FRR, EER, AUC)

Con un umbral `t` (se acepta si `score >= t`):

| Métrica | Definición | Significado |
|---|---|---|
| **FAR** | Fracción de **impostores aceptados** (`impostor_score >= t`). | Falsa aceptación (seguridad). |
| **FRR** | Fracción de **legítimos rechazados** (`genuine_score < t`). | Falso rechazo (usabilidad). |
| **Accuracy** | `(legítimos aceptados + impostores rechazados) / total`. | Exactitud global. |
| **EER** | Umbral donde **FAR == FRR**. | Compromiso único FAR/FRR; más bajo = mejor. |
| **AUC-ROC** | Prob. de que un genuino puntúe más alto que un impostor. | Poder de separación (independiente del umbral). |

**Resultados de referencia** (split por sesión, 51 sujetos). Por defecto el umbral es el óptimo
calibrado `+0.021328`; `0.0` se conserva como línea base:

| Umbral | FAR | FRR | Accuracy |
|---|---|---|---|
| 0.0 (línea base) | ≈ 27.8 % | ≈ 6.0 % | ≈ 72.6 % |
| **+0.021328 (por defecto, óptimo)** | ≈ 16.3 % | ≈ 11.1 % | ≈ 83.8 % |

El EER (~12.19 %) es invariante al umbral. El umbral es configurable (`ML_DECISION_THRESHOLD`)
para ajustar la política de riesgo. La calibración fina se obtiene con
`python manage.py evaluate_models` o `python manage.py benchmark_report`.

---

## 11. Despliegue y ejecución

### 11.1. Desarrollo local

Requisitos: Node 18+, Java 17 + Maven, Python 3.12.

```bash
# 1) Microservicio ML
cd Modelo_predictivo_contrasenas
pip install -r requirements.txt
python manage.py migrate
python manage.py train_from_csv        # genera los modelos del dataset
python manage.py runserver 8000

# 2) Backend
cd Backend
mvn spring-boot:run                    # escucha en :8080

# 3) Frontend
cd Front
npm install
npm run dev                            # Vite (proxy a /api por defecto)
```

### 11.2. Docker

Cada componente trae su `Dockerfile`:

- **Modelo**: `python:3.12-slim` + gunicorn. El `docker-entrypoint.sh` migra, *siembra* solo los
  modelos del dataset que falten y arranca el servidor.
- **Backend**: build multi-stage (Maven -> JRE 17).

### 11.3. Despliegue en la nube

- **Backend**: `DatabaseConfig` construye el `DataSource` desde `DATABASE_URL` (formato Supabase,
  `postgresql://...`), con SSL y esquema opcional (`DB_SCHEMA`). Sin `DATABASE_URL`, usa H2 en
  memoria para desarrollo.
- **Modelo**: `settings.py` usa SQLite por defecto y PostgreSQL si existe `DATABASE_URL`
  (`dj-database-url`). Soporta `ALLOWED_HOSTS` para Render/Fly.

> **Nota**: el filesystem del contenedor es efímero. Por eso los modelos **propios** de usuario
> (`user-*`) y los de cursor se guardan en `ML_USER_MODELS_DIR`, que en despliegue apunta a un
> **volumen persistente** (Disco de Render montado en `/data/user_models`). Los modelos del
> **dataset** (`sXXX`) permanecen en la imagen, ya que son inmutables. Ver §5.7.

---

## 12. Variables de entorno

### Backend

| Variable | Por defecto | Descripción |
|---|---|---|
| `PORT` | `8080` | Puerto HTTP. |
| `DATABASE_URL` | — | PostgreSQL (`postgresql://...`). Si falta, H2 en memoria. |
| `DB_SCHEMA` | — | Esquema dedicado (una BD, varios esquemas). |
| `APP_JWT_SECRET` | (dev) | Secreto del JWT. **Obligatorio en producción.** |
| `APP_JWT_EXPIRATION_MS` | `86400000` | Vida del token (24 h). |
| `ML_BASE_URL` | `http://127.0.0.1:8000` | URL del microservicio ML. |
| `ML_PREDICT_PATH` / `ML_RETRAIN_PATH` | `/api/predict/` / `/api/retrain/` | Rutas del modelo. |
| `ML_READ_TIMEOUT_MS` | `10000` | Timeout de lectura hacia el modelo. |
| `CORS_ALLOWED_ORIGINS` | `*` | Orígenes permitidos (coma-separados). |

### Microservicio ML

| Variable | Por defecto | Descripción |
|---|---|---|
| `DJANGO_SECRET_KEY` | (dev) | Secreto de Django. **Obligatorio en producción**: con `DEBUG=False` el arranque falla si falta. |
| `DJANGO_DEBUG` | `True` | Modo debug. |
| `ALLOWED_HOSTS` | `localhost,...` | Hosts permitidos. |
| `DATABASE_URL` | — | PostgreSQL; si falta, SQLite. |
| `ML_MODELS_DIR` | `ml_models/` | Directorio de los `.joblib` del dataset (inmutable, en la imagen). |
| `ML_USER_MODELS_DIR` | = `ML_MODELS_DIR` | Directorio de los modelos de usuario (`user-*`) y de cursor. En producción apunta al volumen persistente (`/data/user_models`). |
| `DATASET_PATH` | `data/DSL-StrongPasswordData.csv` | Dataset CMU. |
| `ML_DECISION_THRESHOLD` | `0.021328` | Umbral de decisión LEGITIMATE/ANOMALY (óptimo calibrado; `0.0` = línea base). |

### Frontend

| Variable | Por defecto | Descripción |
|---|---|---|
| `VITE_API_URL` | `/api` | URL base del backend. |

---

## 13. Estructura del repositorio

```
.
├── Front/                              # React + Vite
│   └── src/
│       ├── api/client.js               # Cliente HTTP al backend
│       ├── services/keystroke.js       # Captura + cálculo de las 31 features
│       └── components/                 # AuthScreen, KeystrokeTester, TrainingScreen
│
├── Backend/                            # Spring Boot (Java 17)
│   ├── Dockerfile
│   └── src/main/java/com/autentication/
│       ├── controller/                 # AuthController, KeystrokeController, TrainingController
│       ├── service/                    # Interfaces + impl (verificación, entrenamiento)
│       ├── client/                     # WebClientKeystrokeModelClient (hacia el modelo Python)
│       ├── security/                   # JWT, filtro y UserDetails
│       ├── domain/                     # Entidad User
│       ├── dto/                        # Request/Response records
│       ├── config/                     # Security, Web, Database
│       └── exception/                  # Manejo global de errores
│
└── Modelo_predictivo_contrasenas/      # Django + scikit-learn
    ├── authentication_api/
    │   ├── ml_service.py               # Núcleo ML (features, train, predict, evaluate)
    │   ├── views.py                    # /api/retrain/, /api/predict/
    │   ├── models.py                   # UserProfile, AuthInferenceLog
    │   └── management/commands/        # train_from_csv, evaluate_models
    ├── continuous_auth/               # settings, urls, wsgi/asgi
    ├── ml_models/                      # iforest_*.joblib (un modelo por usuario)
    ├── data/DSL-StrongPasswordData.csv # Dataset CMU
    └── Dockerfile / docker-entrypoint.sh / build.sh / render.yaml
```

---

## 14. Estado actual y limitaciones conocidas

**Operativo:**

- Captura de tecleo en el navegador y cálculo de las 31 features.
- Registro/login con JWT y contraseñas BCrypt.
- Verificación y entrenamiento de modelos propios por usuario.
- Microservicio ML con entrenamiento por usuario, inferencia y auditoría completa.
- Importación del dataset CMU (51 modelos) y evaluación FAR/FRR/EER/AUC.
- **Módulo de dinámica del cursor** (12 features, modelo por usuario, endpoints y UI) — §15.
- **Benchmark EER** reproducible con endpoint `/api/metrics/*` y pestaña "Rendimiento" — §16.
- **Pruebas automatizadas** de ML, métricas y cursor — §17.
- Contenerización de los tres componentes y despliegue en Render — §18.

**Limitaciones y trabajo pendiente:**

1. ~~Calibración formal del umbral (curva FAR vs FRR / EER) y fijarlo en producción.~~
   **Resuelto**: umbral óptimo `+0.021328` fijado por defecto; `0.0` conservado como línea base
   (§10).
2. **Endurecer la verificación frente a impostores "promedio"**. IsolationForest es permisivo con
   patrones raros pero globalmente normales (§5.6). Evaluar un enfoque híbrido: detector de
   anomalías + clasificador supervisado entrenado con muestras de otros sujetos como
   pseudo-impostores. Es una decisión de producto, no solo técnica.
3. ~~Persistencia de modelos en producción más allá del filesystem del contenedor (volumen
   persistente u objeto externo), ya que puede ser efímero.~~
   **Resuelto (volumen persistente)**: modelos de usuario y de cursor en `ML_USER_MODELS_DIR`
   (Disco de Render en `/data/user_models`); modelos del dataset en la imagen. Ver §5.7. Para
   escalar a varias réplicas haría falta almacenamiento de objetos (fase futura).
4. ~~Secretos por variable de entorno (`APP_JWT_SECRET`, `DJANGO_SECRET_KEY`) en despliegue.~~
   **Resuelto (Django)**: con `DEBUG=False` el arranque falla si falta `DJANGO_SECRET_KEY`.
   El backend (`APP_JWT_SECRET`) debe configurarse explícitamente en producción, pero todavía
   tiene un valor por defecto de desarrollo en `application.yml` (endurecer pendiente).
5. ~~Pruebas automatizadas de los endpoints y del servicio ML.~~
   **Resuelto parcialmente**: 35 pruebas Python + 4 en Java cubren servicio ML, métricas, cursor,
   persistencia y endpoints. Queda ampliar cobertura de casos límite.
6. **Contraseña fija**: el sistema usa la contraseña del dataset (`.tie5Roanl`) porque las features
   CMU se definieron sobre esa secuencia. Usar una contraseña arbitraria requeriría recalcular el
   esquema de features (ver `docs/DISENO_CONTRASENA_ARBITRARIA.md`).
7. **Fusión tecleo + cursor**: hoy son modelos separados; combinar sus scores en una sola decisión
   es una decisión de producto (trabajo futuro, §15.6).
8. **Validación con tareas reales**: no se han ejecutado estudios con actividades reales de oficina
   ni pruebas de usabilidad; el protocolo propuesto está en `docs/PERSPECTIVAS_ETICAS_SOCIALES.md`
   (§19.3.2).

---

## 15. Dinámica del cursor (mouse dynamics)

Además del tecleo, el sistema incorpora una segunda modalidad biométrica de comportamiento: la
**dinámica del cursor** (cómo se mueve y hace clic el ratón). Es independiente del modelo de tecleo
y se sirve como módulo paralelo en el mismo microservicio ML.

### 15.1. Qué mide y por qué
Cada persona mueve el ratón con un patrón motor propio: velocidad, aceleración, curvatura de la
trayectoria, pausas, presión de clic. Un impostor puede conocer la contraseña pero no reproduce el
estilo de movimiento del titular. El cursor aporta una señal **independiente** del tecleo, lo que
habilita una autenticación multimodal.

### 15.2. Las 12 features del cursor
Definidas en `authentication_api/cursor_service.py` (`CURSOR_FEATURE_COLUMNS`) y capturadas en
`Front/src/services/cursor.js`:

| Familia | Ejemplos | Qué mide |
|---|---|---|
| Velocidad | `M.speed_mean`, `M.speed_max` | Ritmo medio/máximo del puntero. |
| Aceleración | `M.accel_mean` | Cambios de velocidad (brusquedad). |
| Trayectoria | `M.curvature_mean`, `M.path_efficiency` | Curvatura y eficiencia del recorrido. |
| Pausas / tiempos | `M.pause_rate`, `M.duration_mean` | Pausas y duración de la sesión. |
| Clic | `M.click_interval_mean` | Ritmo entre clics. |
| … | (resto) | … |

Los nombres coinciden 1:1 con el modelo Python, así que no hay traducción en el borde.

### 15.3. Flujo de uso
Pantalla **"Dinámica del cursor"** (`CursorScreen.jsx`): el usuario mueve el cursor en una zona
designada y hace clics; la pantalla muestra el número de puntos capturados y, cuando reúne sesiones
suficientes, permite **entrenar** y **verificar** la sesión actual.

### 15.4. Modelo y entrenamiento
Mismo enfoque que el tecleo: `IsolationForest` por usuario (`iforest_cursor_<user_id>.joblib`),
`decision_function` + umbral (`ML_CURSOR_DECISION_THRESHOLD`, por defecto hereda el de tecleo).
Soporta dos modos de entrenamiento:
- **Datos reales**: `{ user_id, records:[...] }`.
- **Datos sintéticos** (para demo antes de capturar): `{ user_id, synthetic:true, n:30 }`, generados
  de forma **reproducible** por usuario.

### 15.5. Endpoints del cursor

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/cursor/retrain/` | Entrena el modelo de cursor (real o sintético). |
| POST | `/api/cursor/predict/` | Infiere y devuelve score + decisión. |
| GET  | `/api/cursor/synthetic/` | Devuelve un dataset sintético reproducible (fixture/inspección). |

### 15.6. Combinación tecleo + cursor
Hoy son **modelos separados** con scores independientes. La **fusión** (p. ej. combinar scores por
media ponderada o una regla AND/OR según el riesgo) es una decisión de producto documentada como
trabajo futuro. La arquitectura ya lo permite: ambos modelos viven en el mismo servicio ML y
comparten el patrón de features→modelo→score→umbral.

---

## 16. Medición de exactitud: benchmark EER

Para responder a la exigencia de **demostrar el EER** de forma comprobable, el sistema incluye un
benchmark reproducible.

### 16.1. Cómo se calcula
- Split **por sesión**: se entrena con sesiones 1-6 y se evalúa con sesiones 7-8 (no vistas) más
  impostores de otros sujetos.
- Se barren umbrales reales y se calculan **FAR**, **FRR**, **EER** y **AUC** por sujeto y agregados.
- Se persiste el resultado en `docs/benchmark_eer.json` (versionado) mediante
  `python manage.py benchmark_report`.

### 16.2. Endpoints de métricas

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/metrics/summary/` | EER/FAR/FRR/AUC agregados y umbrales (referencia y óptimo). |
| GET | `/api/metrics/curve/` | Puntos de la curva FAR/FRR en los umbrales de interés. |

La pestaña **"Rendimiento"** del front (`MetricsDashboard.jsx`) consume estos endpoints y muestra
EER, FAR/FRR, umbral y curva.

### 16.3. Resultados de referencia
Ver §10: EER ≈ 12.19 %, con FAR/FRR según umbral (16.3 %/11.1 % en el óptimo; 27.8 %/6.0 % en la
línea base 0.0). El reporte completo está en `docs/REPORTE_EER.md` y `docs/benchmark_eer.json`.

---

## 17. Pruebas automatizadas

Para dar respaldo de estabilidad y robustez (antes señalado como carencia):

### 17.1. Microservicio ML (Python)
`authentication_api/tests.py` cubre:
- **Servicio ML**: `record_to_vector`, validación de NaN/inf, mínimo de muestras, `train_model`,
  `load_model`, `predict`, `evaluate_model` (FAR/FRR/accuracy).
- **Endpoints**: `/api/retrain/` y `/api/predict/` (casos válidos e inválidos; auditoría).
- **Cursor**: entrenamiento real y sintético, predicción, dataset sintético reproducible.
- **Métricas**: carga del benchmark, resumen y curva.

### 17.2. Backend (Java)
`Backend/src/test/` incluye pruebas de los flujos de autenticación y verificación/orquestación.

### 17.3. Cómo ejecutarlas
```bash
# Python
cd Modelo_predictivo_contrasenas
python manage.py test

# Java
cd Backend
mvn test
```
La suite usa `continuous_auth/test_settings.py` (base de datos de prueba, sin tocar datos reales).

---

## 18. Despliegue en Render (guía y correcciones)

El sistema se despliega en **Render** como 3 Web Services + 1 PostgreSQL. La guía completa, el
registro de **problemas encontrados y sus correcciones**, y la tabla de variables están en
[`Modelo_predictivo_contrasenas/docs/DESPLIEGUE_RENDER.md`](Modelo_predictivo_contrasenas/docs/DESPLIEGUE_RENDER.md).

Resumen de variables manuales (las únicas 2 que se escriben a mano):

| Servicio | Key | Valor |
|---|---|---|
| backend | `ML_BASE_URL` | `https://continuous-auth-ml.onrender.com` (sin `/api`, con `https://`) |
| front | `VITE_API_URL` | `https://continuous-auth-backend.onrender.com/api` (con `/api`) |

**Correcciones destacadas del despliegue** (detalle en el doc):
1. `render.yaml` de `runtime: python` → **`runtime: docker`** (para ejecutar el entrypoint que migra/siembra).
2. `ML_BASE_URL`/`VITE_API_URL` como **`sync: false`** (Render entrega `host:port` sin esquema y rompería el cliente Java y el front).
3. **`VITE_API_URL` requiere rebuild** del front (Vite la incrusta en build).
4. Error «El usuario s002 no existe»: **no era falta de `.joblib`**, sino falta de `UserProfile` en la BD nueva → se resuelve entrenando el **modelo propio** por usuario.
5. `.dockerignore` ahora excluye **`.venv/`** (imagen mucho más ligera).
6. `.gitignore` corregido con **`**/ml_models/cursor_iforest_*.joblib`** (antes solo cubría la raíz).
7. En plan free los modelos de usuario **no persisten** (sin Disco): se regeneran al **re-entrenar**.

---

## 19. Perspectivas éticas, sociales y humanas

El detalle está en [`Modelo_predictivo_contrasenas/docs/PERSPECTIVAS_ETICAS_SOCIALES.md`](Modelo_predictivo_contrasenas/docs/PERSPECTIVAS_ETICAS_SOCIALES.md).
Síntesis:

- **Ética**: consentimiento informado (pendiente de pantalla explícita), minimización (solo features,
  no contenido), retención y derecho de supresión (cascade), transparencia (score/decisión
  visibles), **equidad** (riesgo de sesgo por teclado/idioma/condición motora), gobernanza de datos.
- **Social**: adopción organizacional (protege la sesión, no solo el login), dinámicas de equipos que
  comparten estación, efectos colectivos (reducción de fraude vs riesgo de exclusión).
- **Cultural**: la contraseña fija del dataset es anglocéntrica; se documenta la necesidad de
  layouts/idiomas diversos como limitación.
- **Humana**: el sistema **sugiere**, no bloquea irreversiblemente; el usuario puede **re-entrenar**;
  decisión humana en el bucle.
- **Impacto** (Rel5) y **transferibilidad interdisciplinar** (Uni5): estimaciones cualitativas
  declaradas y glosario interpretable por disciplinas no técnicas.

La evaluación por criterios (los 10 ingredientes) con la evidencia y las correcciones de cada uno
está en [`Modelo_predictivo_contrasenas/docs/EVALUACION_Y_CORRECCIONES.md`](Modelo_predictivo_contrasenas/docs/EVALUACION_Y_CORRECCIONES.md).

---

## 20. Referencias

- Killourhy, K. S., & Maxion, R. A. (2009). *Comparing Anomaly-Detection Algorithms for Keystroke
  Dynamics*. IEEE/IFIP DSN, 125–134. — Dataset **CMU DSL-StrongPasswordData**.
- Monrose, F., & Rubin, A. D. (2000). *Keystroke Dynamics as a Biometric for Authentication*.
  Future Generation Computer Systems, 16(4), 351–359.
- Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). *Isolation Forest*. IEEE ICDM, 413–422.
- Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2012). *Isolation-Based Anomaly Detection*. ACM TKDD, 6(1).
- Chandola, V., Banerjee, A., & Kumar, V. (2009). *Anomaly Detection: A Survey*. ACM Computing
  Surveys, 41(3), 1–58.
- Bolle, R. M., et al. (2013). *Guide to Biometrics*. Springer. — FAR/FRR/EER.
- Fawcett, T. (2006). *An Introduction to ROC Analysis*. Pattern Recognition Letters, 27(8), 861–874.
- Pedregosa, F., et al. (2011). *Scikit-learn: Machine Learning in Python*. JMLR, 12, 2825–2830.

---

## Glosario

- **Keystroke dynamics**: biometría basada en el ritmo de escritura.
- **Hold time (H)**: tiempo que una tecla permanece pulsada.
- **DD / UD**: latencias entre pulsar dos teclas (down-down / up-down).
- **Feature**: cada una de las 31 métricas temporales que describen una muestra de tecleo.
- **IsolationForest**: algoritmo de detección de anomalías de una clase basado en aislar puntos.
- **decision_function**: score continuo; negativo = anomalía, no negativo = normal.
- **FAR / FRR / EER / AUC**: métricas de evaluación de un sistema biométrico.
- **Modelo activo**: el modelo usado al verificar; propio del usuario o del dataset.
- **Mouse dynamics**: biometría basada en cómo se mueve el cursor (velocidad, aceleración, curvatura, clics).
- **M.* features**: las 12 métricas temporales del cursor.
- **Multimodal**: uso conjunto de dos o más señales biométricas (aquí, tecleo + cursor).
- **Benchmark**: medición reproducible de FAR/FRR/EER/AUC sobre un split por sesión.
