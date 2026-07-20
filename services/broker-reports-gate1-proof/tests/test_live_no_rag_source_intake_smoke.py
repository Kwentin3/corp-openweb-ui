from __future__ import annotations

import unittest
from unittest import mock

import requests

from scripts import live_no_rag_source_intake_smoke as smoke


class LiveNoRagSourceIntakeSmokeTests(unittest.TestCase):
    @mock.patch.object(smoke.time, "sleep", return_value=None)
    @mock.patch.object(smoke.time, "monotonic", side_effect=[0.0, 0.0, 1.0])
    def test_processing_status_retries_transient_timeout_to_completed(
        self,
        _monotonic: mock.Mock,
        sleep: mock.Mock,
    ) -> None:
        completed = mock.Mock()
        completed.raise_for_status.return_value = None
        completed.json.return_value = {"status": "completed"}
        session = mock.Mock()
        session.get.side_effect = [requests.ReadTimeout("transient"), completed]

        smoke._wait_file_processed(session, "https://stage.invalid", "synthetic-file")

        self.assertEqual(session.get.call_count, 2)
        sleep.assert_called_once_with(smoke.PROCESS_STATUS_POLL_INTERVAL_SECONDS)

    @mock.patch.object(smoke.time, "sleep", return_value=None)
    @mock.patch.object(smoke.time, "monotonic", side_effect=[0.0, 0.0, 3.0])
    def test_processing_status_reaches_terminal_timeout_after_transient_errors(
        self,
        _monotonic: mock.Mock,
        _sleep: mock.Mock,
    ) -> None:
        session = mock.Mock()
        session.get.side_effect = requests.ReadTimeout("transient")

        with mock.patch.object(smoke, "PROCESS_STATUS_DEADLINE_SECONDS", 2.0):
            with self.assertRaisesRegex(
                RuntimeError,
                "synthetic_file_processing_timeout:transient_ReadTimeout",
            ):
                smoke._wait_file_processed(
                    session,
                    "https://stage.invalid",
                    "synthetic-file",
                )

        self.assertEqual(session.get.call_count, 1)

    def test_processing_failed_is_terminal_and_not_retried(self) -> None:
        failed = mock.Mock()
        failed.raise_for_status.return_value = None
        failed.json.return_value = {"status": "failed"}
        session = mock.Mock()
        session.get.return_value = failed

        with self.assertRaisesRegex(RuntimeError, "synthetic_file_processing_failed"):
            smoke._wait_file_processed(
                session,
                "https://stage.invalid",
                "synthetic-file",
            )

        self.assertEqual(session.get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
