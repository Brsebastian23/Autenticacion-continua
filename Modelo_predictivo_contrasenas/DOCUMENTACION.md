# Documentación del Sistema de Autenticación Continua por Dinámica de Teclado

**Proyecto:** Autenticación Continua (Keystroke Dynamics)
**Módulo documentado:** Microservicio de Machine Learning (Django + DRF + scikit-learn)
**Dataset:** CMU DSL-StrongPasswordData (`DSL-StrongPasswordData.csv`)
**Repositorio (estructura actual):**

```
/
├── Backend/                       Backend de autenticación (Spring Boot, Java)
├── Front/                         Frontend de la aplicación
└── Modelo_predictivo_contrasenas/ Microservicio de ML (Django/Python) ← documento
```

---

## 1. Resumen ejecutivo

El sistema implementa **autenticación continua basada en la dinámica de tecleo (keystroke
dynamics)**: no solo se valida *qué* contraseña se escribe, sino *cómo* se escribe. A partir
de las 31 métricas temporales del dataset CMU DSL-StrongPasswordData, el sistema entrena un
modelo **IsolationForest** por usuario (un modelo de una clase por identidad) y expone una API
HTTP REST que el backend de autenticación consume para:

1. **Entrenar (`/api/retrain/`)** el perfil biométrico de un usuario con un conjunto de muestras.
2. **Inferir (`/api/predict/`)** si un intento de escritura corresponde al usuario legítimo o a un
   impostor, registrando **toda** inferencia en una tabla de auditoría.

El análisis funcional, la definición de requisitos y el diseño de la arquitectura se realizaron
utilizando **NotebookLM**, herramienta empleada como asistente de investigación y síntesis sobre
la documentación del dataset CMU, la literatura de keystroke dynamics y los requisitos del
proyecto.

---

## 2. Fase de análisis y arquitectura — NotebookLM

### 2.1. Uso de NotebookLM

Todo el **análisis de dominio**, la **definición de requisitos** y la **arquitectura inicial**
se realizaron con **NotebookLM**. Las fuentes cargadas en el cuaderno fueron:

- Documentación y *paper* del dataset **CMU DSL-StrongPasswordData** (Killourhy & Maxion).
- Documentación oficial de **scikit-learn** (`IsolationForest`, `decision_function`).
- Documentación de **Django REST Framework** y **dj-database-url**.
- Notas del equipo y requisitos del proyecto.

### 2.2. Resultados del análisis obtenidos con NotebookLM

| Pregunta de análisis | Conclusión documentada |
|---|---|
| ¿Qué features contiene el dataset? | 31 features: 11 de *hold time* (`H.*`), 10 de *down-down* (`DD.*`) y 10 de *up-down* (`UD.*`) de la secuencia `.tie5Roanl` + `Return`. |
| ¿Qué tipo de problema es? | Autenticación **de una sola clase**: solo se dispone de muestras del usuario legítimo → se descarta un clasificador supervisado binario clásico. |
| ¿Qué algoritmo usar? | **IsolationForest**: aprendida de patrones de escritura legítima y detecta desviaciones sin necesitar muestras de impostores en el entrenamiento. |
| ¿Cómo se persiste el modelo? | Un modelo por usuario, serializado con **joblib** en disco. |
| ¿Cómo se integra con el resto del sistema? | Microservicio HTTP REST (Django + DRF) consumido por el backend Spring Boot, en arquitectura de microservicios. |
| ¿Cómo evitar fuga de información? | **Split por sesión**: entrenar en sesiones 1–6 y evaluar en sesiones 7–8 (no vistas). |

### 2.3. Decisiones de arquitectura derivadas

1. **Arquitectura de microservicios.** El backend de autenticación (Spring Boot) delega la
   inteligencia biométrica a un servicio independiente (`Modelo_predictivo_contrasenas`),
   permitiendo desplegar, escalar y versionar el modelo por separado.
2. **API sin estado en la petición.** Cada llamada es autónoma: `user_id` + métricas en el cuerpo
   JSON. El estado (modelos, auditoría) vive en disco y base de datos.
3. **Contrato JSON explícito.** Los features se intercambian por nombre de columna CMU
   (`H.period`, `DD.t.i`, ...), desacoplando el cliente del orden interno del vector.
4. **Base de datos dual.** SQLite en desarrollo local, PostgreSQL en despliegue, seleccionada
   dinámicamente por `DATABASE_URL`.
5. **Auditoría obligatoria.** Toda inferencia, incluso los errores, queda registrada.

---

## 3. Fase de requisitos

### 3.1. Requisitos funcionales

| ID | Requisito |
|---|---|
| RF-01 | Entrenar un modelo por usuario a partir de 31 métricas temporales. |
| RF-02 | Exponer el entrenamiento vía `POST /api/retrain/`. |
| RF-03 | Exponer la verificación vía `POST /api/predict/`. |
| RF-04 | Persistir los modelos entrenados en disco por usuario. |
| RF-05 | Registrar cada inferencia (score, decisión, estado, latencia, timestamp). |
| RF-06 | Importar el dataset CMU completo mediante un comando de gestión. |
| RF-07 | Evaluar los modelos con métricas FRR/FAR/EER/AUC. |

### 3.2. Requisitos no funcionales

