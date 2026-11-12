"""Offline exact-source tests; no LiteLLM install, provider, Docker or database.

GOAL584_LITELLM_SOURCE_ROOT points to the read-only d665 Git cache. The default
is this repository's local/goal584/litellm/upstream cache. Only temporary copies
receive git apply. Native functions/classes execute with memory IO boundaries.
Alternatively GOAL584_NATIVE_FLOOR_SOURCE names the original proxy_server.py
in an exported image tree containing the five SOURCE_SHAS paths below.
"""

from __future__ import annotations

import ast
import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import hashlib
import heapq
import inspect
import json
from functools import lru_cache
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import ModuleType, SimpleNamespace
from typing import Any, ClassVar, Final, Optional, TypeVar
import unittest
from unittest.mock import patch

from pydantic import BaseModel


ROOT = Path(__file__).resolve().parents[2]
PIN = "d665dc1a6315847fcad6cc2c1264ceb47c06abce"
SOURCE_ROOT = Path(os.environ.get(
    "GOAL584_LITELLM_SOURCE_ROOT", ROOT / "local/goal584/litellm/upstream"
))
PATCH = ROOT / "deploy/litellm-patches/positive-floor-v1.105.1/floor.patch"
PROXY_PATH = "litellm/proxy/proxy_server.py"
ORIGINAL_SHA = "227a704e5c9e7bdd0569f80d520aa670bde32397d0983e165089c63dcb775b4e"
SOURCE_SHAS = {
    PROXY_PATH: ORIGINAL_SHA,
    "litellm/caching/in_memory_cache.py": "50a93d8f62ca3938ccd7b24ff76eb3d4e5d98d9efa4fcda395cb1317d77fdf30",
    "litellm/proxy/db/db_lookup_gate.py": "c3ddca1af89fab9aebf46400ca6a0b426d2bdced31f507e55c472f9f716f3fca",
    "litellm/proxy/db/spend_counter_reseed.py": "0d76c24ff02b48c4eda9fb8462f8e0fe394dd1c6ba52075f8ed13499adb03b9f",
    "litellm/proxy/management_endpoints/key_management_endpoints.py": "c9c644c2a93e20ef9d850454ddb4b23bf1db4823b66be415b9a13a5da045b4de",
}
COUNTER = "spend:key:fixture-key-hash"
MARKER = f"spend_db_floor:{COUNTER}"
FUNCTIONS = {"get_current_spend", "_authoritative_floor_spend"}


@lru_cache(maxsize=5)
def source(path: str) -> str:
    image_proxy = os.environ.get("GOAL584_NATIVE_FLOOR_SOURCE")
    if image_proxy:
        # An exported image tree keeps the original litellm/... paths. CI must
        # export these five files, not import/install the native package.
        proxy = Path(image_proxy).resolve(strict=True)
        candidate = proxy if path == PROXY_PATH else proxy.parents[2] / path
        data = candidate.read_bytes()
    else:
        data = subprocess.check_output(
            ["git", "-c", "gc.auto=0", "show", f"{PIN}:{path}"],
            cwd=SOURCE_ROOT,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
        )
    if hashlib.sha256(data).hexdigest() != SOURCE_SHAS[path]:
        raise AssertionError(f"native source mismatch: {path}")
    return data.decode("utf-8")


def execute(nodes: list[ast.stmt], scope: dict, name: str) -> None:
    # Annotations are irrelevant to these actual function bodies, but upstream
    # optional dependencies must not be imported just to resolve their names.
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *nodes,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), name, "exec"), scope)


def named(text: str, names: set[str]) -> list[ast.stmt]:
    nodes = [node for node in ast.parse(text).body if getattr(node, "name", None) in names]
    assert {node.name for node in nodes} == names
    return nodes


def apply_in_temporary_copy(original: str) -> str:
    with tempfile.TemporaryDirectory(prefix="goal584-floor-") as folder:
        path = Path(folder) / PROXY_PATH
        path.parent.mkdir(parents=True)
        path.write_bytes(original.encode())
        apply = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply"]
        for options in (["--check"], []):
            subprocess.run([*apply, *options, str(PATCH)], cwd=folder,
                           check=True, capture_output=True)
        result = path.read_bytes().decode()
        assert hashlib.sha256(result.encode()).hexdigest() == "e354f6e96e245828e35cd3658cced6a78430571f7d7e8590b523e36c848f677e"
        compile(result, PROXY_PATH, "exec")
        # A second application must not silently apply to already patched bytes.
        second = subprocess.run([*apply, "--check", str(PATCH)], cwd=folder,
                                capture_output=True)
        assert second.returncode != 0
        return result


