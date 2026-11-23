import logging
import os
import time
from datetime import datetime, timezone

from opentelemetry import _logs as logs
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


logger_provider: LoggerProvider | None = None


def configure_telemetry() -> None:
    global logger_provider
    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "compra-juegos-api"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        traces = TracerProvider(resource=resource)
        traces.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(traces)
        reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
        logs.set_logger_provider(logger_provider)


configure_telemetry()
meter = metrics.get_meter("compra-juegos.http")
request_count = meter.create_counter("http.server.request.count", unit="{request}")
request_duration = meter.create_histogram("http.server.request.duration", unit="s")


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("http_method", "http_route", "status_code", "response_time_ms"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    if logger_provider is not None:
        root.addHandler(LoggingHandler(level=logging.INFO, logger_provider=logger_provider))
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())


def observe_request(method: str, route: str, status_code: int, elapsed: float) -> None:
    attributes = {
        "http.request.method": method,
        "http.route": route,
        "http.response.status_code": status_code,
    }
    request_count.add(1, attributes)
    request_duration.record(elapsed, attributes)
