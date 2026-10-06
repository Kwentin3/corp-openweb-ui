#!/usr/bin/env python3
"""Host-side, content-free Docker/Linux flight recorder. Python standard library only."""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time


def stamp(t=None):
    return dt.datetime.fromtimestamp(time.time() if t is None else t, dt.timezone.utc).isoformat()


def atomic(path, value):
    tmp = path.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=True))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def run(args):
    return subprocess.check_output(args, timeout=8, stderr=subprocess.DEVNULL, text=True)


def access_record(line):
    # Never retain arbitrary log text, URLs, query strings, headers or bodies.
    m = re.search(r'"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) ([^ "?]+)(?:\?[^ "]*)? HTTP/[\d.]+" (\d{3})', line)
    if not m:
        return None
    method, path, status = m.groups()
    routes = {
        '/health': 'health', '/api/chat/completions': 'chat.completions',
        '/api/v1/chat/completions': 'chat.completions',
        '/api/v1/files/': 'files',
        '/healthz': 'health', '/v1/officecli/help': 'officecli.help',
        '/v1/officecli/skills/load': 'officecli.skills.load',
        '/stage2-api/media/prepare': 'media.prepare',
    }
    route = routes.get(path)
    office = re.fullmatch(r'/v1/officecli/(documents|spreadsheets|presentations)/(inspect|create|apply-batch)', path)
    if office:
        route = '.'.join(office.groups())
    if not route:
        route = 'other'  # Do not store user-controlled path segments.
    return {'method': method, 'route': route, 'status': int(status)}


def docker_record(event):
    action = event.get('Action', event.get('status', ''))
    if action not in {'oom', 'die', 'kill', 'start', 'stop', 'restart', 'destroy', 'create', 'update'} and not action.startswith('health_status:'):
        return None
    attrs = event.get('Actor', {}).get('Attributes', {})
    result = {'action': action, 'container': attrs.get('name', ''),
              'container_id': event.get('id', event.get('Actor', {}).get('ID', '')),
              'time_ns': event.get('timeNano', int(event.get('time', 0)) * 10**9)}
    for name in ('exitCode', 'signal'):
        if str(attrs.get(name, '')).isdigit():
            result[name] = int(attrs[name])
    return result


def kernel_record(entry):
    message = entry.get('MESSAGE', '')
    if not isinstance(message, str):
        return None
    m = re.search(r'(?:Out of memory|Memory cgroup out of memory): Killed process (\d+) \(([^)]+)\)', message)
    if m:
        # comm may be user-controlled. Keep only the PID and memory figures.
        result = {'event': 'oom_kill', 'pid': int(m[1])}
        for key in ('total-vm', 'anon-rss', 'file-rss', 'shmem-rss'):
            v = re.search(re.escape(key) + r':(\d+)kB', message)
            if v:
                result[key + '_kb'] = int(v[1])
        result['scope'] = 'cgroup' if 'Memory cgroup' in message else 'host'
        return result
    return None


class Store:
    def __init__(self, root, history_days=7, incident_days=30, history_bytes=256*1024**2, incident_bytes=64*1024**2):
        self.root = Path(root)
        self.history = self.root / 'history'
        self.incidents = self.root / 'incidents'
        for p in (self.root, self.history, self.incidents):
            p.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.history_days, self.incident_days = history_days, incident_days
        self.history_bytes, self.incident_bytes = history_bytes, incident_bytes
        self.current = None
        self.recent = collections.deque(maxlen=12000)
        self.pending = {p for p in self.incidents.glob('*.json') if not json.loads(p.read_text())['complete']}
        cutoff = time.time() - 600
        for p in sorted(self.history.glob('*.jsonl')):
            if p.stat().st_mtime < cutoff:
                continue
            with p.open(encoding='utf-8') as f:
                for line in f:
                    try:
                        row = json.loads(line)
                        if row['observed_at'] >= cutoff:
                            self.recent.append(row)
                    except (ValueError, KeyError):
                        pass  # A torn final line is not evidence.

    def add(self, kind, data):
        with self.lock:
            now = time.time()
            row = {'observed_at': now, 'utc': stamp(now), 'kind': kind, **data}
            if (self.current is None or not self.current.exists() or self.current.stat().st_size >= 4*1024**2
                    or now - int(self.current.stem)/10**9 >= 3600):
                self.current = self.history / (str(time.time_ns()) + '.jsonl')
            with self.current.open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=True) + '\n')
                f.flush()
                os.fsync(f.fileno())
            self.recent.append(row)
            self.prune()
            return row

    def incident(self, event):
        # Stable event identity also prevents duplicate cards after stream replay.
        key = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()[:24]
        path = self.incidents / (key + '.json')
        with self.lock:
            if path.exists():
                return
            now = time.time()
            atomic(path, {'id': key, 'created_at': now, 'trigger': event,
                          'cause': ('confirmed_container_oom' if event.get('action') == 'oom'
                                    else 'confirmed_kernel_oom' if event.get('event') == 'oom_kill' else 'unknown'),
                          'note': 'Temporal correlation does not establish the operation responsible. Exit 137 alone is not OOM proof.',
                          'after_until': now + 120, 'complete': False, 'timeline': []})
            self.pending.add(path)
            self.finish_cards(now)

    def finish_cards(self, now=None):
        now = time.time() if now is None else now
        with self.lock:
            for p in list(self.pending):
                if not p.exists():
                    self.pending.discard(p)
                    continue
                card = json.loads(p.read_text())
                rows = [r for r in self.recent if card['created_at'] - 600 <= r['observed_at'] <= card['after_until']]
                # Bound even high-volume incidents; explicitly report omitted rows.
                size, selected = 0, []
                for row in reversed(rows):
                    size += len(json.dumps(row))
                    if size > 2*1024**2:
                        break
                    selected.append(row)
                card.update(timeline=list(reversed(selected)), omitted_rows=len(rows)-len(selected),
                            recent_buffer_full=len(self.recent) == self.recent.maxlen,
                            complete=now >= card['after_until'], updated_at=now)
                atomic(p, card)
                if card['complete']:
                    self.pending.discard(p)
            self.prune()

    def prune(self):
        for directory, pattern, days, limit in (
            (self.history, '*.jsonl', self.history_days, self.history_bytes),
            (self.incidents, '*.json', self.incident_days, self.incident_bytes),
        ):
            files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
            total = sum(p.stat().st_size for p in files)
            for p in files:
                size = p.stat().st_size
                if p.stat().st_mtime < time.time() - days*86400 or total > limit:
                    p.unlink()
                    total -= size


