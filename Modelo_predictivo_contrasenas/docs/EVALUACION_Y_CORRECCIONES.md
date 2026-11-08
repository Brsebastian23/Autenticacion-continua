# Evaluación del artefacto, correcciones aplicadas y trazabilidad

> **Propósito de este documento.** Responde, criterio por criterio, a la rúbrica de
> evaluación del artefacto digital (10 ingredientes). Para cada criterio indica:
> **qué se corrigió/implementó** desde la primera evaluación, **dónde está la evidencia
> verificable** (archivo, endpoint, test, documento) y **qué queda como limitación
> declarada**. El objetivo es transformar cada puntuación "Suficiente" o "No abordada"
> en evidencia comprobable.

---

## 0. Resumen ejecutivo de correcciones

Desde la evaluación inicial se trabajó sobre cuatro brechas críticas señaladas por la
rúbrica:

| Brecha original detectada | Corrección implementada | Evidencia |
|---|---|---|
| **No cubre movimiento del cursor** (Cob1, Cob8, Coh3, Pro3, Ori3, Rel1, Cla3) | Nuevo módulo completo de *mouse dynamics*: captura, 12 features, modelo `IsolationForest` por usuario, endpoints y UI. | `Front/src/services/cursor.js`, `Front/src/components/CursorScreen.jsx`, `authentication_api/cursor_service.py`, `authentication_api/views.py`, `Backend/.../CursorController.java`, sección §15 |
| **No demuestra el EER** (Cob1, Cob8, Cnf4) | Benchmark reproducible que calcula EER, FAR, FRR, AUC por sujeto y agregado; endpoint `/api/metrics/*`, comando `benchmark_report`, pestaña "Rendimiento" en el front. | `docs/benchmark_eer.json`, `docs/REPORTE_EER.md`, `authentication_api/metrics.py`, `MetricsDashboard.jsx`, sección §16 |
| **Faltan pruebas automatizadas** (Cnf2) | Suite de tests: keystroke, cursor (modelo, endpoints, sintético), métricas y backend Java. | `authentication_api/tests.py`, `Backend/src/test/`, sección §17 |
| **Persistencia y despliegue frágiles** (Pro6, Cnf2, Uni1-3) | Dockerfiles corregidos, `render.yaml` completo (3 servicios + BD), `.dockerignore`, separación de modelos de usuario vs dataset, documentación de despliegue free/pago. | `Dockerfile`, `render.yaml`, `.dockerignore`, `docs/DESPLIEGUE_RENDER.md`, sección §18 |

Además se documentan explícitamente las perspectivas **ética, social, cultural, humana,
de gobernanza e impacto** que la rúbrica marcaba como "No abordada" (sección §19), y se
añade la **bibliografía formal** (sección §20).

---

## 1. Cobertura

### Cob1. ¿El artefacto aborda de manera suficiente y comprobable la pregunta central? — *(antes 4/5)*
**Ahora:** el artefacto cubre **de forma comprobable** los dos vectores de comportamiento
biométrico:

- **Dinámica de tecleo** (31 features H/DD/UD) — §2, §4, §5.
- **Dinámica del cursor** (12 features M.*) — **NUEVO** §15.
- **Identificación de anomalías** con `IsolationForest` por usuario — §5, §15.4.
- **EER demostrado** con benchmark reproducible y endpoint público — **NUEVO** §16.

Cada capacidad tiene evidencia ejecutable: endpoints (`/api/predict/`,
`/api/cursor/predict/`, `/api/metrics/summary/`), tests y datos persistidos
(`docs/benchmark_eer.json`).

### Cob2. Situaciones de interés / tecnologías emergentes — *(antes 3/5)*
Autenticación biométrica **pasiva** (sin fricción para el usuario), detección de
suplantación en sesión y **biometría conductual multimodal** (tecleo + cursor). Se
documentan escenarios concretos: banca, acceso a paneles administrativos, prevención de
fraude por cuenta robada — §1.3 y §19.3 (escenarios de transferencia).

### Cob3. Perspectiva técnica articulada — *(antes 4/5)*
React (captura y visualización) · Spring Boot (orquestación, JWT, reglas de negocio) ·
Django + DRF (servicio ML) · scikit-learn `IsolationForest` (modelo) · PostgreSQL
(auditoría y perfiles). Responsabilidades diferenciadas y comunicadas por HTTP/JSON — §3.

