import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


EVENT_BATCH_SIZE = 200
OPENOBSERVE_MAX_ATTEMPTS = 3
OPENOBSERVE_RETRY_DELAYS_SECONDS = (1, 2)
OPENOBSERVE_TIMEOUT_SECONDS = 20


def event_metadata() -> dict[str, str]:
    return {
        "commit_sha": os.getenv("GITHUB_SHA", "local"),
        "branch": os.getenv("GITHUB_REF_NAME", "local"),
        "actor": os.getenv("GITHUB_ACTOR", "local"),
        "workflow": os.getenv("GITHUB_WORKFLOW", "CompraJuegos CI/CD"),
        "run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", "local"),
        "repository": os.getenv("GITHUB_REPOSITORY", "local"),
    }


def build_event(event_type: str, outcomes: list[str]) -> dict[str, object]:
    outcome_map = {f"step_{index}": value for index, value in enumerate(outcomes, start=1)}
    status = (
        "success"
        if outcomes and all(value in {"success", "skipped"} for value in outcomes)
        else "failure"
    )
    failed_steps = [
        f"step_{index}"
        for index, outcome in enumerate(outcomes, start=1)
        if outcome == "failure"
    ]
    skipped_steps = [
        f"step_{index}"
        for index, outcome in enumerate(outcomes, start=1)
        if outcome == "skipped"
    ]
    deployment_eligible = (
        os.getenv("GITHUB_REF") == "refs/heads/main"
        and (
            os.getenv("GITHUB_EVENT_NAME") == "push"
            or (
                os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch"
                and os.getenv("ACCEPTANCE_FAILURE_PROBE", "").lower() == "true"
            )
        )
    )
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "status": status,
        "step_outcomes": outcome_map,
        "failed_steps": failed_steps,
        "skipped_steps": skipped_steps,
        "deployment_blocked": (
            status == "failure"
            and event_type == "test_run"
            and deployment_eligible
        ),
        **event_metadata(),
    }


def build_events(event_type: str, outcomes: list[str]) -> list[dict[str, object]]:
    event = build_event(event_type, outcomes)
    events = [event]
    if event["status"] == "failure":
        events.append(
            {
                **event_metadata(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": "pipeline_incident",
                "status": "failure",
                "incident_type": "pipeline_step_failure",
                "failed_event": event_type,
                "failed_steps": event["failed_steps"],
                "skipped_steps": event["skipped_steps"],
                "deployment_blocked": event["deployment_blocked"],
            }
        )
    return events


def _test_status(testcase: ET.Element) -> str:
    if testcase.find("failure") is not None or testcase.find("error") is not None:
        return "failed"
    if testcase.find("skipped") is not None:
        return "skipped"
    return "passed"


def build_junit_events(
    directory: Path, expected_files: Iterable[str] = ()
) -> list[dict[str, object]]:
    report_files = sorted(directory.glob("*.xml"))
    missing_files = sorted(set(expected_files) - {path.name for path in report_files})
    if missing_files:
        raise RuntimeError(f"Missing JUnit reports: {', '.join(missing_files)}.")
    if not report_files:
        print(f"WARNING: No JUnit XML reports found in {directory}.", file=sys.stderr)
        return []

    print(f"JUnit reports found: {', '.join(path.name for path in report_files)}.")
    metadata = event_metadata()
    events: list[dict[str, object]] = []
    for report_path in report_files:
        try:
            root = ET.parse(report_path).getroot()
        except ET.ParseError as error:
            raise RuntimeError(f"JUnit XML is invalid: {report_path}.") from error

        for testcase in root.iter("testcase"):
            test_name = testcase.get("name")
            if not test_name:
                raise RuntimeError(f"JUnit testcase has no name: {report_path}.")
            try:
                duration_ms = round(float(testcase.get("time", "0")) * 1000, 2)
            except ValueError as error:
                raise RuntimeError(f"JUnit testcase has an invalid duration: {report_path}.") from error

            test_context = {
                **metadata,
                "test_suite": testcase.get("classname") or report_path.stem,
                "test_name": test_name,
            }
            events.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": "test_case",
                    "status": _test_status(testcase),
                    "duration_ms": duration_ms,
                    "test_file": report_path.name,
                    **test_context,
                }
            )

            properties = testcase.find("properties")
            if properties is None:
                continue
            for property_element in properties.findall("property"):
                if property_element.get("name") != "http_request_metrics":
                    continue
                raw_metrics = property_element.get("value") or property_element.text or "[]"
                try:
                    metrics = json.loads(raw_metrics)
                except json.JSONDecodeError as error:
                    raise RuntimeError(
                        f"Invalid HTTP request metrics in {report_path} for {test_name}."
                    ) from error
                if not isinstance(metrics, list):
                    raise RuntimeError(
                        f"HTTP request metrics must be a list in {report_path} for {test_name}."
                    )
                for metric in metrics:
                    if not isinstance(metric, dict):
                        raise RuntimeError(
                            f"HTTP request metric must be an object in {report_path} for {test_name}."
                        )
                    required_fields = (
                        "timestamp",
                        "endpoint",
                        "method",
                        "status_code",
                        "response_time_ms",
                    )
                    if any(field not in metric for field in required_fields):
                        raise RuntimeError(
                            f"HTTP request metric is missing required fields in {report_path} for {test_name}."
                        )
                    events.append(
                        {
                            **metadata,
                            **test_context,
                            "event_type": "test_http_request",
                            **{field: metric[field] for field in required_fields},
                        }
                    )
    return events