| ID | Requisito |
|---|---|
| RNF-01 | Validación estricta de entrada (31 features, numéricos, sin NaN/∞). |
| RNF-02 | Respuestas JSON con códigos HTTP semánticos (200/201/400/404/422/500). |
| RNF-03 | Escritura atómica de los modelos (fichero temporal + `os.replace`). |
| RNF-04 | Despliegue portable: SQLite local / PostgreSQL en producción. |
| RNF-05 | Contenerización (Docker) para despliegue reproducible. |

---

## 4. Fase de diseño técnico

### 4.1. Arquitectura general

```
┌─────────────┐      HTTP/JSON      ┌──────────────────────┐   JWT/HTTP   ┌────────────────────────────┐
│  Frontend   │ ──────────────────► │  Backend Spring Boot  │ ───────────► │  Microservicio ML (Django) │
│  (captura   │                     │  (auth, usuarios,     │              │  /api/retrain/             │
│  tecleo)    │                     │  JWT, orquestación)   │              │  /api/predict/             │
└─────────────┘                     └──────────────────────┘              └───────────┬────────────────┘
                                                                                      │
                                                  ┌───────────────────────────────────┼──────────────────────┐
                                                  ▼                                   ▼                      ▼
                                          ┌──────────────┐                  ┌─────────────────┐   ┌────────────────┐
                                          │ ml_service   │                  │ ml_models/*.joblib│  │ DB (SQLite/    │
                                          │ (Isolation   │ ───────────────► │  modelo por user │  │  PostgreSQL)   │
                                          │  Forest)     │                  └─────────────────┘   │ Auditoría       │
                                          └──────────────┘                                         └────────────────┘
                                          
```

### 4.2. Diseño del pipeline de ML

```
CSV CMU ----► parseo + validación (31 features)
   │
   ├─► [Entrenamiento]  split por sesión (1–6 train) ─► IsolationForest.fit ─► joblib.dump
   │
   ├─► [Inferencia]     record JSON ─► vector[1,31] ─► decision_function
   │                                                    │
   │                                                    └─► score >= umbral ? LEGITIMATE : ANOMALY
   │
   └─► [Evaluación]     train(1–6) vs test(7–8) + impostores ─► FAR / FRR / EER / AUC
```

### 4.3. Modelo de datos

**`UserProfile`** — perfil biométrico por usuario.

| Campo | Tipo | Descripción |
|---|---|---|
| `user_id` | CharField(64), PK | Identificador del usuario (p. ej. `s002`). |
| `created_at` | DateTime | Fecha de creación. |
| `updated_at` | DateTime (auto) | Última modificación. |
| `model_trained_at` | DateTime, nullable | Último entrenamiento. |
| `training_samples` | PositiveInteger | Nº de muestras del último entrenamiento. |

**`AuthInferenceLog`** — auditoría de inferencias (FK → `UserProfile`, `on_delete=CASCADE`).

| Campo | Tipo | Descripción |
|---|---|---|
| `user` | FK → UserProfile | Usuario evaluado. |
| `confidence_score` | Float | Score crudo de `decision_function`. |
| `is_legitimate` | Boolean | Decisión final. |
| `status_code` | CharField (choices) | `LEGITIMATE` / `ANOMALY` / `ERROR`. |
| `latency_ms` | Float | Latencia de la inferencia. |
| `detail` | Text | Detalle (p. ej. mensaje de error). |
| `created_at` | DateTime (indexado) | Timestamp de la inferencia. |

Índices: `(user, -created_at)` y `status_code`.

### 4.4. Contrato de la API

**`POST /api/retrain/`**

```json
{
  "user_id": "s002",
  "records": [
    { "H.period": 0.1491, "DD.period.t": 0.3979, "UD.period.t": 0.2488, "...": "las 31 features CMU" }
  ]
}
```

Respuesta `201 Created`:

```json
{
  "status": "trained",
  "user_id": "s002",
  "samples": 2400,
  "model_file": "iforest_s002.joblib",
  "features": 31,
  "training_latency_ms": 1180.4,
  "trained_at": "2026-10-23T01:51:31+00:00"
}
```

**`POST /api/predict/`**

```json
{
  "user_id": "s002",
  "record": { "H.period": 0.1491, "DD.period.t": 0.3979, "UD.period.t": 0.2488, "...": "..." }
}
```

Respuesta `200 OK`:

```json
{
  "user_id": "s002",
  "is_legitimate": true,
  "confidence_score": 0.058321,
  "status_code": "LEGITIMATE",
  "latency_ms": 12.4,
  "log_id": 42,
  "timestamp": "2026-10-23T01:52:10+00:00"
}
```

**Códigos de error:** `400` (payload inválido), `404` (usuario sin modelo), `422` (datos no
procesables: features faltantes, no numéricos, NaN/∞, < 3 muestras), `500` (fallo interno; se
registra igualmente en la auditoría como `ERROR`).

### 4.5. Hiperparámetros del modelo

```python
IFOREST_PARAMS = {
    'n_estimators': 200,      # 200 árboles: estabilidad sin coste excesivo
    'max_samples': 'auto',    # min(256, n_muestras)
    'contamination': 0.1,     # 10% de muestras atípicas asumidas
    'random_state': 42,       # reproducibilidad
    'n_jobs': -1,             # paralelización
}
MIN_TRAINING_SAMPLES = 3
```