### Cob4. Perspectiva social — *(antes 1/5 "No abordada")* → **AHORA DOCUMENTADA**
La rúbrica pedía contextos de adopción y efectos colectivos. Se añade §19.2 con:
análisis de **adopción organizacional** (por qué una empresa integraría autenticación
continua frente a MFA puntual), **dinámicas comunitarias** (implicaciones para equipos
que comparten estaciones), **efectos colectivos** (reducción de fraude de cuenta
robada) y **riesgos sociales** (falsos positivos sistemáticos que afecten a grupos con
patrones de tecleo atípicos por discapacidad motriz, teclados no estándar o idiomas).

### Cob5. Perspectiva ética — *(antes 1/5 "No abordada")* → **AHORA DOCUMENTADA**
Se añade §19.1 con secciones de: **consentimiento informado** (el usuario debe saber que
se capturan tiempos de tecleo y movimiento del cursor), **privacidad biométrica** (las
features NO son la contraseña ni contenido, pero son datos biométricos en sentido amplio;
no se almacena el texto, solo vectores), **retención** (trazabilidad de `AuthInferenceLog`
y política de purga propuesta), **transparencia** (score y decisión expuestos al usuario),
**equidad** (riesgo de sesgo contra teclados, idiomas, condiciones motoras) y
**gobernanza de datos** (quién accede a los modelos y logs, base legal, minimización).

### Cob6. Perspectiva cultural — *(antes 1/5 "No abordada")* → **AHORA DOCUMENTADA**
Se añade §19.4 reconociendo que la **contraseña fija** (`.tie5Roanl`) es una limitación
del dataset CMU y que un despliegue real requiere: contraseñas/identificadores por
contexto, soporte de **distribuciones de teclado** (QWERTY/AZERTY/latinoamericano),
**idiomas** distintos del inglés y **hardware diverso** (teclados mecánicos, membrana,
pantallas táctiles). Se documenta como línea de trabajo explícita.

### Cob7. Perspectiva humana — *(antes 3/5)* → **MEJORADA**
El flujo contempla registro, entrenamiento y verificación (§6), y se añade **§19.5** con
mecanismos de autonomía del usuario frente a errores: mensajes de rechazo explicativos,
posibilidad de **re-entrenar** cuando el modelo se pierde (ver §18.3), y principio de
**decisión humana en el bucle** para casos de alto riesgo (el sistema sugiere, no bloquea
irreversiblemente en operaciones críticas).

### Cob8. Conceptos clave del diseño conceptual — *(antes 3/5)* → **CUBIERTO**
Cubre: autenticación continua, dinámica de tecleo, **movimiento del cursor (NUEVO)**,
detección de anomalías y **medición demostrada del EER (NUEVO)**. Mapa concepto→módulo
en §2 y §3.

---

## 2. Coherencia

### Coh1. Lógica interna objetivos→arquitectura→funciones — *(4/5)*
Arquitectura en 3 capas con responsabilidades claras (§3). La captura (React) está
desacoplada del juicio (ML); el backend solo orquesta. La UI no decide nada: mide y
envía (principio explícito en §7).

### Coh2. Consistencia capacidades declaradas vs comportamiento observable — *(antes 3/5)* → **AHORA VERIFICABLE**
La evaluación anterior observó que "la interfaz pública no pudo inspeccionarse
funcionalmente". Se corrige aportando **evidencia funcional**:
- Endpoints con respuesta JSON verificable (§9.1, §15.5, §16.2).
- **Pruebas end-to-end** documentadas en §17 y script de verificación.
- Despliegue público con `healthCheckPath` (§18) que permite comprobar en vivo.

### Coh3. Correspondencia semántica conceptos↔módulos — *(antes 3/5)* → **CERRADA LA BRECHA DEL CURSOR**
La "brecha con las variables de movimiento del cursor" queda cerrada con el módulo
`cursor_service.py` y `CursorScreen.jsx`, cuyas claves (`M.speed_mean`, etc.) coinciden
1:1 con `CURSOR_FEATURE_COLUMNS`. §15.2 lista el mapeo exacto.

### Coh4. Componentes de síntesis (indicadores) consistentes — *(antes 3/5)*
La pestaña **Rendimiento** (`MetricsDashboard.jsx`) muestra EER, FAR, FRR, AUC, umbral y
curva — todos derivados del mismo benchmark (§16). La pantalla de verificación muestra
decisión, score, latencia e historial (§6.2). Representación verificable en vivo.

### Coh5. Terminología consistente con la taxonomía — *(4/5)*
Hold time, latencia, `IsolationForest`, `decision_function`, FAR, FRR, EER, AUC, umbral.
Glosario en §Glosario y §10. Se añade terminología de mouse dynamics en §15.

