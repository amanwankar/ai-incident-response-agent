import unittest
from datetime import datetime, timezone

from app.evidence_accuracy import (
    evidence_window,
    filter_timestamped_logs,
    nearest_sample,
    parse_log_timestamp,
)


class IncidentTimeEvidenceTests(unittest.TestCase):
    def test_window_is_anchored_to_incident(self):
        created = datetime(2026, 11, 21, 6, 41, tzinfo=timezone.utc)
        start, end = evidence_window(created, now=datetime(2026, 11, 22, tzinfo=timezone.utc))
        self.assertEqual(start.isoformat(), '2026-11-21T06:39:00+00:00')
        self.assertEqual(end.isoformat(), '2026-11-21T06:46:00+00:00')

    def test_only_timestamp_matched_logs(self):
        start = datetime(2026, 11, 21, 6, 39, tzinfo=timezone.utc)
        end = datetime(2026, 11, 21, 6, 46, tzinfo=timezone.utc)
        lines = [
            '{"timestamp":"2026-11-21T06:40:01+00:00","message":"status=500"}',
            '{"timestamp":"2026-11-22T09:00:00+00:00","message":"ERROR port occupied"}',
            'ERROR no timestamp',
        ]
        result = filter_timestamped_logs(lines, start, end)
        self.assertEqual(len(result), 1)
        self.assertIn('status=500', result[0])

    def test_log_timestamp_must_be_timezone_aware(self):
        self.assertIsNone(parse_log_timestamp('ERROR no timestamp'))
        self.assertIsNone(parse_log_timestamp('2026-11-21T06:41:00 ERROR'))

    def test_no_metric_sample_does_not_become_zero(self):
        when = datetime(2026, 11, 21, 6, 41, tzinfo=timezone.utc)
        self.assertIsNone(nearest_sample({'points': []}, when))
        self.assertIsNone(nearest_sample({'points': [{'timestamp': 0, 'value': 0.0}]}, when))

    def test_exact_zero_sample_is_valid(self):
        when = datetime(2026, 11, 21, 6, 41, tzinfo=timezone.utc)
        self.assertEqual(nearest_sample({'points': [{'timestamp': when.timestamp(), 'value': 0.0}]}, when), 0.0)


if __name__ == '__main__':
    unittest.main()
