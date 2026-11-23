# Contexto de continuidad — Proyecto Parcial 2: Compra de juegos

Usa este documento como contexto inicial si el trabajo continúa en otra sesión. Es un resumen del PDF `Proyecto parcial2 GestionProcesoDesarrollo.pdf` y de los requisitos adicionales proporcionados por el estudiante. No representa una implementación de esos requisitos.

## Información de la entrega

- Proyecto: sistema básico para compra de videojuegos.
- Estudiante: Emmanuel Martinez Hernandez.
- Fecha de entrega indicada: 26 de noviembre.
- Valor: 100 puntos; cada omisión resta 4 puntos y la entrega tardía resta 20 puntos.
- Requisitos mencionados fuera del PDF: Login y CRUD de usuarios.
- Revisión presencial en clase.

## Requisitos del PDF

El documento se titula “Arquitectura de Entrega Continua (CI/CD), Pruebas Automatizadas y Observabilidad”.

1. **Pruebas automatizadas (RF-01):** pruebas integrales para frontend y backend con herramientas usadas en clase; enumera pytest, Jest y Playwright.
2. **CI/CD (RF-02):** GitHub Actions debe probar antes de desplegar; el auto-deploy solo ocurre si pasan todas las pruebas.
3. **Trazabilidad del pipeline (RF-03):** enviar a OpenObserve por HTTP/JSON resultados de pruebas (éxito o fallo), commit, rama, usuario ejecutor y eventos de despliegue completados en EC2.
4. **Observabilidad de la aplicación (RF-04):** instrumentar con OpenTelemetry y enviar a OpenObserve:
   - Logs estructurados de operación y excepciones.
   - Métricas por endpoint: latencia, solicitudes por segundo y tasas de error HTTP, con código de estado y timestamp.
   - Trazas distribuidas del ciclo de cada solicitud, incluidos servicios y consultas a la base de datos.
5. **Infraestructura (RF-05):** monitorear recursos del servidor EC2 en OpenObserve mediante un dashboard.
6. **Tableros y alertas (RF-06):** mostrar dashboards y alertas operativas.
7. **Aceptación de fallo:** un commit que introduzca un error debe fallar en Playwright, registrar el incidente en OpenObserve y no conectarse por SSH a EC2.
8. **Aceptación de éxito:** un commit válido debe aprobar la suite, actualizar los contenedores en EC2 y registrar el despliegue en OpenObserve.
9. **Aceptación de observabilidad:** OpenObserve debe mostrar eventos del pipeline, trazas HTTP y gráficas de CPU, ancho de banda, temperatura y memoria RAM de EC2.
10. **Reporte formal:** texto justificado, introducción, portada institucional, imágenes/figuras enumeradas, enlaces al repositorio y servidor, y credenciales del sistema y OpenObserve.

## Requisitos adicionales indicados por el estudiante

- Frontend en **Angular** si el documento no especifica tecnología.
- Backend probado con **pytest**.
- Pruebas frontend con **Playwright usando Python**.
- Base de datos **SQLite**.
- Pipeline con pruebas automatizadas.
- Capturar en las pruebas o telemetría: tiempo de respuesta, endpoint y tipo/método HTTP, código de estado y timestamp.
- Desplegar en AWS EC2.
- Usar OpenObserve para monitorear CPU, RAM, temperatura y ancho de banda; el estudiante confirmó que no requiere añadir Prometheus ni Grafana.
- Implementar Login y CRUD de usuarios.
- Se mencionó “Alpine”, pero no se recuerda el uso previsto.

## Estado actual de la carpeta

La carpeta `compra-juegos` contiene la aplicación Angular CLI 20.3.16 y un backend nuevo en `backend/`.

### Parte terminada: backend inicial

- API FastAPI con SQLite/SQLAlchemy: registro e inicio de sesión, perfil, usuarios (CRUD de admin), catálogo de juegos (CRUD de admin) y compras simuladas con validación y decremento transaccional de inventario.
- Contraseñas con hash scrypt; tokens firmados con vencimiento; la cuenta inicial de admin se configura con variables de entorno.
- El catálogo incluye juegos de demostración. La compra confirma una orden local; no integra procesamiento de pagos.
- Logs JSON de solicitudes con timestamp, método, ruta, status code y duración; métricas OpenTelemetry de conteo/duración por endpoint y trazas FastAPI/SQLAlchemy cuando se configura el exportador OTLP.
- Pruebas API en `backend/tests/`: `4 passed` usando `python -m pytest -q` (Python 3.10 local). Las dependencias se declaran en `backend/requirements.txt`.

### Parte terminada: tienda Angular inicial