Criterio de decisión: `decision_function(x) >= ML_DECISION_THRESHOLD` ⇒ legítimo.

### 4.6. Justificación del algoritmo: por qué IsolationForest

#### 4.6.1. El problema, en una frase

Tenemos que responder: *"¿este patrón de tecleo pertenece al usuario X o a un impostor?"* — pero
en el entrenamiento **solo tenemos muestras del usuario X**. No tenemos, en producción, muestras
etiquetadas de impostores para cada usuario nuevo.

Esa restricción es la que manda. Y define qué familia de algoritmos podemos usar.

#### 4.6.2. Por qué NO usamos un clasificador clásico supervisado

La tentación natural es entrenar un `LogisticRegression`, un `RandomForestClassifier` o una red
neuronal con etiquetas `legítimo / impostor`. El problema:

- **No tenemos la clase "impostor" para cada usuario real.** Cuando un usuario nuevo se registra,
  solo escribe su contraseña unas cuantas veces. No existe un conjunto de "intentos de otras
  personas contra este usuario".
- Si fabricáramos impostores artificiales (con otros usuarios del dataset), el modelo aprendería
  a distinguir *esos* impostores concretos, no la identidad de X. Al llegar un impostor real y
  desconocido, el rendimiento se derrumbaría.
- Es un problema de **verificación biométrica de una sola clase**: el espacio de "no-X" es
  infinitamente grande y no se puede muestrear.

Por eso descartamos el aprendizaje supervisado binario. Necesitamos **detección de anomalías**:
aprender la *forma* de la escritura legítima y marcar como sospechoso lo que se aleja de ella.

#### 4.6.3. Por qué IsolationForest y no otro detector de anomalías

Comparamos las alternativas reales antes de decidir:

| Algoritmo | Por qué no (en nuestro caso) |
|---|---|
| **One-Class SVM** | Necesita ajustar kernel y sensibilidad (ν); es O(n²)–O(n³), lento con muchos datos; muy sensible a la escala → obliga a normalizar cuidadosamente. |
| **LOF (Local Outlier Factor)** | Es *transductivo* por naturaleza: puntúa contra el conjunto de entrenamiento, no tiene un `predict` limpio sobre nuevas muestras sin trucos. Además asume densidades locales, sensible a la elección de `n_neighbors`. |
| **Autoencoder** | Requiere red neuronal, más infraestructura, más hiperparámetros, entrenamiento más lento y menos interpretable. Excesivo para 31 features tabulares. |
| **Gaussian / Elliptic Envelope** | Asume una distribución (gaussiana) y forma elíptica del clúster legítimo. La dinámica de tecleo **no** sigue una gaussiana multivariada, y las features están correlacionadas de forma no lineal. |
| **IsolationForest** ✅ | Escala bien, no asume distribución, no necesita normalización, tiene `predict`/`decision_function` estable sobre muestras nuevas, y es robusto en alta dimensión relativa. |

#### 4.6.4. Qué hace IsolationForest por dentro (el porqué de su fuerza)

La intuición es elegante y es justo lo que necesitamos.

**Construcción:** se crean 200 árboles. En cada árbol, cada punto se "aísla" cortando el espacio
aleatoriamente: eliges una feature al azar, eliges un valor de corte al azar dentro de su rango, y
divides. Repites hasta aislar el punto.

**La clave:** *las anomalías se aíslan con pocos cortes*. Un punto anómalo está lejos del grueso
de los datos, así que cae solo tras 3–4 divisiones. Un punto normal, rodeado de vecinos parecidos,
necesita muchos cortes para quedar aislado.

**El score = profundidad media del camino.** Path corto → anómalo. Path largo → normal. Eso es
exactamente lo que devuelve `decision_function`:

- `score < 0` → anomalía (impostor)
- `score >= 0` → normal (legítimo)

Y nosotros lo comparamos contra `ML_DECISION_THRESHOLD`.

**Por qué eso encaja con keystroke dynamics:**

- Un **usuario legítimo** teclea con un "ritmo" consistente: sus tiempos de hold y de vuelo caen
  siempre en la misma región del espacio de 31 dimensiones → caminos largos → score alto.
- Un **impostor** teclea diferente: sus tiempos se salen de esa región → se aísla rápido → score
  bajo.

No necesitábamos modelar la distribución exacta del usuario; solo necesitábamos detectar cuándo un
punto **está lejos de la nube legítima**. IsolationForest es literalmente un detector de "qué tan
lejos y aislado está este punto".

#### 4.6.5. Por qué encaja con nuestra arquitectura y nuestros datos

1. **Un modelo por usuario, entrenado con pocas muestras.** Cada usuario tiene ~6 sesiones × 50
   repeticiones ≈ 300 muestras (2400 registros si se usan todas las sesiones). IsolationForest
   funciona bien con esas cantidades; los autoencoders o SVMs con kernel necesitan más datos y más
   ajuste.
2. **Sin normalización obligatoria.** Las features CMU (`H.*` en el orden de 0.1 s, `DD.*` en el
   orden de 0.2–0.4 s) vienen ya en la misma unidad (segundos). IsolationForest es invariante a la
   escala y a los ejes, así que evitamos introducir un paso frágil de preprocesado. Con One-Class
   SVM esto habría sido obligatorio y una fuente de errores.