def resources(targets=()):
    listing = run(['docker', 'ps', '-a', '--format', '{{.ID}} {{.Names}} {{.State}}'])
    ids = [parts[0] for line in listing.splitlines() if len(parts := line.split()) == 3
           and (parts[2] == 'running' or parts[1] in targets)]
    containers = json.loads(run(['docker', 'inspect', *ids])) if ids else []
    result = []
    for c in containers:
        state = c['State']
        row = {'name': c['Name'].lstrip('/'), 'id': c['Id'], 'image': c['Image'],
               'status': state['Status'], 'pid': state['Pid'], 'restart_count': c['RestartCount'],
               'oom_killed': state.get('OOMKilled'), 'exit_code': state['ExitCode'],
               'started_at': state['StartedAt'], 'finished_at': state['FinishedAt'],
               'health': state.get('Health', {}).get('Status'),
               'memory_limit': c['HostConfig']['Memory'], 'memory_swap_limit': c['HostConfig']['MemorySwap']}
        if state['Pid']:
            try:
                rel = Path('/proc', str(state['Pid']), 'cgroup').read_text().split('0::', 1)[1].strip()
                cg = Path('/sys/fs/cgroup') / rel.lstrip('/')
                for name in ('memory.current', 'memory.peak', 'memory.swap.current', 'memory.events', 'cpu.stat', 'memory.pressure'):
                    p = cg / name
                    if p.exists():
                        row[name] = p.read_text().strip()
                top = []
                for pid in (cg / 'cgroup.procs').read_text().split():
                    try:
                        status = Path('/proc', pid, 'status').read_text()
                        rss = re.search(r'VmRSS:\s+(\d+)', status)
                        if rss:
                            top.append({'pid': int(pid), 'rss_kb': int(rss[1])})
                    except (FileNotFoundError, ProcessLookupError):
                        pass
                row['top_rss'] = sorted(top, key=lambda p: p['rss_kb'], reverse=True)[:10]
            except (OSError, IndexError):
                row['cgroup_unavailable'] = True
        result.append(row)
    mem = dict(re.findall(r'^(MemTotal|MemAvailable|SwapTotal|SwapFree):\s+(\d+)', Path('/proc/meminfo').read_text(), re.M))
    return {'containers': result, 'host_kb': {k: int(v) for k, v in mem.items()},
            'host_memory_pressure': Path('/proc/pressure/memory').read_text().strip(),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


class Recorder:
    def __init__(self, root, targets, interval):
        self.store = Store(root)
        self.targets = set(targets)
        self.interval = interval
        self.stop = threading.Event()
        self.cursor_path = Path(root) / 'cursors.json'
        self.cursors = json.loads(self.cursor_path.read_text()) if self.cursor_path.exists() else {}
        self.cursor_lock = threading.Lock()
        self.workers = {}
        self.seen = collections.OrderedDict()

    def ingest(self, source, line):
        if source == 'docker':
            event = docker_record(json.loads(line))
            if event and event['container'] in self.targets:
                key = (event['container_id'], event['time_ns'], event['action'])
                if key not in self.seen:
                    self.store.add('docker', event)
                    self.seen[key] = True
                    if len(self.seen) > 4096:
                        self.seen.popitem(last=False)
                    if event['action'] in ('oom', 'die', 'kill', 'restart', 'stop'):
                        self.store.incident(event)
            # Docker accepts Unix seconds for --since. Replay boundary is intentional.
            obj = json.loads(line)
            cursor = str(obj.get('time', int(time.time())))
        elif source == 'kernel':
            obj = json.loads(line)
            event = kernel_record(obj)
            if event:
                record = {**event, 'source_utc_us': obj.get('__REALTIME_TIMESTAMP')}
                self.store.add('kernel', record)
                self.store.incident(record)
            cursor = obj.get('__CURSOR')
        else:
            event = access_record(line)
            cursor = line.split(' ', 1)[0]
            if not re.fullmatch(r'\d{4}-\d\d-\d\dT[\d:.]+Z', cursor):
                cursor = None
            if event and cursor:
                self.store.add('access', {'container': source, **event, 'source_time': cursor})
            elif cursor:
                error = re.search(r'\b(MemoryError|TimeoutError|ConnectionError|OSError|RuntimeError|HTTPException)\b', line)
                if error:
                    self.store.add('error', {'container': source, 'error_type': error[1], 'source_time': cursor})
        if cursor:
            with self.cursor_lock:
                self.cursors[source] = cursor

    def stream(self, source):
        while not self.stop.is_set():
            with self.cursor_lock:
                cursor = self.cursors.get(source)
            if source == 'docker':
                args = ['docker', 'events', '--filter', 'type=container', '--format', '{{json .}}', '--since', cursor or str(int(time.time())-60)]
            elif source == 'kernel':
                args = ['journalctl', '-k', '-f', '-o', 'json', '--no-pager']
                args += ['--after-cursor', cursor] if cursor else ['--since', '-1min']
            else:
                args = ['docker', 'logs', '--follow', '--timestamps', '--since', cursor or stamp(time.time()-60), source]
            process = None
            try:
                process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                while not self.stop.is_set():
                    raw = process.stdout.readline(8193)
                    if not raw:
                        break
                    if len(raw) > 8192 or not raw.endswith(b'\n'):
                        while raw and not raw.endswith(b'\n'):
                            raw = process.stdout.readline(8193)
                        continue
                    try:
                        self.ingest(source, raw.decode('utf-8', 'replace').strip())
                    except (ValueError, KeyError, TypeError):
                        pass  # No raw stderr/payload is persisted.
                self.store.add('collector', {'event': 'stream_disconnected', 'source': source})
            except OSError as e:
                self.store.add('collector', {'event': 'stream_error', 'source': source, 'error_type': type(e).__name__})
            finally:
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                # A vacuumed journal cursor must not cause a permanent collection gap.
                if source == 'kernel' and cursor:
                    with self.cursor_lock:
                        self.cursors.pop(source, None)
            self.stop.wait(5)

    def serve(self):
        self.store.add('collector', {'event': 'started', 'targets': sorted(self.targets), 'pid': os.getpid()})
        for source in ['docker', 'kernel', *sorted(self.targets)]:
            worker = threading.Thread(target=self.stream, args=(source,), daemon=True)
            self.workers[source] = worker
            worker.start()
        while not self.stop.is_set():
            started = time.monotonic()
            try:
                sample = resources(self.targets)
                previous_path = self.store.root / 'last-resources.json'
                previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
                previous = {c['name']: c for c in previous.get('containers', [])}
                for c in sample['containers']:
                    old = previous.get(c['name'])
                    if c['name'] in self.targets and old and any(c[k] != old[k] for k in ('id', 'restart_count', 'started_at')):
                        event = {'action': 'observed_lifecycle_change', 'container': c['name'],
                                 'container_id': c['id'], 'started_at': c['started_at'],
                                 'restart_count': c['restart_count'], 'previous_container_id': old['id']}
                        self.store.add('lifecycle', event)
                        self.store.incident(event)
                self.store.add('resources', sample)
                atomic(previous_path, sample)
            except (OSError, subprocess.SubprocessError, ValueError) as e:
                self.store.add('collector', {'event': 'sample_error', 'error_type': type(e).__name__})
            for source, worker in self.workers.items():
                if not worker.is_alive():
                    raise RuntimeError('collector worker stopped: ' + source)
            with self.cursor_lock:
                atomic(self.cursor_path, self.cursors)
            self.store.finish_cards()
            atomic(self.store.root / 'status.json', {'utc': stamp(), 'pid': os.getpid(), 'sources': sorted(self.workers)})
            self.stop.wait(max(0.1, self.interval - (time.monotonic()-started)))
        self.store.add('collector', {'event': 'stopping'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/var/lib/openwebui-flight-recorder')
    parser.add_argument('--targets', nargs='+', default=['openwebui', 'stage2-stt', 'officecli451e7cede5-officecli-openapi-proof-1'])
    parser.add_argument('--interval', type=float, default=10)
    args = parser.parse_args()
    os.umask(0o077)
    import fcntl  # Linux host only; prevent concurrent writers to the same store.
    Path(args.root).mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (Path(args.root) / 'writer.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    recorder = Recorder(args.root, args.targets, args.interval)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: recorder.stop.set())
    recorder.serve()


if __name__ == '__main__':
    main()
