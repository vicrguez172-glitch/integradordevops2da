import json
import tempfile
import unittest
from pathlib import Path

from observability.cpu_temp_estimator import (
    METRIC_NAME,
    build_otlp_payload,
    calculate_cpu_utilization_percent,
    estimate_temperature_celsius,
    read_cpu_times,
)


class CpuTemperatureEstimateTests(unittest.TestCase):
    def test_reads_aggregate_cpu_counters(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            stat_path = Path(temporary_directory) / "stat"
            stat_path.write_text(
                "cpu  100 20 30 400 10 5 5 0 2 1\n"
                "cpu0 50 10 15 200 5 2 3 0 1 0\n",
                encoding="ascii",
            )

            self.assertEqual(
                read_cpu_times(stat_path),
                (100, 20, 30, 400, 10, 5, 5, 0, 2, 1),
            )

    def test_calculates_busy_cpu_percentage_excluding_guest_counters(self):
        previous = (100, 20, 30, 400, 10, 5, 5, 0, 2, 1)
        current = (150, 20, 60, 480, 10, 5, 5, 0, 102, 101)

        self.assertAlmostEqual(
            calculate_cpu_utilization_percent(previous, current),
            50.0,
        )

    def test_applies_requested_formula_and_rejects_out_of_range_cpu(self):
        self.assertEqual(estimate_temperature_celsius(0), 38.0)
        self.assertEqual(estimate_temperature_celsius(50), 58.0)
        self.assertEqual(estimate_temperature_celsius(100), 78.0)
        with self.assertRaises(ValueError):
            estimate_temperature_celsius(101)

    def test_payload_labels_value_as_an_estimate(self):
        payload = build_otlp_payload(50.0, 58.0, timestamp_unix_nano=123)
        metric = payload["resourceMetrics"][0]["scopeMetrics"][0]["metrics"][0]
        data_point = metric["gauge"]["dataPoints"][0]
        attributes = {
            item["key"]: item["value"]
            for item in data_point["attributes"]
        }

        self.assertEqual(metric["name"], METRIC_NAME)
        self.assertIn("not measured", metric["description"])
        self.assertEqual(data_point["asDouble"], 58.0)
        self.assertEqual(data_point["timeUnixNano"], "123")
        self.assertEqual(attributes["estimated"]["stringValue"], "true")
        self.assertEqual(attributes["source"]["stringValue"], "cpu_utilization_formula")
        self.assertEqual(attributes["cpu_utilization_percent"]["doubleValue"], 50.0)
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