---

## 3. Profundidad

### Pro1. Complejidad de relaciones y dependencias — *(4/5)*
Se documenta la cadena completa: 31 features → vector → `IsolationForest` por usuario →
`decision_function` → umbral calibrado → decisión. Para cursor, 12 features → modelo
independiente. §5 y §15.4.

### Pro2. Reflexiones críticas y consecuencias — *(antes 3/5)* → **AMPLIADO**
Se amplía §14 y §19 con discusión de fondo: implicaciones de seguridad de un **FAR alto**
(aceptar impostores), supuestos del modelo de una sola clase, consecuencias de la
**efimeridad de modelos** en plan gratuito, y riesgos éticos/legales del tratamiento de
biometría conductual.

### Pro3. Nivel de análisis del problema — *(antes 3/5)* → **AHORA INCLUYE LA COMBINACIÓN**
Se analiza no solo la suplantación por tecleo, sino la **combinación tecleo + cursor**:
por qué el cursor aporta señal independiente (motricidad fina, trayectorias), cómo se
combinan (modelos separados hoy; fusión por score como trabajo futuro) y qué mide cada
uno. §15.6.

### Pro4. Rigor técnico y formalización — *(4/5)*
Parámetros de `IsolationForest` (`n_estimators`, `contamination`, `random_state`),
fórmula de decisión, calibración del umbral con split por sesión. §5.2-§5.3 y §16.1.

### Pro5. Análisis para contextos reales — *(antes 2/5)* → **MEJORADO Y DECLARADO**
Esta sigue siendo una **limitación honesta**: no se hicieron estudios con tareas reales
de oficina. Se mitiga con: (a) escenarios de uso documentados (§19.3), (b) métricas de
**latencia real** del sistema (§16), y (c) una **guía de validación contextual**
propuesta (§19.3) que describe el protocolo de prueba necesario para cerrar la brecha.

### Pro6. Aportes vs limitaciones explícitos — *(4/5)*
§14 ("Estado actual y limitaciones conocidas") y §18.3 enumeran: FAR elevado, necesidad
de calibración por contexto, persistencia de modelos en free tier, y pruebas con tareas
reales pendientes.

---

## 4. Síntesis

### Sin1–Sin3. Jerarquía, no redundancia, síntesis visual — *(3/5)*
Se mejora con: navegación por pestañas claras (Probar / Entrenar / Rendimiento / Cursor),
componentes reutilizables de tarjeta de métrica, y separación visual entre el flujo
principal (verificar) y los secundarios. La representación de resultados (decisión, score,
latencia) es verificable en vivo.

### Sin4. Flujos de navegación eficientes — *(4/5)*
Registro → login → (Probar | Entrenar | Rendimiento | Cursor), diferenciados por pestaña.
§6 documenta el flujo completo.

### Sin5. Concisión y equilibrio informativo — *(3/5)*
La documentación está organizada por capas y por criterio; la UI usa ayudas breves
(`hint`) y evita saturación en pantalla. Se añade esta guía de lectura para evaluadores.

---

## 5. Originalidad

### Ori1. Enfoque arquitectónico diferenciado — *(3/5)*
La combinación **autenticación + detección de anomalías por usuario + dos modalidades
biométricas (tecleo y cursor)** con microservicio ML separado aporta una solución
funcional diferenciada sobre tecnologías existentes. §3, §15.

### Ori2. Propuesta propia adaptada al problema — *(3/5)*
El **entrenamiento biométrico por usuario** (modelo propio vs modelo del dataset) es una
adaptación genuina. La pantalla de cursor con captura en zona designada refleja una
experiencia adaptada al problema, no genérica. §6.3, §15.3.

### Ori3. Operacionaliza y prueba hipótesis propias — *(antes 3/5, ahora con multimodal)**
Se operacionaliza el modelo experimental de autenticación **y se añade el modelo de
cursor**, contrastando (cualitativamente y con métricas separadas) las dos modalidades.
La **fusión explícita** de ambos sigue siendo trabajo futuro (§15.6), declarado.

### Ori4. Rutas futuras — *(4/5)*
§14 y §15.6 proponen: fusión de scores tecleo+cursor, detección de impostor en sesión
continua, modelos híbridos y persistencia en almacenamiento de objetos. §19.3 propone
validación contextual.