class RedisMemory:
    """Explicit IO double, not claimed as execution of Redis Lua."""

    def __init__(self):
        self.values = {}
        self.fail_read = False
        self.fail_write = False
        self.force_zero_reads = False
        self.writes = []

    async def async_get_cache(self, key):
        if self.fail_read:
            raise ConnectionError("fixture Redis unavailable")
        return 0 if self.force_zero_reads else self.values.get(key)

    async def async_set_cache(self, key, value, nx=False, **kwargs):
        if self.fail_write:
            raise ConnectionError("fixture Redis unavailable")
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.writes.append(("set-nx" if nx else "set", key, value))
        return True

    async def async_set_max(self, key, value):
        if self.fail_write:
            raise ConnectionError("fixture Redis unavailable")
        self.values[key] = max(self.values.get(key, 0), value)
        self.writes.append(("max", key, value))
        return self.values[key]


class Fixture:
    def __init__(self, proxy: str, *, redis=True, strict=True):
        self.clock = 100.0
        self.db_value = 0.0
        self.db_error = False
        self.db_reads = 0
        self.active_reads = 0
        self.max_active_reads = 0
        self.entered = asyncio.Event()
        self.release = None
        self.records = []
        self.forgotten = []
        self.broadcasts = []
        self.scope = dict(asyncio=asyncio, time=time, Final=Final, ClassVar=ClassVar,
                          Optional=Optional, OrderedDict=OrderedDict, datetime=datetime,
                          timezone=timezone, TypeVar=TypeVar, Callable=Callable,
                          Awaitable=Awaitable, logging=logging)

        gate = source("litellm/proxy/db/db_lookup_gate.py")
        self.scope.update(PROXY_DB_LOOKUP_DEADLINE_SECONDS=10.0,
                          PROXY_DB_LOOKUP_MAX_CONCURRENCY=2)
        execute([n for n in ast.parse(gate).body if not isinstance(n, (ast.Import, ast.ImportFrom))],
                self.scope, "<native-db-lookup-gate>")

        self.scope.update(heapq=heapq, json=json, sys=sys, threading=threading,
                          BaseModel=BaseModel, BaseCache=object,
                          DEFAULT_MAX_SIZE_IN_MEMORY=200,
                          MAX_SIZE_PER_ITEM_IN_MEMORY_CACHE_IN_KB=1024)
        execute(named(source("litellm/caching/in_memory_cache.py"), {"InMemoryCache"}),
                self.scope, "<native-in-memory-cache>")
        self.memory = self.scope["InMemoryCache"](clock=lambda: self.clock)
        self.redis = RedisMemory() if redis else None
        self.cache = SimpleNamespace(in_memory_cache=self.memory, redis_cache=self.redis)

        async def find_unique(**kwargs):
            self.db_reads += 1
            self.active_reads += 1
            self.max_active_reads = max(self.max_active_reads, self.active_reads)
            snapshot = self.db_value
            self.entered.set()
            try:
                if self.release is not None:
                    await self.release.wait()
                if self.db_error:
                    raise ConnectionError("fixture DB unavailable")
                return SimpleNamespace(spend=snapshot)
            finally:
                self.active_reads -= 1

        repository = lambda prisma: SimpleNamespace(table=SimpleNamespace(find_unique=find_unique))

        async def no_batch(counter_key):
            return None

        self.scope.update(
            SPEND_COUNTER_RESEED_LOCKS_MAX_SIZE=10000,
            VerificationTokenRepository=repository, UserRepository=repository,
            TeamRepository=repository, TeamMembershipRepository=repository,
            OrganizationRepository=repository, ProjectRepository=repository,
            read_batched_spend_counter=no_batch,
            record_spend_counter_value=lambda key, value: self.records.append((key, value)),
            forget_spend_counter=lambda key: self.forgotten.append(key),
            verbose_proxy_logger=logging.getLogger("native-floor-test"),
            END_USER_COUNTER_PREFIX="spend:end_user:",
            _WINDOW_SPEND_ENTITY_TYPES={}, _WINDOW_SPEND_LOG_FIELDS={},
        )
        execute(named(source("litellm/proxy/db/spend_counter_reseed.py"), {"SpendCounterReseed"}),
                self.scope, "<native-spend-counter-reseed>")
        self.scope.update(
            spend_counter_cache=self.cache, prisma_client=object(),
            SPEND_DB_FLOOR_CACHE_TTL_SECONDS=5,
            active_spend_counter_batch=lambda: None,
            general_settings={"fail_closed_budget_enforcement": strict},
            HTTPException=__import__("fastapi").HTTPException,
            status=SimpleNamespace(HTTP_503_SERVICE_UNAVAILABLE=503),
        )
        execute(named(proxy, FUNCTIONS | {
            "_fail_closed_budget_enforcement", "_raise_budget_unverifiable",
            "read_spend_counter_cache_value", "_read_spend_counter_estimate",
            "_floor_spend_from_db", "_repair_stale_spend_counter",
        }), self.scope, "<native-proxy-functions>")
        execute(named(source("litellm/proxy/management_endpoints/key_management_endpoints.py"),
                      {"_set_spend_counter_with_floor_and_broadcast"}),
                self.scope, "<native-manual-reset-helper>")

        async def broadcast(**kwargs):
            self.broadcasts.append(kwargs)
        self.scope["publish_auth_cache_invalidation"] = broadcast

    def floor(self, value):
        self.memory.set_cache(key=MARKER, value=value, ttl=5)

    def live(self, value):
        self.memory.set_cache(key=COUNTER, value=value)
        if self.redis is not None:
            self.redis.values[COUNTER] = value

    async def current(self, cap=.4, fallback=0, **kwargs):
        return await self.scope["get_current_spend"](
            counter_key=COUNTER, fallback_spend=fallback, max_budget=cap, **kwargs)

    async def read_floor(self, current=0):
        function = self.scope["_authoritative_floor_spend"]
        kwargs = {"current_spend": current} if "current_spend" in inspect.signature(function).parameters else {}
        return await function(counter_key=COUNTER, **kwargs)

    async def manual_reset(self, value=0):
        module = ModuleType("litellm.proxy.proxy_server")
        module.spend_counter_cache = self.cache
        module.SPEND_DB_FLOOR_CACHE_TTL_SECONDS = 5
        with patch.dict(sys.modules, {"litellm.proxy.proxy_server": module}):
            await self.scope["_set_spend_counter_with_floor_and_broadcast"](COUNTER, value)


class PatchSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = source(PROXY_PATH)
        assert hashlib.sha256(cls.original.encode()).hexdigest() == ORIGINAL_SHA
        cls.patched = apply_in_temporary_copy(cls.original)

    def test_exact_two_function_delta_and_public_signature(self):
        old, new = ast.parse(self.original), ast.parse(self.patched)
        self.assertEqual(len(old.body), len(new.body))
        changed = []
        for before, after in zip(old.body, new.body):
            if ast.dump(before) != ast.dump(after):
                self.assertIsInstance(before, ast.AsyncFunctionDef)
                self.assertIsInstance(after, ast.AsyncFunctionDef)
                self.assertEqual(before.name, after.name)
                changed.append(before.name)
                if before.name == "get_current_spend":
                    self.assertEqual(ast.dump(before.args), ast.dump(after.args))
        self.assertEqual(set(changed), FUNCTIONS)
        self.assertEqual(len(changed), 2)

    def test_patch_paths_and_no_new_nested_owner(self):
        lines = PATCH.read_text().splitlines()
        self.assertEqual([l for l in lines if l.startswith("--- ")], [f"--- a/{PROXY_PATH}"])
        self.assertEqual([l for l in lines if l.startswith("+++ ")], [f"+++ b/{PROXY_PATH}"])
        for node in named(self.patched, FUNCTIONS):
            self.assertFalse(any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                                 for statement in node.body for n in ast.walk(statement)))

    def test_wrong_exported_source_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="goal584-wrong-source-") as folder:
            wrong = Path(folder) / "proxy_server.py"
            wrong.write_bytes(b"# fixture changed native source\n")
            source.cache_clear()
            try:
                with patch.dict(os.environ, {"GOAL584_NATIVE_FLOOR_SOURCE": str(wrong)}):
                    with self.assertRaisesRegex(AssertionError, "native source mismatch"):
                        source(PROXY_PATH)
            finally:
                source.cache_clear()


class NativeFloorTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = source(PROXY_PATH)
        assert hashlib.sha256(cls.original.encode()).hexdigest() == ORIGINAL_SHA
        cls.patched = apply_in_temporary_copy(cls.original)

    def fixture(self, patched=True, **kwargs):
        return Fixture(self.patched if patched else self.original, **kwargs)

    async def test_completed_reset_before_after_counter_chain(self):
        for patched, initial, final in [(False, .2, .4), (True, 0, .2)]:
            with self.subTest(patched=patched):
                fixture = self.fixture(patched)
                fixture.floor(.2)
                # Clean Redis miss reseeds DB0 through actual native coalesced.
                self.assertAlmostEqual(await fixture.current(), initial)
                fixture.db_value = .2
                fixture.live((fixture.redis.values.get(COUNTER) or 0) + .2)
                self.assertAlmostEqual(await fixture.current(), final)
                self.assertAlmostEqual(fixture.redis.values[COUNTER], final)
                self.assertEqual(fixture.db_reads, 2 if patched else 1)

    async def test_same_period_stale_low_still_repairs(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.live(0)
        fixture.db_value = .2
        self.assertEqual(await fixture.current(), .2)
        self.assertEqual(fixture.redis.values[COUNTER], .2)
        self.assertEqual(fixture.redis.writes, [("max", COUNTER, .2)])
        self.assertEqual(fixture.db_reads, 1)

    async def test_actual_manual_marker_during_cold_and_warm_old_read(self):
        for warm in [False, True]:
            with self.subTest(warm=warm):
                fixture = self.fixture()
                fixture.live(0)
                if warm:
                    fixture.floor(.2)
                fixture.db_value = .2
                fixture.release = asyncio.Event()
                task = asyncio.create_task(fixture.current())
                await asyncio.wait_for(fixture.entered.wait(), 1)
                self.assertIsNone(fixture.memory.get_cache(key=MARKER))
                await fixture.manual_reset()
                fixture.release.set()
                self.assertEqual(await task, 0)
                self.assertEqual(fixture.memory.get_cache(key=MARKER), 0)
                self.assertEqual(fixture.redis.values[COUNTER], 0)
                self.assertEqual(len(fixture.broadcasts), 2)

    async def test_same_value_marker_is_not_treated_as_generation(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.db_value = 0
        fixture.release = asyncio.Event()
        task = asyncio.create_task(fixture.read_floor())
        await asyncio.wait_for(fixture.entered.wait(), 1)
        fixture.floor(.2)  # Any marker written during await wins, even same value.
        fixture.release.set()
        self.assertEqual(await task, .2)

    async def test_new_positive_live_increment_is_never_lowered(self):
        for db_value in [0, .2]:
            with self.subTest(db_value=db_value):
                fixture = self.fixture()
                fixture.floor(.2)
                fixture.live(0)
                fixture.db_value = db_value
                fixture.release = asyncio.Event()
                task = asyncio.create_task(fixture.current())
                await asyncio.wait_for(fixture.entered.wait(), 1)
                fixture.live(.3)
                fixture.release.set()
                await task
                self.assertEqual(fixture.redis.values[COUNTER], .3)
                self.assertEqual(fixture.memory.get_cache(key=COUNTER), .3)
                self.assertFalse(any(kind == "set" for kind, _, _ in fixture.redis.writes))

    async def test_simultaneous_followers_coalesce_actual_db_read(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.live(0)
        fixture.db_value = .2
        fixture.release = asyncio.Event()
        leader = asyncio.create_task(fixture.current())
        await asyncio.wait_for(fixture.entered.wait(), 1)
        followers = [asyncio.create_task(fixture.current()) for _ in range(20)]
        await asyncio.sleep(0)
        fixture.release.set()
        results = await asyncio.wait_for(asyncio.gather(leader, *followers), 2)
        self.assertEqual(results, [.2] * 21)
        self.assertEqual(fixture.db_reads, 1)
        self.assertEqual(fixture.max_active_reads, 1)

    async def test_positive_snapshots_before_lock_do_not_claim_burst_coalescing(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.live(0)
        fixture.db_value = .2
        lock = await fixture.scope["SpendCounterReseed"]._get_lock(COUNTER)
        await lock.acquire()
        try:
            tasks = [asyncio.create_task(fixture.current(fallback=.2)) for _ in range(8)]
            # Each caller reads the old positive marker before waiting for this
            # exact native lock. No equality/identity test pretends it is an epoch.
            for _ in range(3):
                await asyncio.sleep(0)
            self.assertTrue(all(not task.done() for task in tasks))
            self.assertEqual(fixture.db_reads, 0)
        finally:
            lock.release()
        self.assertEqual(await asyncio.wait_for(asyncio.gather(*tasks), 3), [.2] * 8)
        self.assertEqual(fixture.db_reads, 8)
        self.assertEqual(fixture.max_active_reads, 1)

    async def test_native_lookup_deadline_restores_floor_and_releases_gate(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.live(0)
        fixture.release = asyncio.Event()
        # Test-only deadline for a deliberately unanswered memory repository.
        # Native default10s, real runtime TTL5s/auth60s are not changed.
        fixture.scope["PROXY_DB_LOOKUP_DEADLINE_SECONDS"] = .5
        with self.assertLogs("native-floor-test", level="ERROR"):
            self.assertEqual(await asyncio.wait_for(fixture.current(), 3), .2)
        self.assertTrue(fixture.scope["db_lookup_stall_tracker"].stalled_within(5))
        await asyncio.sleep(0)
        self.assertEqual(fixture.active_reads, 0)
        self.assertEqual(fixture.memory.get_cache(key=MARKER), .2)
        lock = await fixture.scope["SpendCounterReseed"]._get_lock(COUNTER)
        self.assertFalse(lock.locked())
        fixture.release.set()
        fixture.scope["db_lookup_stall_tracker"].clear()
        self.assertEqual(await fixture.read_floor(), 0)

    async def test_actual_native_cold_manual_protection_baseline(self):
        fixture = self.fixture(False)
        fixture.live(0)
        fixture.db_value = .2
        fixture.release = asyncio.Event()
        task = asyncio.create_task(fixture.current())
        await asyncio.wait_for(fixture.entered.wait(), 1)
        await fixture.manual_reset()
        fixture.release.set()
        self.assertEqual(await task, 0)

    async def test_db_error_conservatively_retains_known_floor(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.live(0)
        fixture.db_error = True
        with self.assertLogs("native-floor-test", level="ERROR"):
            self.assertEqual(await fixture.current(), .2)
        self.assertEqual(fixture.memory.get_cache(key=MARKER), .2)
        self.assertEqual(fixture.redis.values[COUNTER], .2)

    async def test_unexpected_db_exception_identity_is_preserved(self):
        fixture = self.fixture()
        fixture.floor(.2)
        error = RuntimeError("fixture boundary exception")

        async def failed(**kwargs):
            raise error
        fixture.scope["_floor_spend_from_db"] = failed
        with self.assertRaises(RuntimeError) as caught:
            await fixture.read_floor()
        self.assertIs(caught.exception, error)
        self.assertEqual(fixture.memory.get_cache(key=MARKER), .2)
        lock = await fixture.scope["SpendCounterReseed"]._get_lock(COUNTER)
        self.assertFalse(lock.locked())

    async def test_cancellation_restores_floor_and_releases_native_lock(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.release = asyncio.Event()
        task = asyncio.create_task(fixture.read_floor())
        await asyncio.wait_for(fixture.entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(fixture.memory.get_cache(key=MARKER), .2)
        lock = await fixture.scope["SpendCounterReseed"]._get_lock(COUNTER)
        self.assertFalse(lock.locked())
        fixture.release.set()
        fixture.db_value = 0
        self.assertEqual(await asyncio.wait_for(fixture.read_floor(), 1), 0)

    async def test_cancel_does_not_overwrite_new_manual_marker(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.release = asyncio.Event()
        task = asyncio.create_task(fixture.read_floor())
        await asyncio.wait_for(fixture.entered.wait(), 1)
        await fixture.manual_reset()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(fixture.memory.get_cache(key=MARKER), 0)

    async def test_early_cap_and_no_cap_remain_no_db(self):
        for cap in [None, .4]:
            fixture = self.fixture()
            fixture.floor(.2)
            fixture.live(.4)
            self.assertEqual(await fixture.current(cap), .4)
            self.assertEqual(fixture.db_reads, 0)

    async def test_default_mode_only_refreshes_existing_staleness_path(self):
        fixture = self.fixture(strict=False)
        fixture.floor(.2)
        fixture.live(0)
        self.assertEqual(await fixture.current(), 0)
        self.assertEqual(fixture.db_reads, 0)
        self.assertEqual(await fixture.current(fallback=.2), 0)
        self.assertEqual(fixture.db_reads, 1)

    async def test_no_redis_db_failure_remains_fail_closed(self):
        fixture = self.fixture(redis=False)
        fixture.live(0)
        fixture.db_error = True
        with self.assertLogs("native-floor-test", level="WARNING"):
            with self.assertRaises(fixture.scope["HTTPException"]) as error:
                await fixture.current()
        self.assertEqual(error.exception.status_code, 503)

    async def test_no_redis_fresh_db_can_verify_and_repair_without_recursion(self):
        for value in [0, .2]:
            fixture = self.fixture(redis=False)
            fixture.floor(.2)
            fixture.live(0)
            fixture.db_value = value
            self.assertEqual(await asyncio.wait_for(fixture.current(), 2), value)
            self.assertEqual(fixture.memory.get_cache(key=COUNTER), value)
            self.assertEqual(fixture.db_reads, 1)

    async def test_redis_failure_and_no_floor_cannot_admit_unverified_local(self):
        fixture = self.fixture()
        fixture.live(0)
        fixture.redis.fail_read = True
        fixture.db_error = True
        with self.assertLogs("native-floor-test", level="WARNING"):
            with self.assertRaises(fixture.scope["HTTPException"]) as error:
                await fixture.current()
        self.assertEqual(error.exception.status_code, 503)

    async def test_native_gate_limits_distinct_counter_reads(self):
        fixture = self.fixture()
        fixture.release = asyncio.Event()
        function = fixture.scope["_authoritative_floor_spend"]
        tasks = [asyncio.create_task(function(counter_key=f"spend:key:k{i}", current_spend=0))
                 for i in range(6)]
        await asyncio.wait_for(fixture.entered.wait(), 1)
        # The DB coroutine is a native bounded task; allow all contenders to run.
        for _ in range(6):
            await asyncio.sleep(0)
        self.assertEqual(fixture.active_reads, 2)
        fixture.release.set()
        self.assertEqual(await asyncio.wait_for(asyncio.gather(*tasks), 2), [0] * 6)
        self.assertEqual(fixture.db_reads, 6)
        self.assertEqual(fixture.max_active_reads, 2)

    async def test_explicit_limits_calendar_inflight_and_no_redis_stale_high(self):
        # These remain unclosed baseline limitations, not acceptance of a fix.
        for patched in [False, True]:
            fixture = self.fixture(patched)
            fixture.db_value = .2
            fixture.release = asyncio.Event()
            task = asyncio.create_task(fixture.read_floor())
            await asyncio.wait_for(fixture.entered.wait(), 1)
            fixture.db_value = 0  # Calendar commit writes no local floor marker.
            fixture.release.set()
            self.assertEqual(await task, .2)
            no_redis = self.fixture(patched, redis=False)
            no_redis.live(.2)
            no_redis.floor(.2)
            self.assertEqual(await no_redis.current(), .2)
            self.assertEqual(no_redis.db_reads, 0)

    async def test_persistently_stale_low_queries_are_bounded_per_refresh_not_ttl(self):
        fixture = self.fixture()
        fixture.floor(.2)
        fixture.live(0)
        fixture.db_value = .2
        fixture.redis.force_zero_reads = True
        for _ in range(3):
            self.assertEqual(await fixture.current(), .2)
        self.assertEqual(fixture.db_reads, 3)
        self.assertEqual(fixture.max_active_reads, 1)


if __name__ == "__main__":
    unittest.main()
