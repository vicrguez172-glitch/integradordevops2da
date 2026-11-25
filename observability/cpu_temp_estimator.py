#!/usr/bin/env python3
"""Publish a synthetic CPU-temperature proxy; this is not a sensor reading."""

import json
import logging
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_CELSIUS = 38.0
CELSIUS_PER_CPU_PERCENT = 0.4
METRIC_NAME = "cpu_temp_estimate_celsius"
METRIC_DESCRIPTION = (
    "Synthetic estimate from CPU utilization; not measured by a temperature sensor."
)
FORMULA = "38 + (cpu_utilization_percent * 0.4)"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
LOGGER = logging.getLogger("cpu-temp-estimator")


def read_cpu_times(stat_path: Path) -> tuple[int, ...]:
    with stat_path.open(encoding="ascii") as stat_file:
        for line in stat_file:
            if line.startswith("cpu "):
                values = tuple(int(value) for value in line.split()[1:])
                if len(values) < 8:
                    raise ValueError("The aggregate CPU line has fewer than 8 counters.")
                return values
    raise ValueError(f"No aggregate CPU counters found in {stat_path}.")


def calculate_cpu_utilization_percent(
    previous: tuple[int, ...], current: tuple[int, ...]
) -> float:
    if len(previous) < 8 or len(current) < 8:
        raise ValueError("CPU counter samples must contain at least 8 values.")

    total_delta = sum(current[:8]) - sum(previous[:8])
    idle_delta = (current[3] + current[4]) - (previous[3] + previous[4])
    busy_delta = total_delta - idle_delta
    if total_delta <= 0 or busy_delta < 0 or busy_delta > total_delta:
        raise ValueError("CPU counter samples do not produce a valid utilization.")
    return busy_delta * 100.0 / total_delta


def estimate_temperature_celsius(cpu_utilization_percent: float) -> float:
    if not 0.0 <= cpu_utilization_percent <= 100.0:
        raise ValueError("CPU utilization must be between 0 and 100 percent.")
    return BASE_CELSIUS + cpu_utilization_percent * CELSIUS_PER_CPU_PERCENT


def build_otlp_payload(
    cpu_utilization_percent: float,
    estimated_temperature_celsius: float,
    timestamp_unix_nano: int | None = None,
) -> dict[str, object]:
    timestamp = time.time_ns() if timestamp_unix_nano is None else timestamp_unix_nano
    attributes = [
        {"key": "estimated", "value": {"stringValue": "true"}},
        {"key": "source", "value": {"stringValue": "cpu_utilization_formula"}},
        {"key": "formula", "value": {"stringValue": FORMULA}},
        {
            "key": "cpu_utilization_percent",
            "value": {"doubleValue": cpu_utilization_percent},
        },
    ]
    return {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": "ec2-cpu-temp-estimator"},
                        }
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {
                            "name": "compra-juegos.cpu-temp-estimator",
                            "version": "1.0.0",
                        },
                        "metrics": [
                            {
                                "name": METRIC_NAME,
                                "description": METRIC_DESCRIPTION,
                                "unit": "Cel",
                                "gauge": {
                                    "dataPoints": [
                                        {
                                            "attributes": attributes,
                                            "timeUnixNano": str(timestamp),
                                            "asDouble": estimated_temperature_celsius,
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            }
        ]
    }


def send_metric(endpoint: str, payload: dict[str, object]) -> None:
    request = Request(
        endpoint,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"OTLP collector returned HTTP {response.status}.")


def run() -> None:
    endpoint = os.getenv(
        "OTLP_METRICS_ENDPOINT", "http://otel-collector:4318/v1/metrics"
    )
    stat_path = Path(os.getenv("CPU_STAT_PATH", "/host/proc/stat"))
    interval_seconds = float(os.getenv("CPU_TEMP_ESTIMATE_INTERVAL_SECONDS", "30"))
    if interval_seconds <= 0:
        raise ValueError("CPU_TEMP_ESTIMATE_INTERVAL_SECONDS must be greater than zero.")

    previous = read_cpu_times(stat_path)
    LOGGER.info(
        "Publishing synthetic metric %s every %s seconds; formula: %s",
        METRIC_NAME,
        interval_seconds,
        FORMULA,
    )
    while True:
        time.sleep(interval_seconds)
        try:
            current = read_cpu_times(stat_path)
            cpu_percent = calculate_cpu_utilization_percent(previous, current)
        except (OSError, ValueError) as error:
            LOGGER.error("Cannot calculate CPU utilization: %s", error)
            continue

        previous = current
        estimate = estimate_temperature_celsius(cpu_percent)
        payload = build_otlp_payload(cpu_percent, estimate)
        try:
            send_metric(endpoint, payload)
        except (HTTPError, URLError, TimeoutError, RuntimeError) as error:
            LOGGER.error("Could not send %s to the collector: %s", METRIC_NAME, error)
            continue
        LOGGER.info(
            "Sent %s=%.2f Cel (synthetic; CPU utilization %.2f%%)",
            METRIC_NAME,
            estimate,
            cpu_percent,
        )


if __name__ == "__main__":
    run()
