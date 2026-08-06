from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doc30_resource_bounded_backfill.py"
SPEC = importlib.util.spec_from_file_location("doc30_resource_bounded_backfill", SCRIPT)
assert SPEC and SPEC.loader
doc30 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doc30)


def _limits() -> dict:
    return {
        "cpu_millis": 500,
        "memory_bytes": 1024 * 1024 * 1024,
        "io_read_bps": 20 * 1024 * 1024,
        "io_write_bps": 10 * 1024 * 1024,
        "pids_limit": 128,
        "per_document_timeout_seconds": 600,
        "overall_control_timeout_seconds": 10800,
        "log_max_bytes": 10 * 1024 * 1024,
        "maximum_document_bytes": 64 * 1024 * 1024,
        "maximum_components": 4096,
        "minimum_free_bytes": 1024 * 1024 * 1024,
        "critical_free_ratio": 0.10,
        "concurrency": 1,
        "batch_size_documents": 1,
    }


def _fake_cgroup(root: Path) -> None:
    (root / "cpu.max").write_text("50000 100000\n", encoding="ascii")
    (root / "memory.max").write_text(f"{1024 * 1024 * 1024}\n", encoding="ascii")
    (root / "memory.peak").write_text("134217728\n", encoding="ascii")
    (root / "pids.max").write_text("128\n", encoding="ascii")
    (root / "io.max").write_text(
        "8:0 rbps=20971520 wbps=10485760\n", encoding="ascii"
    )
    (root / "cpu.stat").write_text("usage_usec 1000\n", encoding="ascii")
    (root / "io.stat").write_text(
        "8:0 rbytes=4096 wbytes=8192 rios=1 wios=1\n", encoding="ascii"
    )


def test_runtime_limits_fail_closed_when_memory_is_unbounded() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        _fake_cgroup(root)
        (root / "memory.max").write_text("max\n", encoding="ascii")
        with pytest.raises(RuntimeError, match="runtime_limit_unbounded"):
            doc30._validate_runtime_limits(_limits(), root)


def test_inventory_selects_stable_hashed_identity_without_exposing_names() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "private-name.html").write_text("<html>one</html>", encoding="utf-8")
        files, entries = doc30._inventory(
            root, expected_formats={"html": 1}, expected_unique_hashes=1
        )
        assert len(files) == 1
        assert entries[0]["format"] == "html"
        assert len(entries[0]["hashed_document_id"]) == 64
        assert "private-name" not in json.dumps(entries[0])


def test_one_document_checkpoint_is_idempotent_and_has_one_active_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        input_root = root / "input"
        store_root = root / "store"
        cgroup_root = root / "cgroup"
        input_root.mkdir()
        store_root.mkdir()
        cgroup_root.mkdir()
        (input_root / "source.html").write_text(
            "<html><body><h1>Statement</h1><p>Value 1</p></body></html>",
            encoding="utf-8",
        )
        _fake_cgroup(cgroup_root)
        production_inventory = doc30._inventory
        monkeypatch.setattr(doc30, "EXPECTED_FORMATS", {"html": 1})
        monkeypatch.setattr(
            doc30,
            "_inventory",
            lambda path, expected_formats=None, expected_unique_hashes=15: production_inventory(
                path, expected_formats={"html": 1}, expected_unique_hashes=1
            ),
        )
        limits = _limits()
        assert doc30.initialize(input_root, store_root, limits) == 0
        assert (
            doc30.process_one(
                input_root,
                store_root,
                1,
                limits,
                cgroup_root=cgroup_root,
            )
            == 0
        )
        state = doc30._load_state(store_root)
        entry = state["documents"][0]
        assert entry["status"] == "COMPLETED"
        assert entry["attempts"] == 1
        assert doc30._receipt_path(store_root, 1).is_file()
        assert (
            doc30.process_one(
                input_root,
                store_root,
                1,
                limits,
                cgroup_root=cgroup_root,
            )
            == 0
        )
        resumed = doc30._load_state(store_root)["documents"][0]
        assert resumed["attempts"] == 1
        store = doc30._store(store_root)
        context = doc30._context(resumed["normalization_run_id"])
        reader = doc30.CanonicalReaderFactory(store=store, read_enabled=True).create()
        assert len(reader.history(resumed["document_id"], context)) == 1
        assert (
            reader.read_active_envelope(resumed["document_id"], context).canonical_root_sha256
            == resumed["canonical_root_sha256"]
        )


def test_closed_world_image_contains_only_packaged_runtime_inputs() -> None:
    dockerfile = (SCRIPT.parents[1] / "Dockerfile.doc30").read_text(encoding="utf-8")
    assert "COPY broker_reports_gate1 /opt/broker-reports-doc30/broker_reports_gate1" in dockerfile
    assert "COPY scripts/doc30_resource_bounded_backfill.py" in dockerfile
    assert "PYTHONPATH=/opt/broker-reports-doc30" in dockerfile
    assert "../" not in dockerfile