3. **Detección pura en inferencia, barata de ejecutar.** `predict` sobre un único vector es
   O(log n) por árbol → decenas de árboles → latencia de ~10–20 ms (verificado en nuestros logs).
   Cabe en el flujo de autenticación sin penalizar la experiencia.
4. **Reproducible y versionable.** `random_state=42` + `joblib` → mismo modelo en cada deploy.
   Cada usuario tiene su `.joblib` independiente, que se puede versionar y auditar por separado.
5. **Contamination como palanca interpretable.** `contamination=0.1` declara "espero ~10 % de
   muestras atípicas en el propio entrenamiento". Es un parámetro con significado de negocio, no
   una caja negra.

#### 4.6.6. Los hiperparámetros, y por qué esos valores

- **200 árboles** (`n_estimators`): el score es una media de caminos; con menos hay varianza alta,
  con más el coste crece sin ganancia proporcional.
- **`max_samples='auto'`**: IsolationForest, por diseño, *funciona mejor con submuestras* que con
  todos los datos. No por ahorro, sino porque el muestreo aleatorio mejora la separación.
- **`contamination=0.1`**: define dónde corta internamente para que el `-1` (anomalía) capture al
  ~10 % más raro. Es el parámetro que más influye en el comportamiento final, junto con nuestro
  umbral.

#### 4.6.7. La debilidad que reconocemos

IsolationForest tiene **una** debilidad estructural, y es importante ser honestos:

**No modela qué significa "ser el usuario X", solo "no parecerse a nadie" en el conjunto de
entrenamiento.** Si un impostor teclea de forma *rara pero globalmente normal* —por ejemplo, un
usuario promedio cualquiera—, su score puede quedar cerca de cero y pasar el umbral.

Es precisamente lo que observamos en las métricas: **FAR ≈ 27 %**. Ahí está el coste de la
ventaja. Un detector de anomalías de una clase es conservador con los raros y permisivo con los
"normales". El trade-off lo gestionamos con el umbral: bajarlo protege contra el impostor promedio
pero rechaza a usuarios legítimos (sube FRR).

Y por eso el paso natural siguiente, si quisiéramos endurecer la verificación, sería **combinar**
IsolationForest con un clasificador supervisado entrenado a partir de las muestras de otros sujetos
como pseudo-impostores —pero eso es una decisión de producto que hoy no está tomada (ver §9).

#### 4.6.8. Cómo lo validamos (y por qué esto importa)

No calibramos "a ojo". Definimos un **split por sesión**:

- **Entrenar** con sesiones 1–6.
- **Evaluar** con sesiones 7–8 —que el modelo **nunca vio**— más impostores de otros sujetos.
- Métricas: **FAR, FRR, EER, AUC-ROC**, y comparación train vs test para detectar overfitting.

Ese diseño es lo que permite afirmar que el IsolationForest **generaliza**: la brecha train-test
baja indica que no memorizó. Sin este split, los números serían engañosos: puntuar sobre los mismos
datos de entrenamiento siempre sale bien.

#### 4.6.9. Resumen: por qué este algoritmo es fuerte para nuestro caso

1. **Encaja exactamente con la restricción de datos**: una clase, sin impostores etiquetados.
2. **No asume distribución**: la dinámica de tecleo no es gaussiana ni esférica.
3. **Es eficiente y de baja latencia**, apto para autenticación continua en tiempo de ejecución.
4. **No requiere normalización**, reduciendo la superficie de error.
5. **Es reproducible, interpretable en su mecánica y versionable por usuario**.
6. **Su score es directamente explotable**: `decision_function` da una medida continua, no solo una
   etiqueta → permite ajustar el umbral según la política de riesgo (FAR vs FRR).

La debilidad (permisividad ante impostores "promedio") la conocemos, la medimos y la controlamos
con el umbral — y está documentada como el punto a mejorar si el negocio exige mayor rigor.

---

## 5. Flujo de trabajo de construcción (paso a paso)

### Fase 0 — Bootstrap del proyecto

```bash
django-admin startproject continuous_auth .
python manage.py startapp authentication_api
```

Se obtuvo la estructura base Django con el proyecto `continuous_auth` y la app
`authentication_api`.

### Fase 1 — Configuración (`continuous_auth/settings.py`)

Decisiones clave:

- `INSTALLED_APPS` incluye `rest_framework` y `authentication_api`.
- **Base de datos dinámica**: SQLite por defecto; si existe `DATABASE_URL` se usa
  `dj_database_url.config(conn_max_age=600, conn_health_checks=True, ssl_require=True)`
  (compatible con Render/Supabase).
- `ALLOWED_HOSTS` configurable por entorno, con soporte para `.onrender.com` / `.fly.dev`.
- Carga de `.env` con `python-dotenv` en desarrollo (import protegido).
- Parámetros ML centralizados: `ML_MODELS_DIR`, `DATASET_PATH`, `ML_DECISION_THRESHOLD`.
- `REST_FRAMEWORK` restringido a `JSONRenderer`/`JSONParser` (API JSON pura).

### Fase 2 — Modelo de datos (`authentication_api/models.py`)

