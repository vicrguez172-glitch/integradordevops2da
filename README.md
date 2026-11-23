# NIVEL — tienda de videojuegos

Proyecto académico de compra simulada de videojuegos con Angular, FastAPI, SQLite, pruebas automatizadas y una configuración de despliegue/observabilidad para EC2.

## Funcionalidad

- Catálogo público con búsqueda y filtro por categoría.
- Registro, inicio y cierre de sesión.
- Carrito y compra simulada con inventario transaccional e historial de pedidos.
- Panel administrativo para crear clientes y administradores, editar nombre/correo/rol y cambiar contraseñas; las contraseñas requieren al menos 8 caracteres y se pueden mostrar u ocultar.
- Baja lógica y reactivación de usuarios: las cuentas desactivadas no pueden iniciar sesión y conservan sus compras. Se protege al último administrador activo.
- Búsqueda y filtros de usuarios por nombre/correo, rol y estado; el inventario de juegos se filtra por título, categoría y plataforma.
- CRUD de juegos e inventario desde el panel administrativo.
- Interfaz basada en Bootstrap 5, con tema oscuro/morado, transiciones marcadas y animaciones de entrada al desplazarse; respeta la preferencia de movimiento reducido.
- Los avisos, errores y confirmaciones de eliminación se muestran en modales propios; los errores de validación indican los campos que deben revisarse.
- API en `backend/app/main.py`; documentación interactiva al iniciar la API en `/docs`.

No se conecta a un procesador de pagos ni realiza cargos reales.

## Desarrollo local

Requisitos: Node.js 22, Python 3.10 o superior y npm.

### 1. Iniciar la API

En una terminal de PowerShell:

```powershell
cd backend
python -m pip install -r requirements.txt
$env:SECRET_KEY = "local-development-key-change-before-deploy"
$env:BOOTSTRAP_ADMIN_EMAIL = "admin@example.com"
$env:BOOTSTRAP_ADMIN_PASSWORD = "local-admin-change-this"
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

La base de datos se crea en `backend/data/compra_juegos.db`. El admin inicial solo se crea si la cuenta no existe; cambiar el password en las variables de entorno después no rota la clave guardada en SQLite.

### 2. Iniciar Angular

En otra terminal, desde la raíz del proyecto:

```powershell
npm ci
npm start
```

Abre <http://localhost:4200>. El proxy de desarrollo envía `/api` a `http://127.0.0.1:8000`.

### 3. Ejecutar pruebas

```powershell
cd backend
python -m pytest -q
```

Con la API y el frontend activos, abre otra terminal:

```powershell
cd e2e
python -m pip install -r requirements.txt
python -m playwright install chromium
$env:E2E_BASE_URL = "http://127.0.0.1:4200"
$env:E2E_ADMIN_EMAIL = "admin@example.com"
$env:E2E_ADMIN_PASSWORD = "local-admin-change-this"
python -m pytest -q -s test_store.py
python -m pytest -q -s -n 4 test_ui_matrix.py
```

La suite backend cubre las 15 operaciones HTTP de la API, sus permisos y los principales errores/validaciones. Playwright ejecuta cinco recorridos completos y una matriz funcional de 1,700 casos: navegación por header/footer, carrito, login/registro, validación de formularios CRUD y filtros representativos. En Docker, los cinco recorridos pasaron en 26.24 segundos y la matriz con cuatro workers en 478.43 segundos. GitHub Actions ejecuta esos mismos comandos con un timeout de 15 minutos. El reporte de validación está en [runtime-validation-report.md](runtime-validation-report.md).

Playwright registra para cada petición API el timestamp UTC, endpoint, método, código HTTP y duración en milisegundos. Esos datos se imprimen como JSON y se agregan al reporte JUnit.

## Levantar los contenedores

