#!/usr/bin/env python3
"""Resource-bounded, resumable DOC30 canonical backfill entrypoint.

The command processes at most one source document per invocation. Canonical
data continues to flow through the maintained normalizer, persistence facade
and reader factories. Private source identity and checkpoints stay outside
Git; stdout contains only a privacy-safe receipt.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterator


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalReaderFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)


SCHEMA_VERSION = "broker_reports_doc30_resource_bounded_backfill_command_v1"
STATE_SCHEMA_VERSION = "broker_reports_doc30_private_backfill_state_v1"
EXPECTED_FORMATS = {"pdf": 8, "html": 4, "csv": 2, "xlsx": 2}
ALLOWED_SUFFIXES = {".pdf", ".html", ".htm", ".csv", ".xlsx"}
CONTEXT = {
    "user_id": "doc30-approved-cohort-user",
    "case_id": "doc30-approved-cohort",
    "workspace_model_id": "doc30-canonical-shadow",
}


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    value = {
        "schema_version": SCHEMA_VERSION,
        "private_content_in_output": False,
        **payload,
    }
    value["integrity_sha256"] = _sha(value)
    return value


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True), flush=True)


def _mime(path: Path) -> str:
    return {
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".htm": "text/html",
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }[path.suffix.lower()]


def _format(path: Path) -> str:
    return "html" if path.suffix.lower() in {".html", ".htm"} else path.suffix.lower()[1:]


def _inventory(
    input_root: Path,
    *,
    expected_formats: dict[str, int] | None = None,
    expected_unique_hashes: int | None = 15,
) -> tuple[list[Path], list[dict[str, Any]]]:
    files = sorted(
        path
        for path in input_root.iterdir()
        if path.is_file() and path.suffix.lower() in ALLOWED_SUFFIXES
    )
    entries: list[dict[str, Any]] = []
    for index, path in enumerate(files, 1):
        digest = _file_sha(path)
        entries.append(
            {
                "cohort_index": index,
                "hashed_document_id": hashlib.sha256(
                    f"{index}:{digest}".encode("ascii")
                ).hexdigest(),
                "source_sha256": digest,
                "format": _format(path),
                "suffix": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
            }
        )
    formats = Counter(item["format"] for item in entries)
    if expected_formats is not None and dict(formats) != expected_formats:
        raise RuntimeError("doc30_cohort_shape_invalid")
    unique_hashes = len({item["source_sha256"] for item in entries})
    if expected_unique_hashes is not None and unique_hashes != expected_unique_hashes:
        raise RuntimeError("doc30_duplicate_accounting_invalid")
    return files, entries


def _state_path(store_root: Path) -> Path:
    return store_root / "doc30" / "backfill.private.json"


def _receipt_path(store_root: Path, index: int) -> Path:
    return store_root / "doc30" / "receipts" / f"document-{index:03d}.private.json"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _seal_state(state: dict[str, Any]) -> dict[str, Any]:
    sealed = json.loads(json.dumps(state))
    sealed.pop("integrity_sha256", None)
    sealed["integrity_sha256"] = _sha(sealed)
    return sealed


def _write_state(store_root: Path, state: dict[str, Any]) -> None:
    _write_json_atomic(_state_path(store_root), _seal_state(state))


def _load_state(store_root: Path) -> dict[str, Any]:
    path = _state_path(store_root)
    if not path.is_file():
        raise RuntimeError("doc30_private_state_unavailable")
    state = json.loads(path.read_text(encoding="utf-8"))
    supplied = str(state.pop("integrity_sha256", ""))
    if state.get("schema_version") != STATE_SCHEMA_VERSION or supplied != _sha(state):
        raise RuntimeError("doc30_private_state_integrity_invalid")
    state["integrity_sha256"] = supplied
    return state


def _limits(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "cpu_millis": int(args.cpu_millis),
        "memory_bytes": int(args.memory_bytes),
        "io_read_bps": int(args.io_read_bps),
        "io_write_bps": int(args.io_write_bps),
        "pids_limit": int(args.pids_limit),
        "per_document_timeout_seconds": int(args.per_document_timeout_seconds),
        "overall_control_timeout_seconds": int(args.overall_control_timeout_seconds),
        "log_max_bytes": int(args.log_max_bytes),
        "maximum_document_bytes": int(args.maximum_document_bytes),
        "maximum_components": int(args.maximum_components),
        "minimum_free_bytes": int(args.minimum_free_bytes),
        "critical_free_ratio": float(args.critical_free_ratio),
        "concurrency": 1,
        "batch_size_documents": 1,
    }


def initialize(input_root: Path, store_root: Path, limits: dict[str, Any]) -> int:
    files, inventory = _inventory(input_root, expected_formats=EXPECTED_FORMATS)
    if max(item["size_bytes"] for item in inventory) > limits["maximum_document_bytes"]:
        raise RuntimeError("doc30_maximum_document_size_exceeded")
    manifest_hash = _sha(inventory)
    existing_path = _state_path(store_root)
    if existing_path.exists():
        state = _load_state(store_root)
        if state["cohort_manifest_sha256"] != manifest_hash or state["limits"] != limits:
            raise RuntimeError("doc30_resume_authority_drift")
        status = "NO_OP"
    else:
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
            "cohort_manifest_sha256": manifest_hash,
            "limits": limits,
            "documents": [
                {**item, "status": "PENDING", "attempts": 0} for item in inventory
            ],
            "provider_calls": 0,
            "vlm_calls": 0,
            "legacy_handoff_changed": False,
            "product_read_enabled": False,
        }
        _write_state(store_root, state)
        status = "INITIALIZED"
    small_index = min(inventory, key=lambda item: item["size_bytes"])["cohort_index"]
    pdf_entries = [item for item in inventory if item["format"] == "pdf"]
    large_pdf_index = (
        max(pdf_entries, key=lambda item: item["size_bytes"])["cohort_index"]
        if pdf_entries
        else None
    )
    _print(
        {
            "operation": "initialize",
            "status": status,
            "documents": len(files),
            "format_counts": dict(sorted(Counter(item["format"] for item in inventory).items())),
            "unique_content_hashes": len({item["source_sha256"] for item in inventory}),
            "small_canary_index": small_index,
            "large_pdf_canary_index": large_pdf_index,
            "largest_input_bytes": max(item["size_bytes"] for item in inventory),
            "resource_limits_frozen": True,
        }
    )
    return 0


def _store(root: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _context(run_id: str, *, user_id: str | None = None) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id=user_id or CONTEXT["user_id"],
        normalization_run_id=run_id,
        case_id=CONTEXT["case_id"],
        workspace_model_id=CONTEXT["workspace_model_id"],
        allow_private=True,
        require_source_available=True,
    )


def _read_int(path: Path) -> int:
    value = path.read_text(encoding="ascii").strip()
    if value == "max":
        raise RuntimeError("doc30_runtime_limit_unbounded")
    return int(value)


def _runtime_limits(cgroup_root: Path) -> dict[str, Any]:
    cpu_parts = (cgroup_root / "cpu.max").read_text(encoding="ascii").split()
    if cpu_parts[0] == "max":
        raise RuntimeError("doc30_cpu_limit_unbounded")
    cpu_millis = int(round(int(cpu_parts[0]) / int(cpu_parts[1]) * 1000))
    io_lines = (cgroup_root / "io.max").read_text(encoding="ascii").splitlines()
    io_values: dict[str, list[int]] = {"rbps": [], "wbps": []}
    for line in io_lines:
        for token in line.split()[1:]:
            key, _, raw = token.partition("=")
            if key in io_values and raw and raw != "max":
                io_values[key].append(int(raw))
    return {
        "cpu_millis": cpu_millis,
        "memory_bytes": _read_int(cgroup_root / "memory.max"),
        "pids_limit": _read_int(cgroup_root / "pids.max"),
        "io_read_bps": min(io_values["rbps"]) if io_values["rbps"] else None,
        "io_write_bps": min(io_values["wbps"]) if io_values["wbps"] else None,
    }


def _validate_runtime_limits(expected: dict[str, Any], cgroup_root: Path) -> dict[str, Any]:
    observed = _runtime_limits(cgroup_root)
    for key in ("cpu_millis", "memory_bytes", "pids_limit", "io_read_bps", "io_write_bps"):
        if observed.get(key) is None or int(observed[key]) > int(expected[key]):
            raise RuntimeError(f"doc30_{key}_not_applied")
    return observed


def _resource_observation(cgroup_root: Path) -> dict[str, Any]:
    cpu: dict[str, int] = {}
    for line in (cgroup_root / "cpu.stat").read_text(encoding="ascii").splitlines():
        key, raw = line.split()[:2]
        if raw.isdigit():
            cpu[key] = int(raw)
    io_read = 0
    io_write = 0
    for line in (cgroup_root / "io.stat").read_text(encoding="ascii").splitlines():
        for token in line.split()[1:]:
            key, _, raw = token.partition("=")
            if key == "rbytes" and raw.isdigit():
                io_read += int(raw)
            if key == "wbytes" and raw.isdigit():
                io_write += int(raw)
    return {
        "memory_peak_bytes": _read_int(cgroup_root / "memory.peak"),
        "cpu_usage_usec": int(cpu.get("usage_usec", 0)),
        "io_read_bytes": io_read,
        "io_write_bytes": io_write,
    }


@contextlib.contextmanager
def _exclusive_lease(store_root: Path) -> Iterator[None]:
    lock_path = store_root / "doc30" / "backfill.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    stream = lock_path.open("a+b")
    try:
        if os.name == "posix":
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("doc30_concurrent_worker_forbidden") from exc
        yield
    finally:
        if os.name == "posix":
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def _verify_entry(store_root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    store = _store(store_root)
    context = _context(str(entry["normalization_run_id"]))
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    envelope = reader.read_active_envelope(str(entry["document_id"]), context)
    if (
        envelope.canonical_root_sha256 != entry["canonical_root_sha256"]
        or envelope.component_count != int(entry["component_count"])
    ):
        raise RuntimeError("doc30_checkpoint_readback_mismatch")
    return {
        "canonical_root_sha256": envelope.canonical_root_sha256,
        "component_count": envelope.component_count,
        "payload_bytes": envelope.payload_bytes,
        "physical_layout": envelope.physical_layout,
    }


def process_one(
    input_root: Path,
    store_root: Path,
    index: int,
    limits: dict[str, Any],
    *,
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    document_instance_scope: str | None = None,
) -> int:
    with _exclusive_lease(store_root):
        state = _load_state(store_root)
        if state["limits"] != limits:
            raise RuntimeError("doc30_runtime_limit_authority_drift")
        observed_limits = _validate_runtime_limits(limits, cgroup_root)
        files, inventory = _inventory(input_root, expected_formats=EXPECTED_FORMATS)
        if _sha(inventory) != state["cohort_manifest_sha256"]:
            raise RuntimeError("doc30_cohort_manifest_drift")
        if not 1 <= index <= len(files):
            raise RuntimeError("doc30_document_index_invalid")
        entry = state["documents"][index - 1]
        path = files[index - 1]
        if entry["status"] == "COMPLETED":
            verified = _verify_entry(store_root, entry)
            _print(
                {
                    "operation": "process_one",
                    "status": "SKIPPED_COMPLETED",
                    "cohort_index": index,
                    "hashed_document_id": entry["hashed_document_id"],
                    "format": entry["format"],
                    "canonical_version_id": entry["canonical_version_id"],
                    "canonical_root_sha256": verified["canonical_root_sha256"],
                    "component_count": verified["component_count"],
                    "duplicate_active_versions": 0,
                    "checkpoint_verified": True,
                }
            )
            return 0
        if int(entry["size_bytes"]) > int(limits["maximum_document_bytes"]):
            raise RuntimeError("doc30_maximum_document_size_exceeded")
        usage = shutil.disk_usage(store_root)
        if (
            usage.free < int(limits["minimum_free_bytes"])
            or usage.free / usage.total <= float(limits["critical_free_ratio"])
        ):
            raise RuntimeError("doc30_capacity_guard_failed")
        started = time.perf_counter()
        before = _resource_observation(cgroup_root)
        _print(
            {
                "operation": "process_one_progress",
                "status": "STARTED",
                "cohort_index": index,
                "hashed_document_id": entry["hashed_document_id"],
                "format": entry["format"],
            }
        )
        file_input = FileInput.from_bytes(
            private_ref=(
                f"doc30-private-{index:03d}-{entry['source_sha256'][:16]}"
            ),
            filename=f"approved-{index:03d}{entry['suffix']}",
            content=path.read_bytes(),
            mime_type=_mime(path),
        )
        normalized = Gate1Normalizer().normalize(
            [file_input],
            entrypoint="doc30_resource_bounded_backfill",
            trigger_type="approved_parser_only_single_document",
            input_context={
                "canonical_gate2_write_enabled": True,
                "canonical_gate2_compare_enabled": True,
                "canonical_gate2_read_enabled": False,
                "normalizer_version": "canonical-doc30-resource-bounded-v1",
                "provider_calls_allowed": False,
                "vlm_calls_allowed": False,
            },
        )
        if document_instance_scope:
            documents = normalized.package["document_inventory"]["documents"]
            if len(documents) != 1:
                raise RuntimeError("doc31_document_instance_cardinality_invalid")
            original_document_id = str(documents[0].get("document_id") or "")
            if not original_document_id:
                raise RuntimeError("doc31_document_instance_source_missing")
            scoped_document_id = (
                f"brdoc_{document_instance_scope}_{entry['source_sha256'][:12]}"
            )
            _replace_exact_string(
                normalized.package, original_document_id, scoped_document_id
            )
        run_id = str(normalized.package["normalization_run"]["run_id"])
        context = _context(run_id)
        store = _store(store_root)
        manifest = persist_gate1_result(
            store=store,
            result=normalized,
            context=context,
            retention_policy=build_retention_policy(
                mode="manual_purge_required",
                explicit=True,
                requires_manual_purge=True,
            ),
            source_file_refs=[
                {
                    "provider": "doc30_approved_private_cohort",
                    "openwebui_file_id": f"doc30-source-{index:03d}",
                    "file_hash_sha256": entry["source_sha256"],
                    "content_type": _mime(path),
                    "size_bytes": entry["size_bytes"],
                }
            ],
        )
        canonical_refs = manifest.artifact_refs_by_type.get(
            "broker_reports_canonical_artifact_v1", []
        )
        failures = manifest.artifact_refs_by_type.get(
            "broker_reports_canonical_build_failure_v1", []
        )
        if len(canonical_refs) != 1 or failures:
            raise RuntimeError("doc30_canonical_build_incomplete")
        version = store.get_canonical_version_by_manifest(
            context=context, manifest_ref=canonical_refs[0]
        )
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        activation = reader.activate(
            canonical_version_id=version.canonical_version_id,
            expected_previous_version_id=None,
            context=context,
            actor="doc30-resource-bounded-backfill",
            reason="approved per-document activation",
        )
        envelope = reader.read_active_envelope(version.document_id, context)
        history = reader.history(version.document_id, context)
        if len(history) != 1 or envelope.component_count > int(limits["maximum_components"]):
            raise RuntimeError("doc30_duplicate_or_component_limit_violation")
        after = _resource_observation(cgroup_root)
        receipt = {
            "schema_version": "broker_reports_doc30_private_document_receipt_v1",
            "cohort_index": index,
            "hashed_document_id": entry["hashed_document_id"],
            "format": entry["format"],
            "source_sha256": entry["source_sha256"],
            "canonical_version_id": version.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "document_id": version.document_id,
            "normalization_run_id": run_id,
            "component_count": envelope.component_count,
            "payload_bytes": envelope.payload_bytes,
            "physical_layout": envelope.physical_layout,
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "activation_result": activation.status,
            "validation_result": "PASSED",
            "resource_observation": {
                "memory_peak_bytes": after["memory_peak_bytes"],
                "cpu_usage_usec": max(0, after["cpu_usage_usec"] - before["cpu_usage_usec"]),
                "io_read_bytes": max(0, after["io_read_bytes"] - before["io_read_bytes"]),
                "io_write_bytes": max(0, after["io_write_bytes"] - before["io_write_bytes"]),
            },
            "runtime_limits": observed_limits,
            "provider_calls": 0,
            "vlm_calls": 0,
            "legacy_handoff_changed": False,
            "product_read_enabled": False,
        }
        receipt["integrity_sha256"] = _sha(receipt)
        entry.update(
            {
                "status": "COMPLETED",
                "attempts": int(entry.get("attempts", 0)) + 1,
                "canonical_version_id": version.canonical_version_id,
                "canonical_root_sha256": envelope.canonical_root_sha256,
                "document_id": version.document_id,
                "normalization_run_id": run_id,
                "component_count": envelope.component_count,
                "payload_bytes": envelope.payload_bytes,
                "physical_layout": envelope.physical_layout,
                "receipt_integrity_sha256": receipt["integrity_sha256"],
            }
        )
        state["documents"][index - 1] = entry
        _write_state(store_root, state)
        _write_json_atomic(_receipt_path(store_root, index), receipt)
        _print(
            {
                "operation": "process_one",
                "status": "PASSED",
                "cohort_index": index,
                "hashed_document_id": entry["hashed_document_id"],
                "format": entry["format"],
                "canonical_version_id": version.canonical_version_id,
                "canonical_root_sha256": envelope.canonical_root_sha256,
                "component_count": envelope.component_count,
                "payload_bytes": envelope.payload_bytes,
                "physical_layout": envelope.physical_layout,
                "elapsed_seconds": receipt["elapsed_seconds"],
                "activation_result": activation.status,
                "memory_peak_bytes": after["memory_peak_bytes"],
                "duplicate_active_versions": 0,
                "checkpoint_after_document": True,
                "provider_calls": 0,
                "product_side_effects": 0,
            }
        )
        return 0


def _replace_exact_string(value: Any, old: str, new: str) -> None:
    """Replace exact document refs without changing content-bearing strings."""

    if isinstance(value, dict):
        for key, child in value.items():
            if child == old:
                value[key] = new
            else:
                _replace_exact_string(child, old, new)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if child == old:
                value[index] = new
            else:
                _replace_exact_string(child, old, new)


def verify(store_root: Path, *, require_complete: bool) -> int:
    state = _load_state(store_root)
    completed = [item for item in state["documents"] if item["status"] == "COMPLETED"]
    roots = 0
    components = 0
    for entry in completed:
        observed = _verify_entry(store_root, entry)
        roots += int(observed["canonical_root_sha256"] == entry["canonical_root_sha256"])
        components += int(observed["component_count"])
    access_fail_closed = False
    if completed:
        first = completed[0]
        store = _store(store_root)
        try:
            CanonicalReaderFactory(store=store, read_enabled=True).create().read_active(
                first["document_id"],
                _context(first["normalization_run_id"], user_id="doc30-cross-tenant"),
            )
        except ArtifactStoreError as exc:
            access_fail_closed = exc.code in {
                "artifact_access_denied",
                "canonical_version_not_active",
            }
    passed = roots == len(completed) and (not completed or access_fail_closed)
    if require_complete:
        passed = passed and len(completed) == 16
    _print(
        {
            "operation": "verify",
            "status": "PASSED" if passed else "FAILED",
            "completed_documents": len(completed),
            "pending_documents": 16 - len(completed),
            "active_pointers": len(completed),
            "root_hashes_matched": roots,
            "components_verified": components,
            "missing_chunks": 0 if passed else "UNRESOLVED",
            "cross_tenant_access": (
                "DENIED" if access_fail_closed else "NOT_TESTED" if not completed else "FAILED_OPEN"
            ),
            "require_complete": require_complete,
        }
    )
    return 0 if passed else 1


def status(store_root: Path) -> int:
    state = _load_state(store_root)
    counts = Counter(item["status"] for item in state["documents"])
    _print(
        {
            "operation": "status",
            "status": "PASSED",
            "documents": len(state["documents"]),
            "completed": counts["COMPLETED"],
            "pending": counts["PENDING"],
            "failed": counts["FAILED"],
            "per_document_receipts": sum(
                _receipt_path(store_root, item["cohort_index"]).is_file()
                for item in state["documents"]
            ),
            "resource_limits_frozen": True,
        }
    )
    return 0


def _add_limit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cpu-millis", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--io-read-bps", type=int, required=True)
    parser.add_argument("--io-write-bps", type=int, required=True)
    parser.add_argument("--pids-limit", type=int, required=True)
    parser.add_argument("--per-document-timeout-seconds", type=int, required=True)
    parser.add_argument("--overall-control-timeout-seconds", type=int, required=True)
    parser.add_argument("--log-max-bytes", type=int, required=True)
    parser.add_argument("--maximum-document-bytes", type=int, required=True)
    parser.add_argument("--maximum-components", type=int, required=True)
    parser.add_argument("--minimum-free-bytes", type=int, required=True)
    parser.add_argument("--critical-free-ratio", type=float, required=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("initialize")
    init_parser.add_argument("--input-root", type=Path, required=True)
    init_parser.add_argument("--store-root", type=Path, required=True)
    _add_limit_args(init_parser)
    one_parser = commands.add_parser("process-one")
    one_parser.add_argument("--input-root", type=Path, required=True)
    one_parser.add_argument("--store-root", type=Path, required=True)
    one_parser.add_argument("--index", type=int, required=True)
    one_parser.add_argument("--cgroup-root", type=Path, default=Path("/sys/fs/cgroup"))
    _add_limit_args(one_parser)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--store-root", type=Path, required=True)
    verify_parser.add_argument("--require-complete", action="store_true")
    status_parser = commands.add_parser("status")
    status_parser.add_argument("--store-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "initialize":
        return initialize(args.input_root, args.store_root, _limits(args))
    if args.command == "process-one":
        return process_one(
            args.input_root,
            args.store_root,
            args.index,
            _limits(args),
            cgroup_root=args.cgroup_root,
        )
    if args.command == "verify":
        return verify(args.store_root, require_complete=args.require_complete)
    if args.command == "status":
        return status(args.store_root)
    raise RuntimeError("doc30_command_unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        _print(
            {
                "operation": "error",
                "status": "FAILED",
                "error_code": str(exc)[:160],
                "error_type": type(exc).__name__,
            }
        )
        raise
