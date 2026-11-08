# Perspectivas éticas, sociales, culturales, humanas y de impacto

> **Qué es este documento.** La evaluación del artefacto señaló que varias dimensiones no
> técnicas no estaban abordadas (Cob4 social, Cob5 ética, Cob6 cultural, Rel5 impacto, Uni5
> transferibilidad). Este documento las cubre explícitamente. Su objeto es **declarar, no
> idealizar**: cada sección reconoce riesgos y vacíos reales del sistema, y distingue lo ya
> implementado de lo que queda como trabajo pendiente.

---

## 19.1. Perspectiva ética (responsabilidad, gobernanza, transparencia, equidad)

### 19.1.1. Naturaleza de los datos tratados
El sistema recoge **biometría conductual**: tiempos de tecleo (31 features H/DD/UD) y dinámica
del cursor (12 features M.*). Es importante precisar:

- **No se almacena el texto** escrito ni la contraseña como contenido biométrico: se derivan
  **vectores numéricos** de tiempo. La contraseña viaja una sola vez al login para validarse con
  BCrypt y **no se retiene**.
- Aun así, la dinámica de tecleo es **datos biométricos** en sentido amplio (art. 4, RGPD, y
  regulaciones análogas): identifican o contribuyen a identificar a una persona por su comportamiento.

### 19.1.2. Consentimiento informado
Requisito documentado: el usuario debe **saber antes de usar** que se capturan tiempos de tecleo y
movimiento del cursor. En la implementación actual, la captura ocurre al interactuar con las
pantallas de entrenamiento y verificación; la interfaz comunica que se está capturando (instrucción
de escribir la contraseña y repetirla). **Pendiente:** añadir una **pantalla de consentimiento
explícito** y una política de privacidad de una página antes del primer entrenamiento (ver
plan de acción §19.7). Se declara como vacío actual.

### 19.1.3. Privacidad y minimización
- **Minimización**: se guardan features temporales, no pulsaciones crudas ni contenido. `AuthInferenceLog`
  guarda score, decisión, latencia y estado, **sin** datos del teclado.
- **Finalidad**: los datos solo sirven para verificar identidad, no para perfilado publicitario.
- **Riesgo residual**: un vector de features es un identificador biométrico; si se filtra, podría
  intentarse una suplantación que imite los tiempos. Mitigación propuesta: cifrado en reposo y
  rotación, y no exponer features crudas en APIs públicas.

### 19.1.4. Retención y derecho de supresión
- **Retención declarada**: `AuthInferenceLog` puede crecer sin límite. **Política propuesta**: purga
  automática (p. ej. 90 días) y anonimización/agregación para métricas.
- **Derecho de borrado**: al eliminar un usuario deben borrarse en cascada su `UserProfile`, su
  modelo `.joblib` y sus `AuthInferenceLog` (el FK usa `ON DELETE CASCADE`). Debe documentarse y
  probarse.

### 19.1.5. Transparencia y explicabilidad
- Al usuario se le muestra **score, decisión y latencia** (§6.2), no un "no aprobado" opaco.
- El umbral (`ML_DECISION_THRESHOLD`) es explícito y documentado (§10), y por tanto auditable.
- **Límite**: el score de `IsolationForest` no es "explicable" en términos de "por qué este intento
  falló". Trabajo pendiente: exponer **qué features se desviaron** respecto a la media del usuario.

### 19.1.6. Equidad (fairness)
- **Riesgo de sesgo**: un patrón de tecleo atípico por **condición motora**, **teclado no estándar**
  o **idioma/distribución distinta** puede aumentar el FRR (rechazos legítimos). El sistema podría
  penalizar sistemáticamente a ciertos grupos.
- **Mitigación propuesta**: (a) entrenamiento con muestras suficientes y representativas del propio
  usuario; (b) calibración de umbral por usuario; (c) opción de **re-entrenar** si hay rechazos
  repetidos; (d) monitoreo de disparidad de FRR entre grupos de dispositivos.
- Se declara como **brecha abierta**: no se realizaron mediciones de disparidad.

### 19.1.7. Gobernanza de datos
Responsabilidades propuestas (a definir en despliegue real): quién administra el servicio ML, quién
accede a los modelos y logs, base legal del tratamiento, contrato de encargado del tratamiento si
aplica, y procedimiento de notificación de brechas.

---

## 19.2. Perspectiva social (adopción, dinámicas comunitarias, efectos colectivos)

### 19.2.1. Adopción organizacional
¿Por qué una organización integraría autenticación conductual? Porque el **MFA puntual** protege el
login pero no la **sesión**. Un atacante con la contraseña (phishing, filtración) entra en una sesión
autenticada; la verificación continua detecta el cambio de comportamiento. La adopción es atractiva
en banca, administración y soporte, donde el fraude por cuenta robada es costoso.

**Barreras de adopción** (reconocidas): fricción de falsos rechazos, necesidad de onboarding
(entrenamiento del modelo), cumplimiento normativo y confianza del usuario en una tecnología que
"mide cómo escribes".

### 19.2.2. Dinámicas comunitarias
- En **equipos que comparten estaciones** (kioscos, turnos), la biometría conductual distingue
  operadores aunque compartan contraseña de turno.
- Puede generar **tensión** si se percibe como vigilancia; por eso importa la comunicación (qué se
  captura y para qué) y el principio de minimización.

### 19.2.3. Efectos colectivos
- **Positivos**: reducción del fraude de cuenta robada, menor dependencia de contraseñas complejas.
- **Negativos potenciales**: si el umbral es muy estricto, colectivos con patrones atípicos sufren
  rechazos sistemáticos → exclusión. La política de umbral es una decisión con efecto colectivo, no
  solo técnico.

