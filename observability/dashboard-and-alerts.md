# Dashboard y alertas de OpenObserve

## Preparación

1. Inicia los servicios y entra a OpenObserve con el correo y la contraseña de `.env`.
2. Genera tráfico en la tienda. Las métricas OTLP usan el stream `default`; los resultados del workflow se envían al stream `ci_cd`.
3. En OpenObserve abre **Metrics** y confirma los nombres/labels disponibles. El mapeo final de nombres y atributos OTLP depende de la versión de OpenObserve; estas expresiones PromQL son consultas iniciales basadas en las métricas emitidas por OTel Collector.

## Crear el dashboard

En **Metrics → Explorer**, consulta cada métrica, selecciona **Visualize** y usa **Add to Dashboard** para crear un dashboard llamado `Operación CompraJuegos`. Guarda los paneles y activa una actualización periódica si está disponible.

| Panel | Consulta inicial | Unidad sugerida |
|---|---|---|
| CPU utilizada | `avg(sum by (cpu) (system.cpu.utilization{state!="idle"})) * 100` | % |
| Memoria utilizada | `avg(system.memory.utilization) * 100` | % |
| Tráfico de red | `sum by (device, direction) (rate(system.network.io[5m])) / 1048576` | MiB/s |
| Temperatura | `hw.temperature` | °C |

Si un panel no devuelve datos, elige el stream de métricas `default`, confirma primero el nombre de la métrica y sus labels en **Metrics → Explorer**, y ajusta la consulta a los datos que haya recibido esa instancia. CPU utilization y memory utilization se habilitan explícitamente en `observability/otel-collector.yaml`. La lectura de `hw.temperature` solo funcionará en Linux si EC2 expone sensores `sysfs/hwmon`.

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

En **Reliability → Alerts**, crea una alerta de logs con este SQL:

```sql
SELECT count(*) AS errors
FROM "default"
WHERE logger = 'compra_juegos'
  AND message = 'HTTP request'
  AND status_code >= 500
```

Configura la condición para que `errors > 0` durante la ventana deseada y elige una frecuencia/silencio razonables para la demostración. Crea primero un destino de notificación (correo o webhook) en OpenObserve y selecciónalo en la alerta. Las credenciales y destinos de notificación no se incluyen en el repositorio.

## Guardar y reproducir un dashboard

Cuando termines de construir el dashboard en la interfaz, expórtalo como JSON y guárdalo de forma segura fuera del repositorio si contiene datos de la instancia. OpenObserve documenta la importación de dashboards desde **Dashboards → Import → Custom**; Terraform también puede gestionar dashboards usando un JSON exportado por la misma versión de OpenObserve.

La creación/importación del dashboard y el destino/alerta requieren una instancia activa y acceso a la UI; no se pudieron validar en esta sesión porque Docker Desktop no tiene iniciado su daemon.

## Referencias

- [OpenTelemetry Collector: CPU scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/cpuscraper/documentation.md)
- [OpenTelemetry Collector: memory scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/memoryscraper/documentation.md)
- [OpenTelemetry Collector: network scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/networkscraper/documentation.md)
- [OpenTelemetry Collector: hardware scraper](https://github.com/open-telemetry/opentelemetry-collector-contrib/blob/main/receiver/hostmetricsreceiver/internal/scraper/hardwarescraper/documentation.md)
- [OpenObserve Metrics Explorer](https://openobserve.ai/docs/user-guide/data-exploration/metrics/explorer/)
- [OpenObserve OTLP ingestion](https://openobserve.ai/docs/ingestion/logs/otlp/)
- [OpenObserve dashboards](https://openobserve.ai/docs/user-guide/analytics/dashboards/dashboards-in-openobserve/)