Se definieron `UserProfile` y `AuthInferenceLog` (ver §4.3) con índices para consultas de
auditoría por usuario y por estado. Migración generada y aplicada:

```bash
python manage.py makemigrations authentication_api
python manage.py migrate
```

### Fase 3 — Capa de ML (`authentication_api/ml_service.py`)

Separación de responsabilidades: las vistas no conocen scikit-learn. Funciones:

- `FEATURE_COLUMNS`: lista canónica de las 31 features (`H.*`, `DD.*`, `UD.*`).
- `record_to_vector(record)`: acepta dict (por nombre) o lista posicional; valida 31 valores,
  tipo numérico y ausencia de NaN/∞.
- `build_matrix(records)`: valida mínimo de muestras y apila vectores.
- `train_model(user_id, records)`: entrena y persiste con escritura atómica.
- `load_model(user_id)`: carga el `.joblib` o lanza `MLServiceError`.
- `predict(user_id, record)`: `decision_function` + comparación con umbral + latencia.
- `evaluate_model(...)`: FAR/FRR/accuracy sobre datos no vistos.

**Incidencia resuelta durante el desarrollo:** el primer diseño generaba nombres de columna con
doble punto (`H..t`) por concatenación `'H.' + '.t'`. Se corrigió construyendo las claves como
`prefijo + tecla`, verificando las 31 columnas contra las cabeceras reales del CSV.

### Fase 4 — Vistas (`authentication_api/views.py`)

Dos `APIView`:

- `RetrainFromDatasetView`: valida payload, entrena, hace `update_or_create` del `UserProfile`
  dentro de `transaction.atomic()`.
- `PredictAuthView`: verifica existencia del usuario, infiere y **siempre** registra en
  `AuthInferenceLog` (incluidos errores), devolviendo el contrato definido.

### Fase 5 — Enrutamiento

`authentication_api/urls.py` expone `retrain/` y `predict/`; `continuous_auth/urls.py` los
monta bajo `api/`. Resultado: `/api/retrain/` y `/api/predict/`.

### Fase 6 — Importación del dataset (comando `train_from_csv`)

Comando de gestión que:
1. Lee `settings.DATASET_PATH`.
2. Valida columnas y convertibilidad numérica.
3. Agrupa por sujeto y **sesión**.
4. Entrena con sesiones 1–6 y evalúa con 7–8 + impostores.
5. Persiste el modelo y actualiza `UserProfile`; imprime resumen FAR/FRR/accuracy.

Se generaron los **51 modelos** del dataset (`ml_models/iforest_*.joblib`).

### Fase 7 — Evaluación y detección de overfitting (`evaluate_models`)

Comando `evaluate_models` que compara datos vistos (train) vs no vistos (test) y calcula
**FAR, FRR, accuracy, EER y AUC-ROC**, con diagnóstico de brecha train-test.

### Fase 8 — Contenerización y despliegue

- `Dockerfile` (python:3.12-slim) con dependencias del sistema para scipy/scikit-learn/psycopg2.
- `docker-entrypoint.sh`: migraciones, *seed* de modelos faltantes y arranque con **gunicorn**.
- `build.sh` para plataformas tipo Render (collectstatic + migrate).

---

## 6. Módulos creados (inventario)

| Archivo | Propósito |
|---|---|
| `continuous_auth/settings.py` | Configuración: apps, DB dinámica, DRF, parámetros ML. |
| `continuous_auth/urls.py` | Montaje de `/api/`. |
| `authentication_api/models.py` | `UserProfile` y `AuthInferenceLog`. |
| `authentication_api/ml_service.py` | Núcleo de ML: features, entrenamiento, inferencia, evaluación. |
| `authentication_api/views.py` | `RetrainFromDatasetView`, `PredictAuthView`. |
| `authentication_api/urls.py` | Rutas de la app. |
| `authentication_api/admin.py` | Administración de modelos. |
| `authentication_api/migrations/0001_initial.py` | Esquema de BD. |
| `authentication_api/management/commands/train_from_csv.py` | Importación y entrenamiento desde CSV. |
| `authentication_api/management/commands/evaluate_models.py` | Evaluación FAR/FRR/EER/AUC. |
| `authentication_api/management/commands/benchmark_report.py` | Genera `docs/REPORTE_EER.md` y `docs/benchmark_eer.json` (EER persistido). |
| `authentication_api/metrics.py` | Métricas reutilizables (FAR, FRR, EER, AUC, resumen). |
| `docs/REPORTE_EER.md` | Reporte formal de exactitud con respuesta a la pregunta de investigación. |
| `docs/benchmark_eer.json` | Datos crudos del benchmark (fuente de `/api/metrics/*`). |
| `docs/DISENO_CONTRASENA_ARBITRARIA.md` | Diseño (no implementado) para contraseña arbitraria. |
| `authentication_api/cursor_service.py` | Features de cursor, generador sintético y modelo de mouse dynamics. |
| `continuous_auth/test_settings.py` | Settings de test aislados (SQLite en memoria). |
| `manage.py` | Punto de entrada de Django. |
| `requirements.txt` | Dependencias. |
| `Dockerfile` / `docker-entrypoint.sh` / `build.sh` | Despliegue. |

---

## 7. Validaciones realizadas

