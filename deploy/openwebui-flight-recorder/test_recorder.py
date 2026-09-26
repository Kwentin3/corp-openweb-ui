import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('recorder', Path(__file__).with_name('recorder.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class RecorderTests(unittest.TestCase):
    def test_access_does_not_save_payload_query_or_arbitrary_paths(self):
        line = 'INFO: 127.0.0.1 - "POST /v1/officecli/documents/create?token=SECRET HTTP/1.1" 422 Unprocessable Entity PROMPT'
        self.assertEqual(r.access_record(line), {'method': 'POST', 'route': 'documents.create', 'status': 422})
        self.assertEqual(r.access_record('"GET /private/SECRET HTTP/1.1" 200')['route'], 'other')
        self.assertIsNone(r.access_record('Authorization: SECRET'))
        self.assertEqual(r.access_record('"POST /v1/officecli/documents/apply-batch HTTP/1.1" 200')['route'], 'documents.apply-batch')

    def test_events_do_not_keep_labels_or_exec_commands(self):
        event = {'Action': 'die', 'time': 123, 'id': 'id', 'Actor': {'Attributes': {'name': 'test', 'exitCode': '137', 'secret': 'SECRET'}}}
        result = r.docker_record(event)
        self.assertNotIn('SECRET', json.dumps(result))
        self.assertEqual(result['exitCode'], 137)
        event['Action'] = 'exec_create: sh -c SECRET'
        self.assertIsNone(r.docker_record(event))

    def test_kernel_extracts_only_oom_facts(self):
        message = 'Memory cgroup out of memory: Killed process 42 (SECRET) total-vm:100kB, anon-rss:50kB, file-rss:0kB, shmem-rss:0kB'
        row = r.kernel_record({'MESSAGE': message})
        self.assertEqual(row['pid'], 42)
        self.assertEqual(row['scope'], 'cgroup')
        self.assertNotIn('SECRET', json.dumps(row))

    def test_incident_survives_recorder_restart_and_has_before_after(self):
        with tempfile.TemporaryDirectory() as temp:
            store = r.Store(temp)
            store.add('access', {'route': 'spreadsheets.create', 'status': 422})
            event = {'action': 'die', 'container_id': 'test', 'time_ns': 1, 'exitCode': 137}
            store.incident(event)
            store = r.Store(temp)
            store.add('resources', {'state': 'recovered'})
            store.incident(event)
            store.finish_cards(time.time() + 121)
            paths = list(store.incidents.glob('*.json'))
            self.assertEqual(len(paths), 1)
            card = json.loads(paths[0].read_text())
            self.assertTrue(card['complete'])
            self.assertEqual(card['cause'], 'unknown')
            self.assertEqual([x['kind'] for x in card['timeline']], ['access', 'resources'])

    def test_oom_event_is_distinguished_from_exit_137(self):
        with tempfile.TemporaryDirectory() as temp:
            store = r.Store(temp)
            store.incident({'action': 'oom', 'container_id': 'test'})
            card = json.loads(next(store.incidents.glob('*.json')).read_text())
            self.assertEqual(card['cause'], 'confirmed_container_oom')

    def test_retention_removes_expired_and_over_budget_files_only(self):
        with tempfile.TemporaryDirectory() as temp:
            store = r.Store(temp, history_bytes=200)
            keep = store.root / 'operator-note.txt'
            keep.write_text('keep')
            old = store.history / 'old.jsonl'
            old.write_text('{}\n')
            os.utime(old, (time.time()-8*86400,)*2)
            store.prune()
            self.assertFalse(old.exists())
            for i in range(4):
                store.current = None
                store.add('test', {'sequence': i})
            self.assertLessEqual(sum(p.stat().st_size for p in store.history.glob('*.jsonl')), 200)
            self.assertTrue(keep.exists())

    def test_ingest_rejects_fake_timestamp_and_ignores_unknown_container(self):
        with tempfile.TemporaryDirectory() as temp:
            recorder = r.Recorder(temp, ['openwebui'], 10)
            recorder.ingest('openwebui', 'SECRET "GET /health HTTP/1.1" 200')
            recorder.ingest('docker', json.dumps({'Action': 'die', 'time': 1, 'Actor': {'Attributes': {'name': 'other'}}}))
            self.assertEqual(len(recorder.store.recent), 0)

    def test_hourly_rotation_uses_creation_name_not_last_write_time(self):
        with tempfile.TemporaryDirectory() as temp:
            store = r.Store(temp)
            old = store.history / (str(int((time.time()-3601)*10**9)) + '.jsonl')
            old.write_text('{}\n')
            store.current = old
            store.add('test', {'sequence': 1})
            self.assertNotEqual(store.current, old)
            self.assertEqual(old.read_text(), '{}\n')


if __name__ == '__main__':
    unittest.main()