Instala Docker Desktop o Docker Engine con Docker Compose. Copia el ejemplo y reemplaza las claves antes de iniciar:

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up --build -d
```

- Tienda: <http://localhost:8080>
- API: disponible a través de `/api` en el mismo host.
- OpenObserve: <http://localhost:5080>
- El correo y password de OpenObserve son los configurados en `.env`.

`OO_BASIC_AUTH` debe ser Base64 de `ZO_ROOT_USER_EMAIL:ZO_ROOT_USER_PASSWORD`. Para generarlo en PowerShell:

```powershell
$pair = "correo-configurado:password-configurado"
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pair))
```

Pega el resultado en `OO_BASIC_AUTH` en `.env`. Si cambias el usuario o password de OpenObserve, actualiza ambos valores y vuelve a generar esta cadena. No uses las credenciales de ejemplo en un servidor público ni guardes secretos reales en Git.

Detener los servicios sin borrar datos: `docker compose down`. Los volúmenes `store-data` y `openobserve-data` conservan la base SQLite y los datos de monitoreo. `docker compose down --volumes` los elimina.

Para validar solo la imagen de la aplicación sin OpenObserve:

```powershell
docker compose -f compose.e2e.yaml up --build -d
```

El entorno de pruebas usa credenciales fijas únicamente para el contenedor e2e y no se debe desplegar en producción.

## Observabilidad

La API envía logs estructurados, trazas FastAPI/SQLAlchemy y métricas HTTP OTLP al OpenTelemetry Collector. Las métricas HTTP incluyen ruta, método, status code, contador y duración. El Collector envía señales a OpenObserve por OTLP/HTTP.

El Collector también consulta cada 30 segundos métricas de host Linux para CPU, memoria, red y sensores térmicos disponibles. La temperatura depende de que EC2 exponga un sensor en `sysfs/hwmon`; algunas instancias no exponen temperatura y en ese caso la métrica no aparecerá. Los contenedores de Windows/Docker Desktop no representan necesariamente los sensores del host Windows.

Configurar y guardar dashboards y alertas en la interfaz de OpenObserve. La dirección predeterminada del host OpenObserve en Compose es el puerto 5080; protégela con TLS/autenticación y restringe su acceso de red en EC2.

## GitHub Actions y EC2

`.github/workflows/ci-cd.yml` ejecuta pytest, build de Angular y Playwright en push/PR hacia `main`. Un push a `main` solo llega al trabajo de despliegue si todo el trabajo de pruebas termina exitosamente. Se registra el resultado del pipeline y el resultado del despliegue en el stream `ci_cd` de OpenObserve mediante la API HTTP/JSON `POST /api/{org}/{stream}/_json`.

Configura en GitHub:

**Secrets requeridos**

- `OPENOBSERVE_URL`: base URL accesible desde GitHub Actions, por ejemplo `https://observabilidad.tudominio`.
- `OPENOBSERVE_EMAIL`, `OPENOBSERVE_PASSWORD`: cuenta de OpenObserve con permiso de escritura en el stream configurado.
- `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`: host/IP, usuario SSH y clave privada para EC2.
- `EC2_KNOWN_HOSTS`: línea `known_hosts` verificada para ese servidor. No desactives la verificación SSH.

**Variables opcionales**

- `OPENOBSERVE_ORG` (predeterminado `default`).
- `OPENOBSERVE_STREAM` (predeterminado `ci_cd`).
- `EC2_APP_DIR` (predeterminado `/opt/compra-juegos`).

Antes del primer push a `main`, prepara EC2 con Docker/Compose, crea el directorio de despliegue y coloca allí un `.env` seguro con `SECRET_KEY`, credenciales de admin y OpenObserve. El usuario SSH debe poder escribir en el directorio y ejecutar Docker Compose. El workflow conserva ese `.env` y los volúmenes fuera de las carpetas de release.

La aplicación se publica inicialmente en el puerto 8080 y OpenObserve en 5080. Configura los security groups para exponer solo lo necesario; restringe SSH a un origen de confianza. Usa HTTPS/proxy inverso para acceso público y un runner de GitHub con salida SSH estable si la red impide acceso seguro desde runners hospedados. El despliegue real requiere un EC2, secretos válidos y un OpenObserve alcanzable; no se incluyen ni deben añadirse credenciales al repositorio.

## Reporte académico

El borrador editable del reporte formal está en [REPORTE_PROYECTO_COMPRA_JUEGOS.docx](REPORTE_PROYECTO_COMPRA_JUEGOS.docx). Completa los campos entre corchetes y agrega capturas y URLs reales después de validar el despliegue. La guía para crear los paneles y alertas está en [observability/dashboard-and-alerts.md](observability/dashboard-and-alerts.md).