| Prueba | Resultado |
|---|---|
| `python manage.py check` | Sin incidencias. |
| Migraciones | `0001_initial` aplicada correctamente. |
| Entrenamiento `s002` | 2400 muestras (sesiones 1–6) → `.joblib` generado. |
| `POST /api/retrain/` con 1 registro | `422` — "Se requieren al menos 3 registros". |
| `POST /api/predict/` usuario inexistente | `404` — mensaje guía hacia `/api/retrain/`. |
| `POST /api/predict/` muestra válida | `200` + registro en `AuthInferenceLog`. |
| Modelos generados | 51 modelos `iforest_*.joblib`. |

---

## 8. Métricas de referencia

Configuración del benchmark (split por sesión: train 1–6, test 7–8, 51 sujetos).
El umbral **por defecto en producción** es el óptimo calibrado
`ML_DECISION_THRESHOLD = 0.021328`; el valor `0.0` (frontera natural del
algoritmo) se conserva como **línea base** de comparación:

| Umbral | FAR | FRR | Accuracy |
|---|---|---|---|
| **0.0 (línea base)** | ≈ 27.8 % | ≈ 6.0 % | ≈ 72.6 % |
| **+0.021328 (por defecto, óptimo)** | ≈ 16.3 % | ≈ 11.1 % | ≈ 83.8 % |

El umbral es configurable por entorno (`ML_DECISION_THRESHOLD`) para ajustar la
política de riesgo: subirlo reduce FAR a costa de aumentar FRR, y viceversa. Las
métricas definitivas deben obtenerse con `python manage.py evaluate_models` o
`python manage.py benchmark_report`.

### 8.1. Respuesta a la pregunta de investigación: EER

El proyecto se pregunta **qué EER (Equal Error Rate) alcanza el modelo para distinguir al
usuario legítimo de un impostor**. Ese indicador se materializa ahora en un reporte persistente y
consultable, no solo en la salida de consola:

| Resultado del benchmark (51 sujetos, split por sesión) | Valor |
|---|---|
| **EER medio** | **12.19 %** |
| EER mediana | 11.00 % |
| EER min / max | 1.00 % / 35.22 % |
| EER desviación | 7.58 % |
| **AUC-ROC medio** | **93.85 %** |
| FAR @ umbral 0.0 | 27.79 % |
| FRR @ umbral 0.0 | 6.04 % |
| Accuracy @ umbral 0.0 | 72.64 % |
| **Umbral óptimo recomendado** | **+0.021328** |

Con el umbral óptimo (que minimiza |FAR − FRR|), las métricas a umbral 0.0 mejoran notablemente:
FAR **27.8 % → 16.3 %**, FRR 6.0 % → 11.1 %, accuracy **72.6 % → 83.8 %**, manteniendo el EER en
12.19 % (el EER es invariante al umbral por definición).

**Interpretación:** un EER de ~12 % implica que, en el punto de equilibrio, el sistema falla
aproximadamente 1 de cada 8 decisiones, repartiendo el error por igual entre legítimos rechazados
e impostores aceptados. El AUC de ~94 % confirma una alta separación de clases; el error se
concentra en la zona de solapamiento de scores, no en una confusión global.

### 8.2. Cómo reproducir y consultar el EER

```bash
# 1. Genera docs/REPORTE_EER.md y docs/benchmark_eer.json (tabla por sujeto incluida)
python manage.py benchmark_report --per-subject

# 2. Consulta el agregado por API
curl http://localhost:8000/api/metrics/summary/
curl http://localhost:8000/api/metrics/curve/
```

- **`docs/REPORTE_EER.md`** — reporte legible con la respuesta a la pregunta de investigación,
  tablas agregadas y detalle por sujeto.
- **`docs/benchmark_eer.json`** — datos crudos que consume la API y el frontend.
- **Pantalla «Rendimiento»** del frontend — muestra el EER, AUC, FAR/FRR y la curva FAR vs FRR
  con el punto de equilibrio resaltado.

Los endpoints `/api/metrics/summary/` y `/api/metrics/curve/` del microservicio ML se exponen a
través del backend Spring (`/api/metrics/summary/`, `/api/metrics/curve/`), que actúa de fachada
para que el frontend hable un único origen (compatible con el despliegue en Render).

---

## 8.3. Dinámica del cursor (mouse dynamics)

Como complemento al tecleo, el sistema incluye un conjunto **paralelo e
independiente** de features basadas en el movimiento y los clics del cursor.
Está diseñado de forma **totalmente aditiva**: no modifica el esquema de tecleo
(31 features CMU) ni sus modelos; conviven sin interferencias.

### 8.3.1. Features (12)

Genéricas e independientes de la resolución:

| Feature | Descripción |
|---|---|
| `M.speed_mean` | velocidad media (px/ms) |
| `M.speed_std` | desviación de la velocidad |
| `M.speed_max` | velocidad máxima |
| `M.accel_mean` | aceleración media (variación de velocidad) |
| `M.jitter` | variación de la dirección (ruido del pulso) |
| `M.curvature_mean` | curvatura media de la trayectoria |
| `M.straightness` | 1.0 = línea recta perfecta |
| `M.pause_ratio` | fracción de tiempo sin movimiento |
| `M.pause_count` | nº de pausas (> 100 ms sin movimiento) |
| `M.click_rate` | clics por segundo |
| `M.interclick_mean` | tiempo medio entre clics (ms) |
| `M.path_efficiency` | distancia neta / distancia recorrida |

