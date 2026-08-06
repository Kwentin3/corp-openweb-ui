"""Consumer-specific Gate 2 canonical compatibility contracts.

This module owns only Wave 0 compatibility projections and the frozen migration
inventory. It does not select product consumers, enable a global read valve or
perform legacy fallback.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStoreError
from .canonical_artifact import (
    CANONICAL_ARTIFACT_SCHEMA_VERSION,
    assess_canonical_completeness,
    validate_canonical_artifact,
)
from .canonical_store import CanonicalReadEnvelope, CanonicalReaderFactory


CANONICAL_COMPATIBILITY_CONTRACT_VERSION = (
    "broker_reports_canonical_consumer_compatibility_v1"
)
CANONICAL_OK = "CANONICAL_OK"
CANONICAL_INCOMPLETE = "CANONICAL_INCOMPLETE"
CANONICAL_CONFLICT = "CANONICAL_CONFLICT"
CANONICAL_ACCESS_DENIED = "CANONICAL_ACCESS_DENIED"
CANONICAL_VERSION_UNSUPPORTED = "CANONICAL_VERSION_UNSUPPORTED"
CANONICAL_STORAGE_FAILURE = "CANONICAL_STORAGE_FAILURE"

COMPATIBILITY_STATUSES = frozenset(
    {
        CANONICAL_OK,
        CANONICAL_INCOMPLETE,
        CANONICAL_CONFLICT,
        CANONICAL_ACCESS_DENIED,
        CANONICAL_VERSION_UNSUPPORTED,
        CANONICAL_STORAGE_FAILURE,
    }
)

FACTORY_REQUIRED = (
    "Every compatibility read must enter through its consumer-specific "
    "factory and CanonicalReaderFactory.create"
)
FORBIDDEN = (
    "Global canonical read flags, direct ArtifactStore/SQLite/payload reads, "
    "private evidence, parser/cropper/provider reads, financial semantics and "
    "silent legacy fallback are forbidden inside compatibility adapters"
)


@dataclass(frozen=True)
class ConsumerSurface:
    consumer_id: str
    source_file: str
    consumer_class: str
    runtime_purpose: str
    current_legacy_reads: tuple[str, ...]
    side_effects: tuple[str, ...]
    access_context: str
    canonical_equivalent: tuple[str, ...]
    compatibility_adapter: str | None
    migration_wave: str
    tests: tuple[str, ...]
    rollback: str
    legacy_status: str
    legacy_deletion_condition: str


@dataclass(frozen=True)
class CompatibilityMapping:
    consumer_id: str
    source_file: str
    migration_wave: str
    feature_flag: str
    legacy_contract_version: str
    canonical_contract_version: str
    compatibility_adapter_version: str
    output_contract_version: str
    canonical_queries: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalCompatibilityResult:
    consumer_id: str
    migration_wave: str
    compatibility_status: str
    output: dict[str, Any] | None
    error_code: str | None
    telemetry: dict[str, Any]


@dataclass
class CanonicalReadLedger:
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event: dict[str, Any]) -> None:
        self.events.append(dict(event))

    def record_rollback(self, *, consumer_id: str, migration_wave: str) -> None:
        self.events.append(
            {
                "schema_version": "canonical_consumer_read_telemetry_v1",
                "consumer_id": consumer_id,
                "migration_wave": migration_wave,
                "canonical_read_attempts": 0,
                "canonical_read_success": 0,
                "canonical_read_blocked": 0,
                "canonical_read_latency_ms": 0.0,
                "canonical_payload_bytes": 0,
                "canonical_chunks_read": 0,
                "canonical_schema_version": None,
                "canonical_version_id_hash": None,
                "compatibility_status": None,
                "rollback_events": 1,
            }
        )


class _ProjectionIncomplete(RuntimeError):
    pass


class _CanonicalCompatibilityAdapter:
    mapping: CompatibilityMapping

    def __init__(
        self,
        *,
        reader,
        ledger: CanonicalReadLedger,
    ) -> None:
        self._reader = reader
        self._ledger = ledger

    def read_active(
        self, *, document_id: str, context: ArtifactAccessContext
    ) -> CanonicalCompatibilityResult:
        started = time.perf_counter()
        try:
            envelope = self._reader.read_active_envelope(document_id, context)
        except ArtifactStoreError as exc:
            return self._blocked(
                status=_status_for_store_error(exc.code),
                error_code=exc.code,
                started=started,
            )
        integrity_status, validation_error = classify_consumer_artifact(
            envelope.artifact
        )
        if validation_error:
            return self._blocked(
                status=integrity_status,
                error_code=validation_error,
                started=started,
                envelope=envelope,
            )
        try:
            output = self._project(envelope)
        except _ProjectionIncomplete as exc:
            return self._blocked(
                status=CANONICAL_INCOMPLETE,
                error_code=str(exc),
                started=started,
                envelope=envelope,
            )
        event = _telemetry_event(
            mapping=self.mapping,
            status=CANONICAL_OK,
            started=started,
            envelope=envelope,
            success=True,
        )
        self._ledger.append(event)
        return CanonicalCompatibilityResult(
            consumer_id=self.mapping.consumer_id,
            migration_wave=self.mapping.migration_wave,
            compatibility_status=CANONICAL_OK,
            output=output,
            error_code=None,
            telemetry=event,
        )

    def _blocked(
        self,
        *,
        status: str,
        error_code: str,
        started: float,
        envelope: CanonicalReadEnvelope | None = None,
    ) -> CanonicalCompatibilityResult:
        event = _telemetry_event(
            mapping=self.mapping,
            status=status,
            started=started,
            envelope=envelope,
            success=False,
        )
        self._ledger.append(event)
        return CanonicalCompatibilityResult(
            consumer_id=self.mapping.consumer_id,
            migration_wave=self.mapping.migration_wave,
            compatibility_status=status,
            output=None,
            error_code=error_code,
            telemetry=event,
        )

    def _project(self, envelope: CanonicalReadEnvelope) -> dict[str, Any]:
        raise NotImplementedError


def _summary(artifact: dict[str, Any]) -> dict[str, Any]:
    containers = list(artifact.get("containers") or [])
    nodes = list(artifact.get("nodes") or [])
    provenance = list(artifact.get("provenance") or [])
    issues = list(artifact.get("issues") or [])
    ordered_ids = [str(item.get("container_id") or "") for item in containers] + [
        str(item.get("node_id") or "") for item in nodes
    ]
    return {
        "documents_returned": 1,
        "containers_returned": len(containers),
        "nodes_returned": len(nodes),
        "tables_returned": sum(item.get("node_type") == "TABLE" for item in nodes),
        "ordering_sha256": hashlib.sha256(
            json.dumps(ordered_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "provenance_records": len(provenance),
        "provenance_available": bool(provenance),
        "issues_total": len(issues),
        "conflicts_total": sum(item.get("issue_type") == "CONFLICT" for item in issues),
        "ambiguities_total": sum(
            item.get("issue_type") == "AMBIGUITY" for item in issues
        ),
    }


class Gate1ArtifactStoreCanonicalAdapter(_CanonicalCompatibilityAdapter):
    mapping: CompatibilityMapping

    def _project(self, envelope: CanonicalReadEnvelope) -> dict[str, Any]:
        return {
            "schema_version": self.mapping.output_contract_version,
            "artifact_type": "broker_reports_canonical_artifact_v1",
            "validation_status": "validated",
            "handoff_status": "canonical_active",
            "handoff_mode": "canonical_reader_v1",
            "canonical_version_number": envelope.canonical_version_number,
            "physical_layout": envelope.physical_layout,
            **_summary(envelope.artifact),
        }


class PdfCompactCanonicalAdapter(_CanonicalCompatibilityAdapter):
    mapping: CompatibilityMapping

    def _project(self, envelope: CanonicalReadEnvelope) -> dict[str, Any]:
        artifact = envelope.artifact
        if (artifact.get("source") or {}).get("source_format") != "pdf":
            raise _ProjectionIncomplete("pdf_canonical_source_required")
        summary = _summary(artifact)
        return {
            "schema_version": self.mapping.output_contract_version,
            "source_format": "pdf",
            "page_count": sum(
                item.get("container_type") == "PAGE"
                for item in artifact.get("containers") or []
            ),
            "coverage_status": (
                "complete" if summary["provenance_available"] else "incomplete"
            ),
            **summary,
        }


class LocalPdfCompactResearchCanonicalAdapter(PdfCompactCanonicalAdapter):
    mapping: CompatibilityMapping

    def _project(self, envelope: CanonicalReadEnvelope) -> dict[str, Any]:
        output = super()._project(envelope)
        generic_projection = render_neutral_canonical_projection(envelope.artifact)
        if not generic_projection.strip():
            raise _ProjectionIncomplete("canonical_pdf_projection_empty")
        output.update(
            {
                "schema_version": self.mapping.output_contract_version,
                "proof_status": "passed",
                "canonical_root_sha256": envelope.canonical_root_sha256,
                "canonical_version_number": envelope.canonical_version_number,
                "physical_layout": envelope.physical_layout,
                "generic_projection": generic_projection,
                "generic_projection_sha256": hashlib.sha256(
                    generic_projection.encode("utf-8")
                ).hexdigest(),
                "generic_projection_characters": len(generic_projection),
            }
        )
        return output


def render_neutral_canonical_projection(artifact: dict[str, Any]) -> str:
    """Render a validated CanonicalArtifactV1 without reopening source evidence.

    This format-neutral helper is a diagnostic completeness proof owned by the
    compatibility boundary. It is not a Gate 3 runtime,
    prompt, provider surface, or financial interpretation authority.
    """

    validation = validate_canonical_artifact(artifact)
    if not validation["passed"]:
        raise _ProjectionIncomplete("canonical_projection_source_invalid")
    containers = list(artifact.get("containers") or [])
    nodes = list(artifact.get("nodes") or [])
    root_ref = str(artifact.get("root_container_ref") or "")
    by_id = {str(item.get("container_id") or ""): item for item in containers}
    root = by_id.get(root_ref)
    if root is None:
        raise _ProjectionIncomplete("canonical_projection_root_required")
    by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for container in containers:
        by_parent.setdefault(container.get("parent_container_ref"), []).append(
            container
        )
    by_container: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        by_container.setdefault(str(node.get("container_ref") or ""), []).append(node)
    represented_issue_refs: set[str] = set()
    lines: list[str] = []

    def append_nodes(container_ref: str) -> None:
        for node in sorted(
            by_container.get(container_ref, []),
            key=lambda value: int(value.get("order") or 0),
        ):
            node_type = str(node.get("node_type") or "")
            content = node.get("content") or {}
            represented_issue_refs.update(
                str(value) for value in node.get("issue_refs") or []
            )
            if node_type in {"PAGE_BREAK", "SHEET_BREAK"}:
                continue
            if node_type in {"HEADING", "TEXT", "NOTE"}:
                lines.extend([f"[{node_type}]", str(content.get("text") or "")])
            elif node_type == "LIST":
                lines.append("[LIST]")
                for item in content.get("items") or []:
                    prefix = "1." if item.get("ordered") else "-"
                    level = max(0, int(item.get("level") or 0))
                    lines.append(
                        f"{'  ' * level}{prefix} {str(item.get('text') or '')}"
                    )
            elif node_type == "TABLE":
                lines.append("[TABLE]")
                title = content.get("title")
                if title is not None:
                    lines.append(str(title))
                for row in _neutral_table_rows(content):
                    lines.append(
                        "\t".join("" if value is None else str(value) for value in row)
                    )
                for note in content.get("notes") or []:
                    lines.extend(["[NOTE]", str(note)])
            elif node_type in {"CONFLICT", "AMBIGUITY"}:
                lines.extend([f"[{node_type}]", str(content.get("summary") or "")])
            else:
                raise _ProjectionIncomplete(
                    "canonical_projection_node_type_unsupported"
                )

    def append_container(container: dict[str, Any]) -> None:
        lines.append(_neutral_container_marker(container))
        container_ref = str(container.get("container_id") or "")
        append_nodes(container_ref)
        for child in sorted(
            by_parent.get(container_ref, []),
            key=lambda value: int(value.get("order") or 0),
        ):
            append_container(child)

    append_container(root)
    remaining_issues = [
        issue
        for issue in artifact.get("issues") or []
        if str(issue.get("issue_id") or "") not in represented_issue_refs
    ]
    if remaining_issues:
        lines.append("[ISSUES]")
        for issue in remaining_issues:
            lines.append(
                "{0}/{1}: {2}".format(
                    str(issue.get("issue_type") or ""),
                    str(issue.get("severity") or ""),
                    str(issue.get("summary") or ""),
                )
            )
    projection = "\n".join(lines).rstrip() + "\n"
    if not projection.strip():
        raise _ProjectionIncomplete("canonical_projection_empty")
    return projection


def _neutral_container_marker(container: dict[str, Any]) -> str:
    container_type = str(container.get("container_type") or "")
    metadata = container.get("metadata") or {}
    if container_type == "PAGE":
        return f"[PAGE] {int(metadata.get('page_number') or 0)}"
    if container_type == "SECTION":
        return f"[SECTION] {int(metadata.get('section_index') or 0)}"
    if container_type == "SHEET":
        label = metadata.get("sheet_name")
        if label is None:
            label = int(metadata.get("sheet_index") or 0)
        return f"[SHEET] {label}"
    return f"[{container_type}]"


def _neutral_table_rows(content: dict[str, Any]) -> list[list[Any]]:
    header = content.get("header") or []
    rows = content.get("rows") or []
    if header or rows:
        return [*([list(header)] if header else []), *(list(row) for row in rows)]
    cells = list(content.get("cells") or [])
    if not cells:
        return []
    maximum_row = max(int(cell.get("row") or 0) for cell in cells)
    maximum_column = max(int(cell.get("column") or 0) for cell in cells)
    matrix: list[list[Any]] = [
        [None for _ in range(maximum_column)] for _ in range(maximum_row)
    ]
    for cell in cells:
        row = int(cell.get("row") or 0)
        column = int(cell.get("column") or 0)
        if row < 1 or column < 1:
            raise _ProjectionIncomplete("canonical_projection_cell_coordinate_invalid")
        value = cell.get("displayed_value")
        if value is None:
            value = cell.get("cached_value")
        if value is None:
            value = cell.get("value")
        if value is None:
            value = cell.get("raw_value")
        matrix[row - 1][column - 1] = value
    return matrix


class _ConsumerAdapterFactory:
    """Bind one explicit compatibility mapping to the sole public reader."""

    adapter_type: type[_CanonicalCompatibilityAdapter]
    mapping: CompatibilityMapping

    def __init__(
        self,
        *,
        store,
        enabled: bool,
        ledger: CanonicalReadLedger | None = None,
    ) -> None:
        self.store = store
        self.enabled = enabled
        self.ledger = ledger or CanonicalReadLedger()

    def create(self) -> _CanonicalCompatibilityAdapter:
        reader = CanonicalReaderFactory(
            store=self.store, read_enabled=self.enabled
        ).create()
        adapter = self.adapter_type(reader=reader, ledger=self.ledger)
        adapter.mapping = self.mapping
        return adapter


GATE1_ARTIFACT_STORE_MAPPING = CompatibilityMapping(
    consumer_id="gate1_artifact_store_test",
    source_file="tests/test_broker_reports_gate1_artifact_store.py",
    migration_wave="WAVE_0_TEST",
    feature_flag="CANONICAL_READ_GATE1_ARTIFACT_STORE_TEST",
    legacy_contract_version="gate2_handoff_v0",
    canonical_contract_version=CANONICAL_ARTIFACT_SCHEMA_VERSION,
    compatibility_adapter_version="gate1_artifact_store_canonical_adapter_v1",
    output_contract_version="gate1_artifact_store_compatibility_output_v1",
    canonical_queries=("read_active_envelope", "read manifest"),
)

PDF_COMPACT_CANONICAL_MAPPING = CompatibilityMapping(
    consumer_id="pdf_compact_canonical_test",
    source_file="tests/test_broker_reports_pdf_compact_canonical.py",
    migration_wave="WAVE_0_TEST",
    feature_flag="CANONICAL_READ_PDF_COMPACT_CANONICAL_TEST",
    legacy_contract_version="gate2_handoff_v0",
    canonical_contract_version=CANONICAL_ARTIFACT_SCHEMA_VERSION,
    compatibility_adapter_version="pdf_compact_canonical_adapter_v1",
    output_contract_version="pdf_compact_compatibility_output_v1",
    canonical_queries=(
        "read_active_envelope",
        "read ordered containers",
        "read ordered nodes",
        "read provenance",
        "read issues",
    ),
)

LOCAL_PDF_COMPACT_RESEARCH_MAPPING = CompatibilityMapping(
    consumer_id="local_pdf_compact_canonical_proof",
    source_file="scripts/local_pdf_compact_canonical_proof.py",
    migration_wave="WAVE_0_RESEARCH",
    feature_flag="CANONICAL_READ_LOCAL_PDF_COMPACT_CANONICAL_PROOF",
    legacy_contract_version="broker_reports_pdf_compact_canonical_controlled_proof_v1",
    canonical_contract_version=CANONICAL_ARTIFACT_SCHEMA_VERSION,
    compatibility_adapter_version="local_pdf_compact_research_canonical_adapter_v2",
    output_contract_version="local_pdf_compact_research_output_v2",
    canonical_queries=(
        "read_active_envelope",
        "read ordered containers",
        "read ordered nodes",
        "read provenance",
        "read issues",
    ),
)


class Gate1ArtifactStoreCanonicalAdapterFactory(_ConsumerAdapterFactory):
    adapter_type = Gate1ArtifactStoreCanonicalAdapter
    mapping = GATE1_ARTIFACT_STORE_MAPPING


class PdfCompactCanonicalAdapterFactory(_ConsumerAdapterFactory):
    adapter_type = PdfCompactCanonicalAdapter
    mapping = PDF_COMPACT_CANONICAL_MAPPING


class LocalPdfCompactResearchCanonicalAdapterFactory(_ConsumerAdapterFactory):
    adapter_type = LocalPdfCompactResearchCanonicalAdapter
    mapping = LOCAL_PDF_COMPACT_RESEARCH_MAPPING


WAVE0_MAPPINGS = (
    GATE1_ARTIFACT_STORE_MAPPING,
    PDF_COMPACT_CANONICAL_MAPPING,
    LOCAL_PDF_COMPACT_RESEARCH_MAPPING,
)


def _surface(
    consumer_id: str,
    source_file: str,
    consumer_class: str,
    purpose: str,
    legacy_reads: tuple[str, ...],
    side_effects: tuple[str, ...],
    access_context: str,
    canonical_equivalent: tuple[str, ...],
    adapter: str | None,
    tests: tuple[str, ...],
) -> ConsumerSurface:
    return ConsumerSurface(
        consumer_id=consumer_id,
        source_file=source_file,
        consumer_class=consumer_class,
        runtime_purpose=purpose,
        current_legacy_reads=legacy_reads,
        side_effects=side_effects,
        access_context=access_context,
        canonical_equivalent=canonical_equivalent,
        compatibility_adapter=adapter,
        migration_wave=consumer_class,
        tests=tests,
        rollback="consumer flag off restores the unchanged legacy authority; no adapter fallback",
        legacy_status=(
            "DEPRECATED_FOR_CONSUMER_READ_RETAINED_FOR_REGRESSION"
            if consumer_class == "WAVE_0_TEST"
            else "RETAINED"
        ),
        legacy_deletion_condition=(
            "all assigned waves passed, observation and retention windows closed, "
            "and imports/tests/contracts/persisted-data/audit dependencies are zero"
        ),
    )


FROZEN_CONSUMER_SURFACES = (
    _surface(
        "artifact_schema_registry",
        "broker_reports_gate1/artifact_models.py",
        "MIGRATION_ONLY",
        "persisted artifact type registry",
        ("gate2_handoff_v0 type",),
        (),
        "not a read path",
        ("canonical artifact/version/component types",),
        None,
        ("test_broker_reports_gate1_artifact_store.py",),
    ),
    _surface(
        "legacy_handoff_producer",
        "broker_reports_gate1/gate2_handoff.py",
        "LEGACY_FALLBACK",
        "authoritative compatibility producer",
        ("gate2_handoff_v0 publication",),
        ("writes product artifacts",),
        "trusted product ArtifactAccessContext",
        ("retained until Wave 4",),
        None,
        ("test_broker_reports_gate1_artifact_store.py",),
    ),
    _surface(
        "gate2_input_readiness",
        "broker_reports_gate1/gate2_input_readiness.py",
        "WAVE_2_BACKGROUND_PRODUCT",
        "product source-fact readiness",
        ("legacy handoff refs and source units",),
        ("changes product eligibility decision",),
        "trusted product ArtifactAccessContext",
        ("ordered containers/nodes/tables/provenance/issues",),
        None,
        ("current readiness tests",),
    ),
    _surface(
        "gate2_source_fact_runtime",
        "broker_reports_gate1/gate2_source_fact_runtime.py",
        "WAVE_2_BACKGROUND_PRODUCT",
        "background semantic extraction input",
        ("legacy readiness package",),
        ("writes product artifacts and can call provider",),
        "trusted product ArtifactAccessContext",
        ("future Gate 3 projection input",),
        None,
        ("current source-fact runtime tests",),
    ),
    _surface(
        "gate1_primary_pipe",
        "openwebui_actions/broker_reports_gate1_pipe.py",
        "WAVE_3_PRIMARY_PRODUCT",
        "primary user-facing orchestration",
        ("legacy handoff required-type accounting",),
        ("user response and product artifact writes",),
        "authenticated OpenWebUI context",
        ("consumer-specific active canonical read",),
        None,
        ("test_broker_reports_gate1_pipe_bundle.py",),
    ),
    _surface(
        "gate1_primary_pipe_bundle",
        "openwebui_actions/broker_reports_gate1_pipe_bundled.py",
        "WAVE_3_PRIMARY_PRODUCT",
        "generated primary product bundle",
        ("bundled legacy handoff accounting",),
        ("user response and product artifact writes",),
        "authenticated OpenWebUI context",
        ("generated parity with maintained pipe",),
        None,
        ("test_broker_reports_gate1_pipe_bundle.py",),
    ),
    _surface(
        "domain_source_fact_bundle",
        "openwebui_actions/broker_reports_gate2_domain_source_fact_pipe_bundled.py",
        "WAVE_3_PRIMARY_PRODUCT",
        "generated domain product route",
        ("bundled legacy runtime",),
        ("provider calls and product writes",),
        "authenticated OpenWebUI context",
        ("future canonical-backed domain projection",),
        None,
        ("test_broker_reports_gate2_pipe_bundle.py",),
    ),
    _surface(
        "source_fact_bundle",
        "openwebui_actions/broker_reports_gate2_source_fact_pipe_bundled.py",
        "WAVE_3_PRIMARY_PRODUCT",
        "generated source-fact product route",
        ("bundled legacy runtime",),
        ("provider calls and product writes",),
        "authenticated OpenWebUI context",
        ("future canonical-backed source-fact projection",),
        None,
        ("test_broker_reports_gate2_pipe_bundle.py",),
    ),
    _surface(
        "live_retention_smoke",
        "scripts/live_artifactstore_retention_smoke.py",
        "MIGRATION_ONLY",
        "operator retention smoke",
        ("legacy artifact type assertion",),
        ("upload, chat, delete and function update",),
        "live operator session",
        ("separate future read-only inspector required",),
        None,
        ("operator smoke proof",),
    ),
    _surface(
        "live_case_group_eligibility",
        "scripts/live_case_group_eligibility_rerun.py",
        "WAVE_2_BACKGROUND_PRODUCT",
        "operator eligibility rerun",
        ("legacy handoff payload",),
        ("upload, chat, delete and function update",),
        "live operator session",
        ("canonical readiness projection",),
        None,
        ("operator rerun proof",),
    ),
    _surface(
        "live_case_group_process_false",
        "scripts/live_case_group_process_false_gate1_run.py",
        "WAVE_2_BACKGROUND_PRODUCT",
        "operator process-false run",
        ("legacy handoff metadata",),
        ("upload, chat and delete",),
        "live operator session",
        ("canonical manifest and issues",),
        None,
        ("operator process-false proof",),
    ),
    _surface(
        "live_pdf_table_operator",
        "scripts/live_pdf_table_intake_gate1_operator_proof.py",
        "WAVE_2_BACKGROUND_PRODUCT",
        "operator PDF table proof",
        ("legacy handoff presence",),
        ("upload, chat, download, write and delete",),
        "live operator session",
        ("canonical partial table/provenance reads",),
        None,
        ("operator PDF proof",),
    ),
    _surface(
        "live_private_intake_smoke",
        "scripts/live_process_false_private_intake_smoke.py",
        "WAVE_2_BACKGROUND_PRODUCT",
        "private intake smoke",
        ("legacy artifact counts",),
        ("upload, chat and delete",),
        "live operator session",
        ("canonical manifest and access behavior",),
        None,
        ("operator private-intake proof",),
    ),
    _surface(
        "local_pdf_compact_canonical_proof",
        "scripts/local_pdf_compact_canonical_proof.py",
        "WAVE_0_RESEARCH",
        "local non-product PDF proof",
        ("legacy handoff payload",),
        ("writes only ignored local research evidence",),
        "explicit local trusted context",
        ("active PDF canonical artifact summary",),
        "LocalPdfCompactResearchCanonicalAdapterFactory",
        ("test_broker_reports_canonical_consumer_compatibility.py",),
    ),
    _surface(
        "gate1_artifact_store_test",
        "tests/test_broker_reports_gate1_artifact_store.py",
        "WAVE_0_TEST",
        "legacy store regression plus canonical consumer",
        ("legacy handoff payload and refs",),
        ("isolated temporary store only",),
        "isolated synthetic test context",
        ("active canonical manifest/version summary",),
        "Gate1ArtifactStoreCanonicalAdapterFactory",
        (
            "test_broker_reports_gate1_artifact_store.py",
            "test_broker_reports_canonical_consumer_compatibility.py",
        ),
    ),
    _surface(
        "pdf_compact_canonical_test",
        "tests/test_broker_reports_pdf_compact_canonical.py",
        "WAVE_0_TEST",
        "PDF compact compatibility regression",
        ("legacy authority assertion",),
        ("isolated temporary store only",),
        "isolated synthetic test context",
        ("active PDF containers/nodes/tables/provenance",),
        "PdfCompactCanonicalAdapterFactory",
        (
            "test_broker_reports_pdf_compact_canonical.py",
            "test_broker_reports_canonical_consumer_compatibility.py",
        ),
    ),
)


def classify_consumer_artifact(
    artifact: dict[str, Any],
) -> tuple[str, str | None]:
    if artifact.get("schema_version") != CANONICAL_ARTIFACT_SCHEMA_VERSION:
        return (
            CANONICAL_VERSION_UNSUPPORTED,
            "canonical_schema_version_unsupported",
        )
    provenance_ids = {
        str(item.get("provenance_id") or "")
        for item in artifact.get("provenance") or []
    }
    for collection in (
        artifact.get("containers") or [],
        artifact.get("nodes") or [],
        artifact.get("issues") or [],
    ):
        for item in collection:
            refs = [str(value) for value in item.get("source_refs") or []]
            if not refs or any(ref not in provenance_ids for ref in refs):
                return CANONICAL_INCOMPLETE, "canonical_provenance_unresolved"
    for issue in artifact.get("issues") or []:
        if issue.get("issue_type") == "CONFLICT" and issue.get("severity") in {
            "blocking",
            "critical",
        }:
            return CANONICAL_CONFLICT, "canonical_critical_conflict"
        if issue.get("issue_type") == "PARTIAL" and issue.get("severity") in {
            "blocking",
            "critical",
        }:
            return (
                CANONICAL_INCOMPLETE,
                "canonical_required_information_missing",
            )
    completeness = assess_canonical_completeness(artifact)
    if completeness["status"] != "passed":
        reason_codes = list(completeness.get("reason_codes") or [])
        return (
            CANONICAL_INCOMPLETE,
            reason_codes[0] if reason_codes else "canonical_incomplete",
        )
    return CANONICAL_OK, None


def _status_for_store_error(code: str) -> str:
    if code == "artifact_access_denied":
        return CANONICAL_ACCESS_DENIED
    if code in {
        "canonical_chunk_missing",
        "canonical_chunk_hash_mismatch",
        "artifact_payload_missing",
        "artifact_payload_corrupt",
    }:
        return CANONICAL_STORAGE_FAILURE
    if code == "canonical_schema_version_mismatch":
        return CANONICAL_VERSION_UNSUPPORTED
    return CANONICAL_INCOMPLETE


def _telemetry_event(
    *,
    mapping: CompatibilityMapping,
    status: str,
    started: float,
    envelope: CanonicalReadEnvelope | None,
    success: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "canonical_consumer_read_telemetry_v1",
        "consumer_id": mapping.consumer_id,
        "migration_wave": mapping.migration_wave,
        "canonical_read_attempts": 1,
        "canonical_read_success": int(success),
        "canonical_read_blocked": int(not success),
        "canonical_read_latency_ms": round((time.perf_counter() - started) * 1000, 6),
        "canonical_payload_bytes": envelope.payload_bytes if envelope else 0,
        "canonical_chunks_read": envelope.component_count if envelope else 0,
        "canonical_schema_version": envelope.schema_version if envelope else None,
        "canonical_version_id_hash": (
            hashlib.sha256(envelope.canonical_version_id.encode("utf-8")).hexdigest()
            if envelope
            else None
        ),
        "compatibility_status": status,
        "rollback_events": 0,
    }