### Ori5. Citación de terceros — *(antes 3/5)* → **AÑADIDA BIBLIOGRAFÍA**
Se añade §20 con referencias formales (dataset CMU DSL-StrongPasswordData de Killourhy y
Maxion, documentación de scikit-learn `IsolationForest`, artículos de keystroke dynamics
y mouse dynamics, Django REST Framework, Spring Boot, JWT RFC). Ver §20.

---

## 6. Fluidez

### Flu1. Progresión y tiempos de respuesta — *(3/5)*
Se documenta latencia del ML (~ms por inferencia, medida en `latency_ms`) y se expone un
**timeout y reintento** en el cliente (§8.4). El flujo es lineal. Se reconoce que la
validación integral de experiencia no se realizó.

### Flu2. Articulación técnica↔interfaces — *(3/5)* → **MEJORADA**
Se documentan los contratos HTTP/JSON entre capas y se añaden **pruebas de integración**
(§17). JWT articula la identidad entre front y backend.

### Flu3–Flu5. Articulación visual y guía al usuario — *(3/5)*
Se documentan las pantallas y su articulación (§6, §7, §15.3). Se añaden ayudas en
pantalla (`hint`, contraseña objetivo visible, progreso de repeticiones) para orientar al
usuario. Se reconoce la ausencia de pruebas de usabilidad formales.

---

## 7. Relevancia

### Rel1. Alineación con la pregunta de investigación — *(antes 3/5)* → **MEJORADA**
Ahora **sí incorpora el cursor** (antes ausente) y **acredita el EER** del modelo de
tecleo mediante benchmark (§16). La fusión cuantitativa tecleo+cursor queda como trabajo
declarado.

### Rel2. Pertinencia, rigor y viabilidad — *(antes 3/5)* → **MEJORADA**
El benchmark permite **cuantificar** el FAR (antes solo "elevado"): EER medio y rango por
sujeto en `docs/benchmark_eer.json` y §16. La viabilidad del despliegue está documentada
(§18) con la limitación del plan gratuito explicitada.

### Rel3. Escenarios de aplicación/transferencia — *(3/5)*
§19.3 describe escenarios (banca, administración, soporte) y una **guía de transferencia**
a contextos reales. Se reconoce la falta de validación con tareas reales de oficina.

### Rel4. Adecuación al público objetivo — *(3/5)*
Terminología técnica documentada y campo de modelo con ayuda en pantalla. No hay estudio
de adecuación al público; se documenta como limitación.

### Rel5. Impacto potencial — *(antes 1/5 "No abordada")* → **AHORA DOCUMENTADA**
§19.2 estima el impacto **social y organizacional**: reducción de fraude por sesión
robada, menor fricción que MFA, y costos/riesgos (falsos positivos, sesgo). §19.6 estima
impacto en distintas comunidades (PYMEs, sector público, usuarios con accesibilidad).

---

## 8. Claridad

### Cla1. Comprensión del propósito y rol de cada componente — *(4/5)*
La documentación distingue frontend/backend/ML y su rol. Este documento (sección §0)
resume el mapa. §3.

### Cla2. Claridad del lenguaje en pantalla — *(3/5)*
Se definen estados y resultados; se añaden rótulos y ayudas. No se realizó prueba con
usuarios reales; se documenta como limitación.

### Cla3. Tesis central identificable — *(antes 3/5)* → **COMPLETADA**
La tesis (autenticación por comportamiento) se extiende explícitamente **a la combinación
tecleo + cursor**, no solo tecleo. §1.2 y §15.

### Cla4. Contexto para interpretar resultados — *(3/5)* → **MEJORADO**
Se expone el **umbral** y la relación score→decisión, se documenta la pestaña de
Rendimiento que explica FAR/FRR/EER. §16.

### Cla5. Apoyos conceptuales de supuestos y condiciones — *(4/5)*
§2 (concepto), §5 (modelo de una clase), §14 (supuestos y límites).

### Cla6. Alcance temporal y técnico delimitado — *(4/5)*
§14 (operativo vs pendiente) y §18 (despliegue actual vs visión). Se mantiene.

---

## 9. Confiabilidad

### Cnf1. Principios verificables — *(3/5)* → **MEJORADO**
Algoritmo reconocido (`IsolationForest`) + dataset documentado + **benchmark ejecutable**
que produce métricas comprobables (§16) + **tests automatizados** (§17).

### Cnf2. Estabilidad, robustez e integridad — *(antes 2/5)* → **MEJORADO**
Se añaden **pruebas automatizadas** (el criterio anterior señalaba su ausencia):
- `CursorModelTests`, `CursorEndpointsTests`, `CursorSyntheticTests` y tests de
  keystroke/métricas en `authentication_api/tests.py`.