### 8.3.2. Generador sintético

Antes de contar con captura real masiva, `cursor_service.generate_synthetic_cursor_records`
produce muestras **reproducibles** por usuario. Cada `user_id` recibe un perfil
estable (`precise`, `fast`, `erratic`, `slow`) derivado de un hash determinista;
sobre ese perfil se añade ruido gaussiano proporcional para simular la
variabilidad natural entre repeticiones. Con la misma semilla, la salida es
idéntica. Cuando exista captura real, `train_cursor_model` acepta esos `records`
directamente sin cambios en el esquema.

### 8.3.3. Modelo y umbral

- Algoritmo: `IsolationForest` (mismos hiperparámetros que el de tecleo).
- Modelo persistido como `ml_models/cursor_iforest_<user>.joblib` (prefijo
  distinto al de tecleo para no colisionar).
- Umbral propio `ML_CURSOR_DECISION_THRESHOLD` (por defecto hereda
  `ML_DECISION_THRESHOLD`), de modo que calibrar el cursor no afecta al tecleo.

### 8.3.4. Endpoints

| Método | Ruta (ML) | Ruta (backend) | Descripción |
|---|---|---|---|
| `POST` | `/api/cursor/retrain/` | `/api/cursor/retrain/` | Entrena con `records` reales o `synthetic:true` |
| `POST` | `/api/cursor/predict/` | `/api/cursor/predict/` | Verifica una sesión de cursor |
| `GET` | `/api/cursor/synthetic/` | (directo al ML) | Dataset sintético reproducible |

### 8.3.5. Interfaz

La pestaña **«Dinámica del cursor»** del frontend ofrece una zona interactiva:
el usuario mueve el cursor y hace clic; cada ráfaga es una *sesión* con sus 12
features. Tras acumular sesiones puede (a) entrenar con sus datos reales, (b)
entrenar con datos sintéticos para demos, y (c) verificar una nueva sesión
contra el modelo.

### 8.3.6. Pruebas

- Python: `CursorSyntheticTests`, `CursorModelTests`, `CursorEndpointsTests`
  (10 casos) — generador, cotas físicas, entrenamiento, separación
  legítimo/impostor y endpoints.
- Java: `CursorControllerTest` (2 casos) — la fachada reenvía al modelo.

---

## 8.4. Persistencia de modelos en producción

Los modelos ``.joblib`` viven en disco. En local eso es suficiente, pero en un
contenedor el filesystem es **efímero**: cada redeploy o reinicio borraría los
modelos de usuario. La solución adoptada **separa dos tipos de modelo**:

| Tipo | Identificador | Dónde vive | ¿Persiste? |
|---|---|---|---|
| **Dataset** | ``s002`` … (CMU) | ``ML_MODELS_DIR`` (en la imagen) | No hace falta: es inmutable y va empaquetado. |
| **Usuario** | ``user-<username>`` | ``ML_USER_MODELS_DIR`` (volumen) | **Sí**, en el Disco de Render. |
| **Cursor** | siempre de usuario | ``ML_USER_MODELS_DIR`` (volumen) | **Sí**. |

La distinción se resuelve en un único punto, ``ml_service.model_path_for``:
si el id empieza por ``user-`` va al directorio persistente; si no, al del
dataset. Esto mantiene intacto el flujo de tecleo y evita re-entrenar los 51
modelos del dataset en cada arranque.

### Configuración

- **Local / tests:** no se define ``ML_USER_MODELS_DIR`` → por defecto es igual a
  ``ML_MODELS_DIR``. Comportamiento **idéntico** al anterior, nada cambia.
- **Producción (Render):** se monta un Disco en ``/data`` y se define
  ``ML_USER_MODELS_DIR=/data/user_models``. El ``docker-entrypoint.sh`` crea la
  subcarpeta al arrancar.

### Despliegue en Render (pasos)

1. Crear un **Disk** (Web Service → Disks): nombre ``user-models``, mount path
   ``/data``, 1 GB.
2. Variable de entorno ``ML_USER_MODELS_DIR=/data/user_models``.
3. (Opcional) usar el ``render.yaml`` incluido, que ya declara disco + variable.

### Limitación y fase siguiente

Un Render Disk va atado a **una sola instancia** (``numInstances=1``). Para
escalar horizontalmente a varias réplicas hace falta un almacenamiento
compartido (S3 / Cloudflare R2 / Supabase Storage) con caché local. Está
previsto como evolución; la abstracción de rutas ya deja el punto de
integración localizado en ``model_path_for``/``cursor_model_path_for``.

### Pruebas

``ModelStorageSeparationTests`` (6 casos) verifica que ``sXXX`` va a
``ML_MODELS_DIR``, ``user-*`` y los modelos de cursor van a
``ML_USER_MODELS_DIR``, y que sin el setting todo cae a ``ML_MODELS_DIR``
(compatibilidad).

---

## 9. Estado actual y trabajo pendiente

**Operativo:** pipeline de entrenamiento, inferencia, auditoría, importación del dataset,
evaluación y contenerización.

