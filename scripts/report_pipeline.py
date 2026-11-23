import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def build_event(event_type: str, outcomes: list[str]) -> dict[str, object]:
    outcome_map = {f"step_{index}": value for index, value in enumerate(outcomes, start=1)}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "status": "success" if outcomes and all(value == "success" for value in outcomes) else "failure",
        "step_outcomes": outcome_map,
        "commit_sha": os.getenv("GITHUB_SHA", "local"),
        "branch": os.getenv("GITHUB_REF_NAME", "local"),
        "actor": os.getenv("GITHUB_ACTOR", "local"),
        "workflow": os.getenv("GITHUB_WORKFLOW", "CompraJuegos CI/CD"),
        "run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "repository": os.getenv("GITHUB_REPOSITORY", "local"),
    }


def send_event(event: dict[str, object]) -> None:
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
    request = Request(
        url,
        data=json.dumps([event]).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"OpenObserve rechazó el evento: HTTP {response.status}")
            print(f"Evento {event['event_type']} registrado en OpenObserve (HTTP {response.status}).")
    except HTTPError as error:
        raise RuntimeError(f"OpenObserve respondió HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError(f"No se pudo contactar OpenObserve: {error.reason}.") from error


def main() -> int:
    parser = argparse.ArgumentParser(description="Reporta el resultado de CI/CD a OpenObserve.")
    parser.add_argument("--event", choices=("test_run", "deployment"), required=True)
    parser.add_argument("--outcome", action="append", default=[])
    arguments = parser.parse_args()
    try:
        send_event(build_event(arguments.event, arguments.outcome))
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