- Se reemplazó el placeholder por una tienda en español con catálogo, búsqueda, filtro por categoría, login/registro, carrito persistente en el navegador, confirmación de compra simulada, historial personal y panel de admin para CRUD de usuarios y juegos.
- El CRUD de usuarios permite registrar clientes o administradores, actualizar nombre/correo/rol y cambiar la contraseña de manera opcional; la contraseña requiere al menos 8 caracteres y tiene control mostrar/ocultar. La baja de usuario es lógica: impide autenticación, conserva compras y se puede revertir reactivando la cuenta. Se impide desactivar o degradar al último administrador activo.
- El panel permite buscar usuarios por nombre/correo y filtrar por rol/estado; el inventario de juegos se filtra por título, categoría y plataforma. El CRUD de juegos permite crear, consultar, editar y eliminar productos.
- Se amplió el footer con navegación a tienda, carrito y cuenta/administración, nota de compra académica y acceso para volver arriba. El layout mantiene el footer en el fondo en páginas cortas.
- Los mensajes de éxito/error y las confirmaciones de eliminación usan modales propios; se eliminaron alertas nativas y banners Bootstrap. Las respuestas de validación FastAPI se formatean por campo para evitar mostrar `[object Object]`.
- Se instaló Bootstrap 5 y se aplicó tema oscuro con acentos morados. Login/registro usan formularios Bootstrap; el cierre de sesión tiene estilo rojo con icono. Se agregaron animaciones de scroll, elevación de tarjetas y microinteracciones respetando `prefers-reduced-motion`.
- Se corrigió el icono SVG de búsqueda, que por no tener dimensiones se expandía como una gran mancha negra debajo del título del catálogo.
- El frontend consume la API por `/api`; `proxy.conf.json` enruta a `http://127.0.0.1:8000` para desarrollo local.
- `npm run build` pasa (Angular CLI 20.3.16, Node 22.22.0). El bundle inicial actual es de 619.46 kB, por encima de la advertencia configurada de 500 kB, pero debajo del límite de error de 1 MB. La instalación de npm indicó 16 vulnerabilidades moderadas en el árbol de dependencias; están pendientes de revisión.
- Las compras son simuladas: no se integra un proveedor de pago.

### Parte terminada: pruebas Playwright Python

- `e2e/test_store.py` valida cinco recorridos: login inválido, navegación header/footer, carrito y bloqueo de checkout anónimo, registro/compra/historial y administración de usuarios/juegos con persistencia.
- `e2e/test_ui_matrix.py` genera exactamente 1,700 casos funcionales: 100 de navegación en viewports distintos, 480 de acciones/cantidades del carrito, 320 de login/registro, 350 de validación de usuarios, 430 de validación de juegos y 20 de búsqueda/filtro representativos.
- `e2e/conftest.py` captura por solicitud API `timestamp`, `endpoint`, `method`, `status_code` y `response_time_ms`; imprime JSON y lo adjunta como propiedad JUnit para el pipeline.
- Validación más reciente: en Docker, `5 passed` en recorridos completos (26.24 s) y `1,700 passed` en la matriz con cuatro workers (478.43 s); `pytest --collect-only` confirmó 1,705 pruebas totales. Playwright 1.65.2/Chromium. GitHub Actions ejecuta cuatro workers y tiene timeout de 15 minutos.
- Durante la validación se corrigió el registro de locale `es-MX` para evitar un error Angular en CurrencyPipe.

### Parte implementada: CI/CD y publicación de eventos

- `.github/workflows/ci-cd.yml` contiene trabajos para pytest, build de Angular y Playwright. El deploy SSH está condicionado al éxito del trabajo de pruebas y solo corre en push a `main`.
- `compose.e2e.yaml` proporciona una pila de prueba sin OpenObserve ni credenciales productivas.
- `scripts/report_pipeline.py` envía eventos HTTP/JSON a OpenObserve con status, commit, rama, actor, workflow y run ID. Se verificó localmente contra un servidor HTTP simulado, incluyendo URL y Basic Auth.
- Los pasos de reporte de tests/despliegue requieren configurar secretos de OpenObserve en GitHub. El workflow de deploy requiere además SSH key, host verificado, usuario EC2 y directorio de despliegue.

### Estado de implementación

