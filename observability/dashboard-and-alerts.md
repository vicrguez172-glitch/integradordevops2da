# Dashboard y alertas de OpenObserve

## Estado actual en EC2

- El Collector está estable y OpenObserve acepta logs, métricas y trazas OTLP con HTTP 200.
- El dashboard `Operación CompraJuegos` está guardado en OpenObserve. Se duplicó la plantilla **Host Metrics** y se corrigió su panel de CPU para usar la métrica disponible `system_cpu_utilization`.
- Se verificaron datos de CPU, RAM y tráfico de red en el dashboard. Los paneles de carga y disco de la plantilla no tienen datos con la configuración actual.
- EC2 no expone sensores térmicos en `sysfs/hwmon`; no se puede medir ni mostrar temperatura real en °C.
- Todavía no hay una alerta guardada. OpenObserve rechazó la creación porque requiere al menos un destino de notificación o workflow. La configuración opcional de Gmail ya está preparada en Compose, pero no estará activa en EC2 hasta publicar el cambio y agregar los valores al `.env` de ese servidor.

## Preparación

1. Inicia los servicios y entra a OpenObserve con el correo y la contraseña de `.env`.
2. Genera tráfico en la tienda. Las métricas OTLP usan el stream `default`; los resultados del workflow se envían al stream `ci_cd`.
3. En OpenObserve abre **Metrics** y confirma los nombres/labels disponibles. El mapeo final de nombres y atributos OTLP depende de la versión de OpenObserve; estas expresiones PromQL son consultas iniciales basadas en las métricas emitidas por OTel Collector.

## Dashboard

El dashboard ya existe en EC2. Para recrearlo en otra instancia, duplica la plantilla **Host Metrics** desde **Dashboards** y renómbrala `Operación CompraJuegos`. La consulta validada para el panel de CPU es:

```promql
100 * avg by (host_name) (
  sum by (host_name, cpu) (
    system_cpu_utilization{state!="idle"}
  )
)
```

La métrica y consulta se validaron en Metrics Explorer y en el panel. Para RAM y red, usa los paneles de la plantilla **Host Metrics**, que ya muestran datos de esta instancia. No agregues `hw.temperature` como si tuviera datos: esta EC2 no tiene sensores térmicos.

Si un panel no devuelve datos, elige el stream de métricas correspondiente y confirma el nombre de la métrica y sus labels en **Metrics → Explorer**. CPU utilization y memory utilization se habilitan explícitamente en `observability/otel-collector.yaml`.

Para paneles de aplicación, cambia a **Logs**, stream `default`, y usa SQL:

```sql
SELECT histogram(_timestamp) AS x_axis_1,
       avg(response_time_ms) AS y_axis_1
FROM "default"
WHERE logger = 'compra_juegos' AND message = 'HTTP request'
GROUP BY x_axis_1
ORDER BY x_axis_1
```

Configura un panel de líneas con `x_axis_1` como eje X y `y_axis_1` como eje Y. Para errores HTTP:

```sql
SELECT histogram(_timestamp) AS x_axis_1,
       count(*) AS y_axis_1
FROM "default"
WHERE logger = 'compra_juegos'
  AND message = 'HTTP request'
  AND status_code >= 500
GROUP BY x_axis_1
ORDER BY x_axis_1
```

Para observar resultados de CI/CD, selecciona **Logs**, stream `ci_cd`, y consulta:

```sql
SELECT _timestamp, event_type, status, commit_sha, branch, actor, run_id
FROM "ci_cd"
ORDER BY _timestamp DESC
```

## Alertas

Para habilitar alertas por correo con Gmail:

1. Activa la verificación en dos pasos de la cuenta y crea una contraseña de aplicación para OpenObserve. No uses la contraseña normal de Google.
2. Configura estas variables en el archivo `.env` del servidor EC2; no las pongas en GitHub ni las compartas por chat:

   ```dotenv
   ZO_SMTP_ENABLED=true
   ZO_SMTP_HOST=smtp.gmail.com
   ZO_SMTP_PORT=587
   ZO_SMTP_USER_NAME=tu-correo@gmail.com
   ZO_SMTP_PASSWORD=tu-contraseña-de-aplicación
   ZO_SMTP_FROM_EMAIL=tu-correo@gmail.com
   ZO_SMTP_ENCRYPTION=starttls
   ```

3. Despliega la actualización de `compose.yaml` y recrea únicamente OpenObserve para que cargue las variables. El volumen `openobserve-data` conserva dashboards y datos.
4. En OpenObserve, abre **Alerts → Destinations**, crea un destino de tipo **Email** y agrega la dirección que recibirá las alertas. Usa la opción de prueba para confirmar la entrega.

La API requiere al menos un destino o workflow; sin SMTP no hay una alerta activa.

Después de agregar el destino, se recomienda una alerta programada de CPU con esta consulta:

```promql
100 * avg by (host_name) (
  sum by (host_name, cpu) (
    system_cpu_utilization{state!="idle"}
  )
)
```

Configura la condición `value > 80`, una ventana de 5 minutos y evaluación cada minuto; selecciona el destino recién creado. No guardes URLs privadas, tokens ni credenciales en el repositorio.

## Guardar y reproducir un dashboard

Cuando termines de construir el dashboard en la interfaz, expórtalo como JSON y guárdalo de forma segura fuera del repositorio si contiene datos de la instancia. OpenObserve documenta la importación de dashboards desde **Dashboards → Import → Custom**; Terraform también puede gestionar dashboards usando un JSON exportado por la misma versión de OpenObserve.

El dashboard ya está guardado en la instancia EC2. La alerta queda pendiente hasta configurar un destino válido.

## Referencias

- [OpenTelemetry Collector: CPU scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/cpuscraper/documentation.md)
- [OpenTelemetry Collector: memory scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/documentation.md)
- [OpenTelemetry Collector: network scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/networkscraper/documentation.md)
- [OpenTelemetry Collector: hardware scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/hardwarescraper/documentation.md)
- [OpenObserve Metrics Explorer](https://openobserve.ai/docs/user-guide/data-exploration/metrics/explorer/)
- [OpenObserve OTLP ingestion](https://openobserve.ai/docs/ingestion/logs/otlp/)
- [OpenObserve dashboards](https://openobserve.ai/docs/user-guide/analytics/dashboards/dashboards-in-openobserve/)