def send_events(events: Iterable[dict[str, object]]) -> None:
    event_list = list(events)
    if not event_list:
        return

    base_url = os.getenv("OPENOBSERVE_URL", "").rstrip("/")
    email = os.getenv("OPENOBSERVE_EMAIL", "")
    password = os.getenv("OPENOBSERVE_PASSWORD", "")
    organization = os.getenv("OPENOBSERVE_ORG", "default")
    stream = os.getenv("OPENOBSERVE_STREAM", "ci_cd")
    if not all((base_url, email, password)):
        raise RuntimeError(
            "Configura OPENOBSERVE_URL, OPENOBSERVE_EMAIL y OPENOBSERVE_PASSWORD "
            "en los secretos/variables de GitHub."
        )

    url = f"{base_url}/api/{quote(organization, safe='')}/{quote(stream, safe='')}/_json"
    credentials = base64.b64encode(f"{email}:{password}".encode("utf-8")).decode("ascii")
    batches = [
        event_list[index : index + EVENT_BATCH_SIZE]
        for index in range(0, len(event_list), EVENT_BATCH_SIZE)
    ]
    for batch_number, batch in enumerate(batches, start=1):
        request = Request(
            url,
            data=json.dumps(batch).encode("utf-8"),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(1, OPENOBSERVE_MAX_ATTEMPTS + 1):
            try:
                with urlopen(request, timeout=OPENOBSERVE_TIMEOUT_SECONDS) as response:
                    if not 200 <= response.status < 300:
                        raise RuntimeError(
                            f"OpenObserve rechazó el lote: HTTP {response.status}"
                        )
                    print(
                        f"Lote {batch_number}/{len(batches)} registrado en OpenObserve "
                        f"({len(batch)} eventos, HTTP {response.status})."
                    )
                break
            except HTTPError as error:
                status_code = error.code
                if error.fp is not None:
                    error.close()
                if status_code not in {408, 425, 429} and status_code < 500:
                    raise RuntimeError(
                        f"OpenObserve respondió HTTP {status_code}."
                    ) from error
                failure_reason = f"HTTP {status_code}"
            except URLError as error:
                failure_reason = str(error.reason)
            except TimeoutError as error:
                failure_reason = str(error)

            if attempt == OPENOBSERVE_MAX_ATTEMPTS:
                raise RuntimeError(
                    f"No se pudo contactar OpenObserve tras {attempt} intentos: "
                    f"{failure_reason}."
                )

            delay = OPENOBSERVE_RETRY_DELAYS_SECONDS[attempt - 1]
            print(
                f"OpenObserve no disponible ({failure_reason}); "
                f"reintento {attempt + 1}/{OPENOBSERVE_MAX_ATTEMPTS} en {delay}s.",
                file=sys.stderr,
            )
            time.sleep(delay)


def main() -> int:
    parser = argparse.ArgumentParser(description="Reporta el resultado de CI/CD a OpenObserve.")
    parser.add_argument("--event", choices=("test_run", "deployment"), required=True)
    parser.add_argument("--outcome", action="append", default=[])
    parser.add_argument("--junit-dir", type=Path)
    parser.add_argument("--expected-junit-file", action="append", default=[])
    parser.add_argument("--require-http-metrics", action="store_true")
    arguments = parser.parse_args()
    try:
        events = build_events(arguments.event, arguments.outcome)
        if arguments.junit_dir is not None:
            all_steps_passed = bool(arguments.outcome) and all(
                outcome == "success" for outcome in arguments.outcome
            )
            expected_files = arguments.expected_junit_file if all_steps_passed else []
            detail_events = build_junit_events(arguments.junit_dir, expected_files)
            test_case_count = sum(event["event_type"] == "test_case" for event in detail_events)
            request_count = sum(event["event_type"] == "test_http_request" for event in detail_events)
            print(
                f"Preparados {test_case_count} resultados individuales y "
                f"{request_count} observaciones HTTP."
            )
            if arguments.require_http_metrics and all_steps_passed and request_count == 0:
                raise RuntimeError("No HTTP request metrics were found in the successful JUnit reports.")
            events.extend(detail_events)
        send_events(events)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
