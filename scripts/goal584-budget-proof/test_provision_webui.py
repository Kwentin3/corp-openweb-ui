"""Bounded native HTTP clock and administrator creation-order fixture checks."""
import copy
from datetime import datetime, timezone
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "deploy/openwebui-budgets")]
import provision_webui as P


CONTROL = "ffffffff-ffff-4fff-8fff-ffffffffffff"
OWNER = "11111111-1111-4111-8111-111111111111"  # Wins native UUID tie-break if timestamps tie.
CREATED = 1793664000


class NativeClockTests(unittest.TestCase):
    def setUp(self):
        self.records = {CONTROL: {"id": CONTROL, "role": "admin", "created_at": CREATED},
                        OWNER: {"id": OWNER, "role": "admin", "created_at": CREATED + 1}}
        self.dates, self.requests = [], []
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                owner.requests.append((self.path, self.headers.get("Authorization")))
                user_id = self.path.removeprefix("/api/v1/users/")
                if user_id not in owner.records:
                    self.send_error(404)
                    return
                data = json.dumps(owner.records[user_id]).encode()
                self.send_response_only(200)
                date = owner.dates.pop(0) if owner.dates else CREATED
                if date is not None:
                    self.send_header("Date", date if isinstance(date, str) else
                                     format_datetime(datetime.fromtimestamp(date, timezone.utc), usegmt=True))
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.target = patch.object(P, "WEBUI_URL", "http://127.0.0.1:" + str(self.server.server_port))
        self.target.start()
        self.webui = P.WebUI()
        self.control = {"id": CONTROL, "token": "synthetic-controller-session"}

    def tearDown(self):
        self.target.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive(), "Owned native-clock HTTP fixture did not stop")

    def state(self):
        return {"role_probe_control": self.control, "admin": {"id": OWNER, "token": "synthetic-owner-session"},
                "admin_creation_order": {"controller_created_at": CREATED, "server_second_before_owner_create": CREATED + 1}}

    def test_wait_uses_actual_response_date_and_rechecks_until_next_second(self):
        self.dates = [CREATED, CREATED, CREATED + 1]
        with patch.object(P.time, "sleep") as sleep:
            evidence = P.wait_after_controller_creation(self.webui, self.control)
        self.assertEqual(evidence, {"controller_created_at": CREATED, "server_second_before_owner_create": CREATED + 1})
        self.assertEqual(len(self.requests), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(self.requests, [("/api/v1/users/" + CONTROL, "Bearer synthetic-controller-session")] * 3)

    def test_server_already_in_later_second_needs_no_sleep(self):
        self.dates = [CREATED + 5]
        with patch.object(P.time, "sleep") as sleep:
            self.assertEqual(P.wait_after_controller_creation(self.webui, self.control)["server_second_before_owner_create"], CREATED + 5)
        sleep.assert_not_called()

    def test_stalled_server_date_times_out_without_using_runner_wall_clock(self):
        with patch.object(P.time, "monotonic", side_effect=[0.0, 1.0, 6.0]), patch.object(P.time, "sleep") as sleep:
            with self.assertRaisesRegex(P.ProofError, "clock did not advance"):
                P.wait_after_controller_creation(self.webui, self.control, timeout=5)
        self.assertEqual(len(self.requests), 2)
        sleep.assert_called_once_with(.1)

    def test_missing_or_invalid_date_never_reuses_previous_response_clock(self):
        for value in (None, "invalid native date"):
            self.dates = [CREATED + 1, value]
            P.native_admin_created_at(self.webui, self.control, self.control)
            self.assertEqual(self.webui.server_second, CREATED + 1)
            with self.subTest(date=value), self.assertRaisesRegex(P.ProofError, "HTTP Date is unavailable"):
                P.wait_after_controller_creation(self.webui, self.control)
            self.assertIsNone(self.webui.server_second)

    def test_strict_readback_rejects_uuid_tie_and_same_primary_identity(self):
        self.assertLess(OWNER, CONTROL)
        self.records[OWNER]["created_at"] = CREATED
        with self.assertRaisesRegex(P.ProofError, "strictly older"):
            P.read_admin_creation_order(self.webui, self.state())
        state = self.state()
        state["admin"]["id"] = CONTROL
        with self.assertRaisesRegex(P.ProofError, "ordering evidence is missing"):
            P.read_admin_creation_order(self.webui, state)

    def test_readback_binds_native_role_identity_and_timestamps(self):
        state = self.state()
        evidence = P.read_admin_creation_order(self.webui, state)
        self.assertEqual(evidence, {"controller_created_at": CREATED, "owner_created_at": CREATED + 1,
                                    "server_second_before_owner_create": CREATED + 1})
        state["admin_creation_order"] = evidence
        self.records[OWNER]["created_at"] += 1
        with self.assertRaisesRegex(P.ProofError, "strictly older"):
            P.read_admin_creation_order(self.webui, state)
        self.records[OWNER]["created_at"] -= 1
        for field, value in (("id", CONTROL), ("role", "user"), ("created_at", True), ("created_at", None)):
            original = copy.deepcopy(self.records[OWNER])
            self.records[OWNER][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(P.ProofError):
                P.read_admin_creation_order(self.webui, state)
            self.records[OWNER] = original


if __name__ == "__main__":
    unittest.main()