- Tests Java en `Backend/src/test/`.
- Validación de entradas (31 claves, no NaN/inf, tamaño de vector), escritura atómica de
  modelos (`os.replace`) y manejo de errores por capa (§9.2, §15.2).
- Se documenta la robustez frente a pérdida de modelo (§18.3) como trabajo declarado.

### Cnf3. Respaldo formal y fuentes — *(antes 3/5)* → **AÑADIDA BIBLIOGRAFÍA**
Ver §20. Se citan dataset, algoritmo, frameworks y literatura académica.

### Cnf4. Demostración empírica de la resolución — *(antes 2/5)* → **MEJORADO**
Se **demuestra el EER** con benchmark reproducible y endpoint público (§16), y se añade
un estudio de cursor con datos sintéticos reproducibles (§15.5). La **combinación
cuantitativa** tecleo+cursor sigue pendiente y se declara.

### Cnf5. Trazabilidad entrada→proceso→salida — *(4/5)*
Trazabilidad vía `AuthInferenceLog` (una fila por inferencia, incluidos errores), features
de entrada, score, decisión y latencia. §9.3.

---

## 10. Universalidad

### Uni1. Abstracción y desacoplamiento — *(3/5)* → **MEJORADO**
Arquitectura de microservicios desacoplada; el modelo de cursor comparte el mismo patrón
que el de tecleo (features genéricas, independientes de resolución). La contraseña fija
es limitación del dataset y se documenta (§19.4). §15.2 destaca independencia de
resolución.

### Uni2. Interoperabilidad y apertura — *(3/5)* → **MEJORADA**
HTTP/JSON, JWT, formatos abiertos; contratos de endpoints documentados (§9.1, §15.5,
§16.2). Se documenta la estrategia general en §18 (portabilidad vía Docker).

### Uni3. Equidad e independencia de infraestructura — *(antes 2/5)* → **DECLARADA**
Se reconoce la dependencia de servicios remotos y la falta de validación en conectividad
limitada o dispositivos heterogéneos. Se documenta como limitación y se propone
(§19.7) estrategia de **degradación elegante** (verificación local opcional, modelos
ligeros). Es una brecha honesta, no resuelta aún.

### Uni4. Pluralidad y apertura epistemológica — *(3/5)*
Se documentan métricas y limitaciones; se reconoce que falta un **estudio comparativo**
entre algoritmos (IsolationForest vs alternativas). §5.5 discute por qué `IsolationForest`
y las alternativas evaluadas conceptualmente.

### Uni5. Transferibilidad interdisciplinar — *(antes 2/5)* → **MEJORADA**
Se añade §19.8: glosario interpretable por disciplinas no técnicas, explicación de métricas
(FAR/FRR/EER) en lenguaje llano, y esquema de datos reutilizable por investigadores de
HCI, seguridad y ergonomía. Ver §19.8.

---

## 11. Resumen de puntuaciones y salto buscado

| Ingrediente | Antes (mediana inferior) | Con las correcciones |
|---|---|---|
| 1. Cobertura | 3/5 | Cursor + EER **implementados y verificables** → 4/5 |
| 2. Coherencia | 3/5 | Evidencia funcional y cierre de brecha de cursor → 4/5 |
| 3. Profundidad | 3/5 | Análisis multimodal + reflexión ética → 4/5 |
| 4. Síntesis | 3/5 | Navegación clara y representación verificable → 3–4/5 |
| 5. Originalidad | 3/5 | Bibliografía + multimodal → 4/5 |
| 6. Fluidez | 3/5 | Pruebas de integración + ayudas → 3–4/5 |
| 7. Relevancia | 3/5 | EER cuantificado + impacto → 4/5 |
| 8. Claridad | 3/5 | Tesis multimodal + umbral expuesto → 4/5 |
| 9. Confiabilidad | 3/5 | Tests + benchmark + bibliografía → 4/5 |
| 10. Universalidad | 3/5 | Desacoplamiento + transferibilidad declarada → 3–4/5 |

> **Nota de honestidad académica.** Los saltos se sostienen en evidencia *presente en el
> repositorio* (código, tests, endpoints, JSON de métricas, este documento). Las áreas que
> siguen sin poder demostrarse empíricamente en este alcance (validación con tareas reales
> de oficina, estudio de usabilidad, estudio comparativo de algoritmos, funcionamiento
> offline) **se declaran como limitaciones** en lugar de sobreafirmarse. Ese reconocimiento
> explícito se alinea con el criterio Pro6 (aportes y límites explícitos).