- Backend y pytest: terminados. Suite actual: `20 passed`; `backend/tests/test_endpoint_coverage.py` cubre las 15 operaciones HTTP de la API, incluyendo permisos, errores, filtros, persistencia, inventario y compras.
- Tienda Angular y build de producción: terminados.
- Pruebas end-to-end con Playwright Python: `1,700` casos funcionales y cinco recorridos completos pasaron localmente. La matriz cubre navegación, carrito, autenticación, formularios CRUD y filtros; no concentra los casos en combinaciones repetidas de búsquedas. El build de Angular pasa; su bundle inicial (619.46 kB) supera el presupuesto de advertencia de 500 kB.
- Dockerfiles Alpine, Compose y configuración OTLP/hostmetrics para OpenObserve: escritos. Los archivos Compose pasan validación y la pila `compose.e2e.yaml` se construyó y arrancó localmente; API healthy y UI E2E completa aprobada en contenedores. El stack E2E temporal se apagó tras validar. Falta iniciar/validar el Compose de producción con OpenObserve y, después, EC2.
- Pipeline: implementado en archivos, falta validarlo en GitHub Actions después de subir el proyecto.
- Hostmetrics incluye CPU, RAM, red y temperatura; CPU y memoria en porcentaje están habilitados explícitamente. Las métricas se exportan al stream `default`. La temperatura depende de sensores Linux `sysfs/hwmon`, que podrían no estar expuestos por el tipo de EC2.
- Se agregó `observability/dashboard-and-alerts.md` con consultas iniciales PromQL/SQL y pasos de UI para crear dashboard y alerta. El mapeo exacto OTLP a labels/stream se debe confirmar en Metrics Explorer de la instancia. El dashboard/alerta aún no se crearon ni comprobaron en una instancia OpenObserve activa.
- Se generó `REPORTE_PROYECTO_COMPRA_JUEGOS.docx` con portada institucional editable, arquitectura, funcionalidades, pruebas, CI/CD, observabilidad, riesgos y referencias. Falta completar campos entre corchetes, agregar capturas reales y completar URLs después del despliegue.
- No se ha desplegado a EC2; se necesitan credenciales/secretos AWS y acceso a un repositorio GitHub para validar la conexión real.
- Última verificación local: backend `20 passed`; Angular build exitoso con advertencia no bloqueante del bundle (619.46 kB frente al presupuesto de 500 kB); Docker E2E `5 + 1,700 passed`. No se hizo deploy a EC2. El remoto GitHub indicado está vacío, pero la cuenta CLI conectada solo tiene permiso READ, así que todavía no se puede inicializar/subir el repositorio. Tampoco se verificaron los secrets de Actions: la consulta devolvió HTTP 403 por falta de permisos. El reporte detallado está en `runtime-validation-report.md`.

## Diferencias y puntos por confirmar

- El PDF no exige Angular ni SQLite; son decisiones/añadidos del estudiante, no requisitos textuales del PDF. El estudiante confirmó OpenObserve como plataforma de observabilidad y no requiere Prometheus ni Grafana.
- El PDF sí exige OpenTelemetry para logs, métricas **y trazas**, además de latencia, solicitudes por segundo y tasa de errores por endpoint. El requisito adicional de registrar método HTTP, status code y timestamp encaja con esas métricas, pero deberá cubrirse en la instrumentación y en la evidencia de pruebas.
- El PDF pide que los dashboards de infraestructura estén en OpenObserve; el estudiante confirmó que OpenObserve basta y que no se agreguen Prometheus ni Grafana.
- “Alpine” se mencionó en el contexto de simplificar/generalizar los contenedores y reducir recursos. Probablemente se refiere a Alpine Linux como imagen base ligera, no a Alpine.js; verificar compatibilidad al definir los Dockerfiles, ya que el estudiante no recuerda el detalle exacto.
- La temperatura puede no estar disponible como sensor de hardware en una instancia EC2. Antes de prometer esa gráfica hay que verificar una fuente viable para el tipo de instancia/entorno y documentar cualquier limitación.
- El PDF solicita credenciales en el reporte. No guardar contraseñas, tokens, claves SSH ni credenciales reales en este archivo, en el repositorio o en logs; acordar una forma segura de entrega y usar secretos protegidos en GitHub Actions.

## Orientación para continuar

1. Iniciar Docker Desktop y validar build/arranque de la pila; comprobar recepción real de métricas, logs y trazas en OpenObserve.
2. Crear el dashboard y alertas desde la UI siguiendo `observability/dashboard-and-alerts.md`; exportar el JSON y guardar evidencias sin incluir credenciales.
3. Completar el reporte Word: datos institucionales, capturas propias de la aplicación/OpenObserve y enlaces reales después de desplegar.
4. Crear/configurar repositorio GitHub y secretos necesarios; ejecutar el pipeline y validar despliegue condicionado a tests.
5. Configurar EC2 y validar conectividad/monitoreo únicamente después de disponer de credenciales y acceso seguros.
6. Actualizar este contexto al cerrar cada parte, como pidió el estudiante.
