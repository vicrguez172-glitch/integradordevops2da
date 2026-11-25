import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.report_pipeline import build_events, build_junit_events, send_events


class PipelineIncidentTests(unittest.TestCase):
    def test_failed_main_push_creates_incident_and_marks_deploy_blocked(self):
        environment = {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_RUN_ID": "12345",
        }
        with patch.dict(os.environ, environment):
            events = build_events("test_run", ["success", "failure", "skipped"])

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["status"], "failure")
        self.assertEqual(events[0]["failed_steps"], ["step_2", "step_3"])
        self.assertTrue(events[0]["deployment_blocked"])
        self.assertEqual(events[1]["event_type"], "pipeline_incident")
        self.assertEqual(events[1]["incident_type"], "pipeline_step_failure")
        self.assertEqual(events[1]["failed_event"], "test_run")
        self.assertEqual(events[1]["run_id"], "12345")
        self.assertTrue(events[1]["deployment_blocked"])

    def test_failure_on_non_deployable_ref_does_not_claim_main_deploy_blocked(self):
        with patch.dict(
            os.environ,
            {"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/feature"},
        ):
            events = build_events("test_run", ["failure"])

        self.assertFalse(events[0]["deployment_blocked"])
        self.assertFalse(events[1]["deployment_blocked"])

    def test_successful_pipeline_does_not_create_incident(self):
        self.assertEqual(len(build_events("test_run", ["success", "success"])), 1)


class JUnitEventTests(unittest.TestCase):
    def test_builds_case_and_http_events_from_junit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "playwright.xml"
            root = ET.Element("testsuites")
            suite = ET.SubElement(root, "testsuite", name="e2e.test_store")
            passed = ET.SubElement(
                suite,
                "testcase",
                classname="e2e.test_store",
                name="test_customer_purchase",
                time="0.125",
            )
            properties = ET.SubElement(passed, "properties")
            ET.SubElement(
                properties,
                "property",
                name="http_request_metrics",
                value=json.dumps(
                    [
                        {
                            "timestamp": "2026-11-23T08:00:00+00:00",
                            "endpoint": "/api/purchases",
                            "method": "POST",
                            "status_code": 201,
                            "response_time_ms": 24.5,
                        }
                    ]
                ),
            )
            failed = ET.SubElement(
                suite,
                "testcase",
                classname="backend.test_users",
                name="test_invalid_update",
                time="0.03",
            )
            ET.SubElement(failed, "failure", message="assertion failed")
            skipped = ET.SubElement(
                suite,
                "testcase",
                classname="backend.test_users",
                name="test_optional_feature",
                time="0",
            )
            ET.SubElement(skipped, "skipped")
            ET.ElementTree(root).write(report_path, encoding="utf-8", xml_declaration=True)

            events = build_junit_events(Path(temporary_directory))

        test_events = [event for event in events if event["event_type"] == "test_case"]
        request_events = [event for event in events if event["event_type"] == "test_http_request"]
        self.assertEqual([event["status"] for event in test_events], ["passed", "failed", "skipped"])
        self.assertEqual(test_events[0]["test_name"], "test_customer_purchase")
        self.assertEqual(test_events[0]["duration_ms"], 125.0)
        self.assertEqual(len(request_events), 1)
        self.assertEqual(request_events[0]["endpoint"], "/api/purchases")
        self.assertEqual(request_events[0]["method"], "POST")
        self.assertEqual(request_events[0]["status_code"], 201)
        self.assertEqual(request_events[0]["response_time_ms"], 24.5)
        self.assertEqual(request_events[0]["timestamp"], "2026-11-23T08:00:00+00:00")

    def test_reports_all_expected_backend_and_browser_cases(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            for filename, suite_name, test_count in (
                ("backend.xml", "backend.tests", 20),
                ("playwright-store.xml", "e2e.test_store", 5),
                ("playwright-matrix.xml", "e2e.test_ui_matrix", 1700),
            ):
                root = ET.Element("testsuites")
                suite = ET.SubElement(root, "testsuite", name=suite_name)
                for index in range(test_count):
                    ET.SubElement(
                        suite,
                        "testcase",
                        classname=suite_name,
                        name=f"test_case_{index}",
                        time="0.001",
                    )
                report_path = Path(temporary_directory) / filename
                ET.ElementTree(root).write(report_path, encoding="utf-8", xml_declaration=True)

            events = build_junit_events(
                Path(temporary_directory),
                ["backend.xml", "playwright-store.xml", "playwright-matrix.xml"],
            )

        self.assertEqual(len(events), 1725)
        self.assertEqual(events[0]["test_suite"], "backend.tests")
        self.assertEqual(events[0]["test_name"], "test_case_0")
        matrix_cases = [
            event for event in events if event["test_suite"] == "e2e.test_ui_matrix"
        ]
        self.assertEqual(len(matrix_cases), 1700)
        self.assertEqual(matrix_cases[-1]["test_name"], "test_case_1699")

    def test_rejects_malformed_http_metrics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            report_path = Path(temporary_directory) / "invalid.xml"
            root = ET.Element("testsuites")
            suite = ET.SubElement(root, "testsuite", name="e2e.test_store")
            testcase = ET.SubElement(
                suite,
                "testcase",
                classname="e2e.test_store",
                name="test_bad_metrics",
                time="0",
            )
            properties = ET.SubElement(testcase, "properties")
            ET.SubElement(
                properties,
                "property",
                name="http_request_metrics",
                value="{not-json}",
            )
            ET.ElementTree(root).write(report_path, encoding="utf-8", xml_declaration=True)

            with self.assertRaisesRegex(RuntimeError, "Invalid HTTP request metrics"):
                build_junit_events(Path(temporary_directory))

    def test_requires_named_junit_reports_when_requested(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(RuntimeError, "Missing JUnit reports: backend.xml"):
                build_junit_events(Path(temporary_directory), ["backend.xml"])


class EventBatchTests(unittest.TestCase):
    def test_sends_all_test_events_in_bounded_batches(self):
        response = MagicMock()
        response.status = 200
        environment = {
            "OPENOBSERVE_URL": "https://observe.example.test",
            "OPENOBSERVE_EMAIL": "test@example.test",
            "OPENOBSERVE_PASSWORD": "test-password",
            "OPENOBSERVE_ORG": "default",
            "OPENOBSERVE_STREAM": "ci_cd",
        }
        with patch.dict(os.environ, environment), patch(
            "scripts.report_pipeline.urlopen"
        ) as mocked_urlopen:
            mocked_urlopen.return_value.__enter__.return_value = response
            send_events([{"event_type": "test_case", "test_name": str(index)} for index in range(1725)])

        self.assertEqual(mocked_urlopen.call_count, 9)
        first_request = mocked_urlopen.call_args_list[0].args[0]
        final_request = mocked_urlopen.call_args_list[-1].args[0]
        payload_sizes = [
            len(json.loads(call.args[0].data))
            for call in mocked_urlopen.call_args_list
        ]
        self.assertEqual(payload_sizes, [200] * 8 + [125])
        self.assertEqual(
            first_request.full_url,
            "https://observe.example.test/api/default/ci_cd/_json",
        )
        self.assertEqual(len(json.loads(first_request.data)), 200)
        self.assertEqual(len(json.loads(final_request.data)), 125)


if __name__ == "__main__":
    unittest.main()