**Pendiente / mejoras:**
1. ~~Calibración formal del umbral (curva FAR vs FRR / EER) y fijarlo en producción.~~
   **Resuelto**: `benchmark_report` calcula el umbral óptimo (+0.021328) y el EER (12.19 %);
   ver §8.1. Fijado como valor por defecto de `ML_DECISION_THRESHOLD` (0.0 conservado como
   línea base documentada).
2. **Endurecer la verificación frente a impostores "promedio".** IsolationForest es permisivo con
   patrones raros pero globalmente normales (ver §4.6.7). Evaluar un enfoque híbrido que combine el
   detector de anomalías con un clasificador supervisado entrenado usando las muestras de otros
   sujetos como pseudo-impostores. Es una decisión de producto, no solo técnica.
3. ~~Persistencia de modelos en producción más allá del sistema de ficheros del contenedor
   (volumen persistente u objeto externo), ya que el filesystem puede ser efímero.~~
   **Resuelto (volumen persistente)**: los modelos de usuario (``user-*`` y de cursor) se
   guardan en ``ML_USER_MODELS_DIR``, que en despliegue apunta a un Disco de Render
   (``/data/user_models``). Los modelos del dataset (``sXXX``) permanecen en la imagen.
   Ver §8.4. Para escalar a varias réplicas habría que migrar a almacenamiento de objetos.
4. ~~`SECRET_KEY` y demás secretos por variable de entorno en despliegue.~~
   **Resuelto**: con `DEBUG=False`, si `DJANGO_SECRET_KEY` no está definido el arranque
   **falla** explícitamente (en vez de usar la clave insegura por defecto). En local
   (`DEBUG=True`) se mantiene la clave de desarrollo para comodidad.
5. ~~Pruebas automatizadas (`tests.py`) de los endpoints y del servicio ML.~~
   **Resuelto parcialmente**: `tests.py` cubre el servicio ML, métricas, cursor y
   endpoints (29 pruebas Python; más 4 en Java). Queda ampliar cobertura de casos límite.

---

## 10. Conclusiones

El sistema materializa una arquitectura de microservicios donde el análisis y diseño se apoyaron
en **NotebookLM** para sintetizar el dominio (keystroke dynamics), seleccionar el modelo
(IsolationForest de una clase) y definir el contrato y la persistencia. La implementación separa
limpiamente:
- **Dominio ML** (`ml_service`),
- **Adaptación HTTP** (`views`/`urls`),
- **Persistencia y auditoría** (`models`),
- **Operación** (comandos de gestión, Docker, build).

Esta separación permite evaluar, reentrenar y desplegar el modelo de forma independiente del
resto de la plataforma, cumpliendo los requisitos funcionales y no funcionales definidos durante
el análisis.

---

## 11. Referencias

**Dataset y dinámica de tecleo**

1. Killourhy, K. S., & Maxion, R. A. (2009). *Comparing Anomaly-Detection Algorithms for
   Keystroke Dynamics*. IEEE/IFIP International Conference on Dependable Systems & Networks
   (DSN), 125–134. — Origen del dataset **CMU DSL-StrongPasswordData** y del benchmark de
   algoritmos de detección de anomalías para tecleo.
2. CMU Data Set for Keystroke Dynamics. Carnegie Mellon University, School of Computer Science.
   `https://www.cs.cmu.edu/~keystroke/`.
3. Monrose, F., & Rubin, A. D. (2000). *Keystroke Dynamics as a Biometric for Authentication*.
   Future Generation Computer Systems, 16(4), 351–359. — Fundamentos de la biometría de tecleo y
   sus tipos de features (hold time, latencias).

**Detección de anomalías**

4. Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). *Isolation Forest*. IEEE International
   Conference on Data Mining (ICDM), 413–422. — Algoritmo base del sistema.
5. Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2012). *Isolation-Based Anomaly Detection*. ACM
   Transactions on Knowledge Discovery from Data (TKDD), 6(1), 1–39. — Extensión y análisis
   del método.
6. Chandola, V., Banerjee, A., & Kumar, V. (2009). *Anomaly Detection: A Survey*. ACM Computing
   Surveys, 41(3), 1–58. — Marco general de detección de anomalías (una clase, aprendizaje no
   supervisado).

**Métricas biométricas**

7. Bolle, R. M., Connell, J. H., Pankanti, S., Ratha, N. K., & Senior, A. W. (2013). *Guide to
   Biometrics*. Springer. — Definición de FAR, FRR, EER y AUC-ROC.
8. Fawcett, T. (2006). *An Introduction to ROC Analysis*. Pattern Recognition Letters, 27(8),
   861–874. — Curva ROC y AUC.

**Tecnologías**

9. Pedregosa, F., et al. (2011). *Scikit-learn: Machine Learning in Python*. Journal of Machine
   Learning Research (JMLR), 12, 2825–2830.
10. Django Software Foundation. *Django Documentation* — `https://docs.djangoproject.com/`.
11. Django REST Framework — `https://www.django-rest-framework.org/`.
12. Spring Boot Reference Documentation — `https://docs.spring.io/spring-boot/`.
13. React Documentation — `https://react.dev/`.

**Herramienta de análisis**

14. Google NotebookLM — `https://notebooklm.google.com/` — empleado en la fase de análisis de
    dominio y síntesis de requisitos (§2).