---

## 19.3. Escenarios de aplicación, transferencia y guía de validación contextual

La rúbrica señala (Pro5, Rel3) la falta de pruebas con tareas reales de oficina. Se **declara como
limitación** y se documenta el **protocolo necesario** para cerrarla:

### 19.3.1. Escenarios concretos
1. **Banca en línea**: verificación continua durante transferencias; anomalía → paso a MFA.
2. **Panel administrativo**: detectar toma de control de sesión tras el login.
3. **Soporte / atención al cliente**: detectar que quien atiende no es el titular de la cuenta.
4. **Puesto de trabajo compartido**: identificación del operador real por comportamiento.

### 19.3.2. Guía de validación contextual (protocolo propuesto, no ejecutado)
Para cerrar la brecha de «tareas reales», se propone un estudio con:
- **Sesiones reales** (escribir correos, documentos) para medir estabilidad del patrón en
  condiciones naturales, no solo con la contraseña objetivo.
- **Distintos dispositivos** (teclado mecánico/membrana/táctil) y **distribuciones** lingüísticas.
- Métricas: FRR por tarea, tasa de molestias percibidas (usabilidad), y latencia percibida.
- Grupos de control para medir **disparidad** de FRR (equidad).

Este protocolo se declara como trabajo futuro; su ausencia explica por qué algunas puntuaciones de
«contexto real» no pueden ser plenamente demostradas en este alcance.

---

## 19.4. Perspectiva cultural (adaptabilidad, lenguaje, apropiación)

- **Contraseña fija del dataset CMU** (`.tie5Roanl`): es **anglocéntrica** y con distribución QWERTY
  estadounidense. Un despliegue real requiere contraseñas/identificadores por contexto y soportar
  **AZERTY**, teclados latinoamericanos y layouts alternativos — los tiempos H/DD/UD cambian según
  el layout, no solo según la persona.
- **Idioma**: el esquema de features no depende del idioma per se, pero la elección de contraseña y
  los patrones de tecleo sí. Se documenta como limitación (Cob6).
- **Apropiación**: la relación de las personas con un sistema que "mide cómo escriben" varía
  culturalmente. Sin estudio de apropiación, se declara la brecha.

---

## 19.5. Perspectiva humana (experiencia, autonomía, decisión)

- **Autonomía frente a errores**: el sistema debe **sugerir**, no bloquear irreversiblemente en
  operaciones críticas. Cuando la decisión es ANOMALY, lo correcto es escalar a un segundo factor
  (MFA), no cerrar la cuenta. Se documenta como principio de diseño (decisión humana en el bucle).
- **Re-entrenamiento**: si hay rechazos repetidos por cambio de hábito (nuevo teclado, lesión), el
  usuario debe poder **volver a entrenar** su modelo. En el sistema, la pantalla de entrenamiento
  sobrescribe el modelo propio, habilitando esta corrección.
- **Recuperación tras pérdida de modelo** (plan gratuito): ver §18.3 (manejo propuesto).
- **Brecha**: no hay estudio de experiencia de usuario (satisfacción, frustración ante FRR). Se
  declara.

---

## 19.6. Impacto potencial (Rel5)

| Ámbito | Impacto estimado | Riesgo si falla |
|---|---|---|
| Organizaciones (banca, soporte) | Reducción de fraude por sesión robada | FRR alto → fricción y llamadas a soporte |
| PYMEs | Autenticación reforzada con menos fricción que MFA | Requiere onboarding y tolerancia a falsos rechazos |
| Sector público | Protección de trámites con identidad débil | Sesgo contra usuarios con acceso atípico |
| Usuarios con accesibilidad | Adopción más fácil que hardware biométrico dedicado | Riesgo de exclusión si no se calibra por usuario |

> Las estimaciones son **cualitativas y declaradas como tales**; no se presentan como estudio
> empírico de impacto.

---

## 19.7. Plan de acción para cerrar brechas abiertas

1. **Consentimiento y privacidad**: pantalla de consentimiento + política de una página.
2. **Retención**: purga configurable de `AuthInferenceLog` y cifrado en reposo.
3. **Explicabilidad**: mostrar features desviadas respecto al perfil del usuario.
4. **Equidad**: medir disparidad de FRR por dispositivo/idioma; calibrar umbral por usuario.
5. **Validación contextual**: ejecutar el protocolo de §19.3.2.
6. **Usabilidad**: estudio de experiencia con usuarios reales.
7. **Degradación elegante** (Uni3): modo local/ligero para conectividad limitada.

---

## 19.8. Transferibilidad interdisciplinar (Uni5)

Para que investigadores de HCI, ergonomía o derecho puedan interpretar el sistema:
- **Definición llana de métricas**: FAR = «cuántas veces se deja pasar a un impostor»; FRR =
  «cuántas veces se rechaza al dueño»; EER = «punto donde ambos errores se igualan».
- **Esquema de datos reutilizable**: features temporales documentadas (§4, §15) con nombres y
  unidades estables.
- **Contratos de API abiertos** (HTTP/JSON) que permiten reutilizar el servicio ML desde otros
  frontales o estudios.

---

## 19.9. Nota final de honestidad académica

Este documento **no convierte en resueltas** las brechas éticas, sociales y de validación real: las
**declara**, describe su naturaleza y propone cómo medirlas. La actividad realizada (multimodalidad
tecleo+cursor, benchmark EER, pruebas automatizadas, documentación de perspectivas) mejora la
cobertura, pero el sistema sigue siendo un **prototipo** cuya solidez empírica en contextos reales
está pendiente de los estudios descritos en §19.3.2 y §19.7.
