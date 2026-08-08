"""Tenant-scoped rebuildable SQL cache for Gate 4 financial facts."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date
import json
import re
import sqlite3
from typing import Any, Iterator

from .artifact_models import ArtifactAccessContext
from .artifact_resolver import ArtifactResolver
from .artifact_store import SqliteArtifactStoreAdapter
from .gate3_ndfl_case_readiness import Gate3NdflCaseReadinessFactory
from .gate4_financial_case_materialization import (
    GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION,
    Gate4FinancialCaseMaterialization,
    Gate4FinancialCaseMaterializationError,
    Gate4FinancialCaseMaterializerFactory,
    gate4_financial_case_fact_id,
)


GATE4_FINANCIAL_CASE_CACHE_SCHEMA_VERSION = (
    "broker_reports_gate4_financial_case_sql_cache_v1"
)
CASE_COMPLETE_FOR_CURRENT_INPUT_SET = (
    "CASE_COMPLETE_FOR_CURRENT_INPUT_SET"
)
CASE_INCOMPLETE = "CASE_INCOMPLETE"
FACTORY_REQUIRED = (
    "Gate4FinancialCaseRuntimeFactory.create is the production G4.2/G4.3 "
    "entrypoint; "
    "it composes Gate4FinancialCaseMaterializerFactory.create and "
    "Gate4FinancialCaseSqlCacheFactory.create over the existing ArtifactStore"
)
FORBIDDEN = (
    "G4.2/G4.3 must not create a second database, ACL, lifecycle or case "
    "registry; "
    "SQL must not own financial meaning, parse broker formats, call an LLM, "
    "deduplicate, reconcile, relate facts or apply tax logic"
)

_GENERATION_TABLE = "gate4_financial_case_cache_generation_v1"
_FACT_TABLE = "gate4_financial_case_fact_cache_v1"
_FINANCIAL_TYPE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


class Gate4FinancialCaseCacheError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _CacheScope:
    user_id: str
    case_id: str
    workspace_model_key: str

    @property
    def parameters(self) -> tuple[str, str, str]:
        return (self.user_id, self.case_id, self.workspace_model_key)


@dataclass(frozen=True)
class _UpstreamBinding:
    document_id: str
    financial_annotations_artifact_id: str
    canonical_version_id: str


@dataclass(frozen=True)
class Gate4FinancialCaseSource:
    """One case document's current Gate 3 eligibility, derived not stored."""

    document_id: str
    status: str
    canonical_version_id: str | None
    financial_annotations_artifact_id: str | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class Gate4FinancialCaseAssembly:
    """Current case facts plus narrowly scoped technical completeness."""

    status: str
    gate3_case_status: str
    sources: tuple[Gate4FinancialCaseSource, ...]
    facts: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _CaseSourceSet:
    gate3_case_status: str
    sources: tuple[Gate4FinancialCaseSource, ...]

    @property
    def bindings(self) -> tuple[_UpstreamBinding, ...]:
        return tuple(
            _UpstreamBinding(
                document_id=source.document_id,
                financial_annotations_artifact_id=(
                    source.financial_annotations_artifact_id
                ),
                canonical_version_id=source.canonical_version_id,
            )
            for source in self.sources
            if source.status == "CURRENT_GATE3_V2"
            and source.financial_annotations_artifact_id is not None
            and source.canonical_version_id is not None
        )

    @property
    def assembly_status(self) -> str:
        if self.sources and all(
            source.status == "CURRENT_GATE3_V2" for source in self.sources
        ):
            return CASE_COMPLETE_FOR_CURRENT_INPUT_SET
        return CASE_INCOMPLETE

    def assembly(
        self, *, facts: list[dict[str, Any]]
    ) -> Gate4FinancialCaseAssembly:
        return Gate4FinancialCaseAssembly(
            status=self.assembly_status,
            gate3_case_status=self.gate3_case_status,
            sources=self.sources,
            facts=tuple(copy.deepcopy(fact) for fact in facts),
        )


class Gate4FinancialCaseSqlCacheFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate4FinancialCaseSqlCache":
        if not isinstance(self._store, SqliteArtifactStoreAdapter):
            raise Gate4FinancialCaseCacheError(
                "gate4_sqlite_artifact_store_required"
            )
        return Gate4FinancialCaseSqlCache(
            store=self._store,
            read_enabled=self._read_enabled,
        )


class Gate4FinancialCaseRuntimeFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate4FinancialCaseRuntime":
        materializer = Gate4FinancialCaseMaterializerFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        cache = Gate4FinancialCaseSqlCacheFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        return Gate4FinancialCaseRuntime(
            store=self._store,
            materializer=materializer,
            cache=cache,
        )


class Gate4FinancialCaseRuntime:
    """Factory-composed G4.2/G4.3 materialize, rebuild and read boundary."""

    def __init__(self, *, store: Any, materializer: Any, cache: Any) -> None:
        self._store = store
        self._materializer = materializer
        self._cache = cache
        self._resolver = ArtifactResolver(store)

    def materialize_artifact(
        self,
        *,
        financial_annotations_artifact_id: str,
        context: ArtifactAccessContext,
    ) -> Gate4FinancialCaseMaterialization:
        return self._materializer.materialize(
            financial_annotations_artifact_id=(
                financial_annotations_artifact_id
            ),
            context=context,
        )

    def rebuild_artifact(
        self,
        *,
        financial_annotations_artifact_id: str,
        context: ArtifactAccessContext,
    ) -> list[dict[str, Any]]:
        bindings = self._cache.current_upstream_bindings(context=context)
        binding = next(
            (
                item
                for item in bindings
                if item.financial_annotations_artifact_id
                == financial_annotations_artifact_id
            ),
            None,
        )
        if binding is None:
            raise Gate4FinancialCaseCacheError("gate4_upstream_stale")
        materialized = self._materialize_binding(
            binding=binding,
            context=context,
        )
        self._cache.replace_document(
            context=context,
            materialization=materialized,
        )
        return [copy.deepcopy(fact) for fact in materialized.facts]

    def rebuild_case(
        self, *, context: ArtifactAccessContext
    ) -> Gate4FinancialCaseAssembly:
        source_set = self._cache.current_case_source_set(context=context)
        records = {
            record.artifact_id: record
            for record in self._resolver.catalog_case(context)
        }
        materializations = tuple(
            self._materialize_binding(
                binding=binding,
                context=context,
                records=records,
            )
            for binding in source_set.bindings
        )
        self._cache.replace_case(
            context=context,
            source_set=source_set,
            materializations=materializations,
        )
        return self.read_case(context=context)

    def read_case(
        self, *, context: ArtifactAccessContext
    ) -> Gate4FinancialCaseAssembly:
        return self._cache.read_case(context=context)

    def _materialize_binding(
        self,
        *,
        binding: _UpstreamBinding,
        context: ArtifactAccessContext,
        records: dict[str, Any] | None = None,
    ) -> Gate4FinancialCaseMaterialization:
        if records is None:
            records = {
                record.artifact_id: record
                for record in self._resolver.catalog_case(context)
            }
        record = records.get(binding.financial_annotations_artifact_id)
        if record is None:
            raise Gate4FinancialCaseCacheError("gate4_upstream_stale")
        record_context = replace(
            context,
            normalization_run_id=record.normalization_run_id,
        )
        try:
            materialized = self.materialize_artifact(
                financial_annotations_artifact_id=(
                    binding.financial_annotations_artifact_id
                ),
                context=record_context,
            )
        except Gate4FinancialCaseMaterializationError as exc:
            code = (
                "gate4_upstream_stale"
                if exc.code == "gate4_upstream_stale"
                else "gate4_materialization_failed"
            )
            raise Gate4FinancialCaseCacheError(code) from exc
        if (
            materialized.document_id != binding.document_id
            or materialized.financial_annotations_artifact_id
            != binding.financial_annotations_artifact_id
            or materialized.canonical_version_id
            != binding.canonical_version_id
        ):
            raise Gate4FinancialCaseCacheError("gate4_upstream_stale")
        return materialized

    def clear_case_cache(self, *, context: ArtifactAccessContext) -> None:
        self._cache.clear_case(context=context)

    def list_facts(
        self, *, context: ArtifactAccessContext
    ) -> list[dict[str, Any]]:
        return self._cache.list_for_case(context=context)

    def list_by_financial_type(
        self,
        *,
        context: ArtifactAccessContext,
        financial_type: str,
    ) -> list[dict[str, Any]]:
        return self._cache.list_by_financial_type(
            context=context,
            financial_type=financial_type,
        )

    def get_fact(
        self,
        *,
        context: ArtifactAccessContext,
        fact_id: str,
    ) -> dict[str, Any] | None:
        return self._cache.get_fact(context=context, fact_id=fact_id)

    def list_by_asset(
        self,
        *,
        context: ArtifactAccessContext,
        asset: str,
    ) -> list[dict[str, Any]]:
        return self._cache.list_by_asset(context=context, asset=asset)

    def list_by_period(
        self,
        *,
        context: ArtifactAccessContext,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        return self._cache.list_by_period(
            context=context,
            date_from=date_from,
            date_to=date_to,
        )


class Gate4FinancialCaseSqlCache:
    """Small SQL projection; every read first proves current upstream identity."""

    def __init__(
        self, *, store: SqliteArtifactStoreAdapter, read_enabled: bool
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._transactions = _Gate4CacheTransactionFactory(store=store)

    def current_upstream_bindings(
        self, *, context: ArtifactAccessContext
    ) -> tuple[_UpstreamBinding, ...]:
        return self.current_case_source_set(context=context).bindings

    def current_case_source_set(
        self, *, context: ArtifactAccessContext
    ) -> _CaseSourceSet:
        _scope(context)
        readiness = Gate3NdflCaseReadinessFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create(context=context)
        sources = tuple(
            Gate4FinancialCaseSource(
                document_id=item["document_id"],
                status=(
                    "CURRENT_GATE3_V2"
                    if item["gate3_ready"]
                    else "NOT_READY"
                ),
                canonical_version_id=item["current_canonical_version_id"],
                financial_annotations_artifact_id=(
                    item["selected_annotations_artifact_id"]
                ),
                reason_codes=tuple(item["reason_codes"]),
            )
            for item in readiness["documents"]
        )
        source_set = _CaseSourceSet(
            gate3_case_status=readiness["case_status"],
            sources=sources,
        )
        is_complete = (
            source_set.assembly_status
            == CASE_COMPLETE_FOR_CURRENT_INPUT_SET
        )
        if is_complete != bool(
            readiness["summary"]["gate4_handoff_ready"]
        ):
            raise Gate4FinancialCaseCacheError(
                "gate4_case_source_set_invalid"
            )
        return source_set

    def replace_document(
        self,
        *,
        context: ArtifactAccessContext,
        materialization: Gate4FinancialCaseMaterialization,
    ) -> None:
        expected = _UpstreamBinding(
            document_id=materialization.document_id,
            financial_annotations_artifact_id=(
                materialization.financial_annotations_artifact_id
            ),
            canonical_version_id=materialization.canonical_version_id,
        )
        current = self.current_upstream_bindings(context=context)
        if expected not in current:
            raise Gate4FinancialCaseCacheError("gate4_upstream_stale")
        scope = _scope(context)
        fact_ids: set[str] = set()
        for fact in materialization.facts:
            _validate_fact_for_cache(
                fact=fact,
                scope=scope,
                materialization=materialization,
            )
            if fact["fact_id"] in fact_ids:
                raise Gate4FinancialCaseCacheError(
                    "gate4_cache_duplicate_fact"
                )
            fact_ids.add(fact["fact_id"])
        with self._transactions.open(context=context, write=True) as repository:
            repository.replace_document(
                materialization=materialization,
            )
        if expected not in self.current_upstream_bindings(context=context):
            with self._transactions.open(
                context=context, write=True
            ) as repository:
                repository.clear_document(materialization.document_id)
            raise Gate4FinancialCaseCacheError("gate4_upstream_stale")

    def replace_case(
        self,
        *,
        context: ArtifactAccessContext,
        source_set: _CaseSourceSet,
        materializations: tuple[Gate4FinancialCaseMaterialization, ...],
    ) -> None:
        if source_set != self.current_case_source_set(context=context):
            raise Gate4FinancialCaseCacheError("gate4_upstream_stale")
        expected = source_set.bindings
        actual = tuple(
            _UpstreamBinding(
                document_id=item.document_id,
                financial_annotations_artifact_id=(
                    item.financial_annotations_artifact_id
                ),
                canonical_version_id=item.canonical_version_id,
            )
            for item in materializations
        )
        if actual != expected:
            raise Gate4FinancialCaseCacheError(
                "gate4_case_materialization_set_invalid"
            )
        scope = _scope(context)
        fact_ids: set[str] = set()
        for materialization in materializations:
            for fact in materialization.facts:
                _validate_fact_for_cache(
                    fact=fact,
                    scope=scope,
                    materialization=materialization,
                )
                if fact["fact_id"] in fact_ids:
                    raise Gate4FinancialCaseCacheError(
                        "gate4_cache_duplicate_fact"
                    )
                fact_ids.add(fact["fact_id"])
        with self._transactions.open(context=context, write=True) as repository:
            repository.replace_case(materializations=materializations)
        if source_set != self.current_case_source_set(context=context):
            with self._transactions.open(
                context=context, write=True
            ) as repository:
                repository.clear_case()
            raise Gate4FinancialCaseCacheError("gate4_upstream_stale")

    def clear_case(self, *, context: ArtifactAccessContext) -> None:
        with self._transactions.open(context=context, write=True) as repository:
            repository.clear_case()

    def read_case(
        self, *, context: ArtifactAccessContext
    ) -> Gate4FinancialCaseAssembly:
        source_set = self.current_case_source_set(context=context)
        facts = self._read(
            context=context,
            query="case",
            parameters=(),
            source_set=source_set,
            allow_empty=True,
        )
        return source_set.assembly(facts=facts)

    def list_for_case(
        self, *, context: ArtifactAccessContext
    ) -> list[dict[str, Any]]:
        return self._read(context=context, query="case", parameters=())

    def list_by_financial_type(
        self,
        *,
        context: ArtifactAccessContext,
        financial_type: str,
    ) -> list[dict[str, Any]]:
        if (
            not isinstance(financial_type, str)
            or _FINANCIAL_TYPE.fullmatch(financial_type) is None
        ):
            raise Gate4FinancialCaseCacheError(
                "gate4_financial_type_invalid"
            )
        return self._read(
            context=context,
            query="financial_type",
            parameters=(financial_type,),
        )

    def get_fact(
        self,
        *,
        context: ArtifactAccessContext,
        fact_id: str,
    ) -> dict[str, Any] | None:
        if (
            not isinstance(fact_id, str)
            or re.fullmatch(r"g4fact_[0-9a-f]{32}", fact_id) is None
        ):
            raise Gate4FinancialCaseCacheError("gate4_fact_id_invalid")
        facts = self._read(
            context=context,
            query="fact_id",
            parameters=(fact_id,),
        )
        return facts[0] if facts else None

    def list_by_asset(
        self,
        *,
        context: ArtifactAccessContext,
        asset: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(asset, str) or not asset.strip() or asset != asset.strip():
            raise Gate4FinancialCaseCacheError("gate4_asset_invalid")
        return self._read(
            context=context,
            query="asset",
            parameters=(asset,),
        )

    def list_by_period(
        self,
        *,
        context: ArtifactAccessContext,
        date_from: str,
        date_to: str,
    ) -> list[dict[str, Any]]:
        start = _iso_date(date_from)
        end = _iso_date(date_to)
        if start > end:
            raise Gate4FinancialCaseCacheError("gate4_period_invalid")
        return self._read(
            context=context,
            query="period",
            parameters=(start, end),
        )

    def _read(
        self,
        *,
        context: ArtifactAccessContext,
        query: str,
        parameters: tuple[str, ...],
        source_set: _CaseSourceSet | None = None,
        allow_empty: bool = False,
    ) -> list[dict[str, Any]]:
        source_set = source_set or self.current_case_source_set(context=context)
        expected = source_set.bindings
        with self._transactions.open(context=context, write=False) as repository:
            stored = repository.generations()
            if not stored and (expected or not allow_empty):
                raise Gate4FinancialCaseCacheError("gate4_cache_missing")
            if stored != expected:
                raise Gate4FinancialCaseCacheError("gate4_cache_stale")
            rows = repository.query(query=query, parameters=parameters)
        facts = [_fact_from_row(row=row, scope=_scope(context)) for row in rows]
        if source_set != self.current_case_source_set(context=context):
            raise Gate4FinancialCaseCacheError("gate4_cache_stale")
        return facts


class _Gate4CacheTransactionFactory:
    """Create the repository only inside a trusted tenant/case transaction."""

    def __init__(self, *, store: SqliteArtifactStoreAdapter) -> None:
        self._store = store

    @contextmanager
    def open(
        self, *, context: ArtifactAccessContext, write: bool
    ) -> Iterator["_Gate4CacheRepository"]:
        scope = _scope(context)
        connection = sqlite3.connect(self._store.sqlite_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            if write:
                connection.execute("BEGIN IMMEDIATE")
            repository = _Gate4CacheRepository(
                connection=connection,
                scope=scope,
            )
            repository.ensure_schema()
            yield repository
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class _Gate4CacheRepository:
    """All Gate 4 cache SQL; constructed only from a scoped transaction."""

    def __init__(self, *, connection: sqlite3.Connection, scope: _CacheScope) -> None:
        self._connection = connection
        self._scope = scope

    def ensure_schema(self) -> None:
        self._connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_GENERATION_TABLE}(
                user_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                workspace_model_key TEXT NOT NULL,
                document_id TEXT NOT NULL,
                financial_annotations_artifact_id TEXT NOT NULL,
                canonical_version_id TEXT NOT NULL,
                fact_count INTEGER NOT NULL CHECK(fact_count >= 0),
                cache_schema_version TEXT NOT NULL,
                PRIMARY KEY(
                    user_id, case_id, workspace_model_key, document_id
                ),
                UNIQUE(financial_annotations_artifact_id),
                FOREIGN KEY(financial_annotations_artifact_id)
                    REFERENCES artifact_records(artifact_id)
            )
            """
        )
        self._connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_FACT_TABLE}(
                fact_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                workspace_model_key TEXT NOT NULL,
                document_id TEXT NOT NULL,
                financial_annotations_artifact_id TEXT NOT NULL,
                canonical_version_id TEXT NOT NULL,
                annotation_index INTEGER NOT NULL CHECK(annotation_index >= 0),
                financial_type TEXT NOT NULL,
                fact_status TEXT NOT NULL,
                asset_value TEXT NULL,
                fact_date TEXT NULL,
                fact_json TEXT NOT NULL,
                cache_schema_version TEXT NOT NULL,
                FOREIGN KEY(financial_annotations_artifact_id)
                    REFERENCES artifact_records(artifact_id)
            )
            """
        )
        self._connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_g4_case_type_v1
            ON {_FACT_TABLE}(
                user_id, case_id, workspace_model_key, financial_type
            )
            """
        )
        self._connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_g4_case_asset_v1
            ON {_FACT_TABLE}(
                user_id, case_id, workspace_model_key, asset_value
            )
            """
        )
        self._connection.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_g4_case_date_v1
            ON {_FACT_TABLE}(
                user_id, case_id, workspace_model_key, fact_date
            )
            """
        )
        self._connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_g4_upstream_lifecycle_v1
            AFTER UPDATE OF lifecycle_status, purge_status ON artifact_records
            WHEN NEW.lifecycle_status IN (
                'expired', 'purge_pending', 'purged', 'blocked', 'privacy_failed'
            ) OR NEW.purge_status IN (
                'expired', 'purge_pending', 'purged', 'blocked'
            )
            BEGIN
                DELETE FROM {_FACT_TABLE}
                WHERE financial_annotations_artifact_id = NEW.artifact_id;
                DELETE FROM {_GENERATION_TABLE}
                WHERE financial_annotations_artifact_id = NEW.artifact_id;
            END
            """
        )
        self._connection.execute(
            f"""
            CREATE TRIGGER IF NOT EXISTS trg_g4_upstream_delete_v1
            AFTER DELETE ON artifact_records
            BEGIN
                DELETE FROM {_FACT_TABLE}
                WHERE financial_annotations_artifact_id = OLD.artifact_id;
                DELETE FROM {_GENERATION_TABLE}
                WHERE financial_annotations_artifact_id = OLD.artifact_id;
            END
            """
        )

    def clear_case(self) -> None:
        predicate = (
            "user_id = ? AND case_id = ? AND workspace_model_key = ?"
        )
        self._connection.execute(
            f"DELETE FROM {_FACT_TABLE} WHERE {predicate}",
            self._scope.parameters,
        )
        self._connection.execute(
            f"DELETE FROM {_GENERATION_TABLE} WHERE {predicate}",
            self._scope.parameters,
        )

    def clear_document(self, document_id: str) -> None:
        predicate = (
            "user_id = ? AND case_id = ? AND workspace_model_key = ? "
            "AND document_id = ?"
        )
        parameters = (*self._scope.parameters, document_id)
        self._connection.execute(
            f"DELETE FROM {_FACT_TABLE} WHERE {predicate}",
            parameters,
        )
        self._connection.execute(
            f"DELETE FROM {_GENERATION_TABLE} WHERE {predicate}",
            parameters,
        )

    def replace_document(
        self,
        *,
        materialization: Gate4FinancialCaseMaterialization,
    ) -> None:
        self.clear_document(materialization.document_id)
        self._insert_document(materialization)

    def replace_case(
        self,
        *,
        materializations: tuple[Gate4FinancialCaseMaterialization, ...],
    ) -> None:
        self.clear_case()
        for materialization in materializations:
            self._insert_document(materialization)

    def _insert_document(
        self, materialization: Gate4FinancialCaseMaterialization
    ) -> None:
        self._connection.execute(
            f"""
            INSERT INTO {_GENERATION_TABLE}(
                user_id, case_id, workspace_model_key, document_id,
                financial_annotations_artifact_id, canonical_version_id,
                fact_count, cache_schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                *self._scope.parameters,
                materialization.document_id,
                materialization.financial_annotations_artifact_id,
                materialization.canonical_version_id,
                len(materialization.facts),
                GATE4_FINANCIAL_CASE_CACHE_SCHEMA_VERSION,
            ),
        )
        for fact in materialization.facts:
            self._insert_fact(fact)

    def generations(self) -> tuple[_UpstreamBinding, ...]:
        rows = self._connection.execute(
            f"""
            SELECT g.document_id, g.financial_annotations_artifact_id,
                   g.canonical_version_id, g.fact_count,
                   COUNT(f.fact_id) AS actual_fact_count
            FROM {_GENERATION_TABLE} g
            LEFT JOIN {_FACT_TABLE} f
              ON f.financial_annotations_artifact_id =
                 g.financial_annotations_artifact_id
            WHERE g.user_id = ? AND g.case_id = ?
              AND g.workspace_model_key = ?
              AND g.cache_schema_version = ?
            GROUP BY g.document_id, g.financial_annotations_artifact_id,
                     g.canonical_version_id, g.fact_count
            ORDER BY g.document_id
            """,
            (*self._scope.parameters, GATE4_FINANCIAL_CASE_CACHE_SCHEMA_VERSION),
        ).fetchall()
        if any(int(row["fact_count"]) != int(row["actual_fact_count"]) for row in rows):
            raise Gate4FinancialCaseCacheError("gate4_cache_corrupt")
        return tuple(
            _UpstreamBinding(
                document_id=str(row["document_id"]),
                financial_annotations_artifact_id=str(
                    row["financial_annotations_artifact_id"]
                ),
                canonical_version_id=str(row["canonical_version_id"]),
            )
            for row in rows
        )

    def query(
        self, *, query: str, parameters: tuple[str, ...]
    ) -> list[sqlite3.Row]:
        clauses = [
            "user_id = ?",
            "case_id = ?",
            "workspace_model_key = ?",
            "cache_schema_version = ?",
        ]
        values: tuple[Any, ...] = (
            *self._scope.parameters,
            GATE4_FINANCIAL_CASE_CACHE_SCHEMA_VERSION,
        )
        if query == "case":
            pass
        elif query == "financial_type":
            clauses.append("financial_type = ?")
            values = (*values, *parameters)
        elif query == "fact_id":
            clauses.append("fact_id = ?")
            values = (*values, *parameters)
        elif query == "asset":
            clauses.append("asset_value = ?")
            values = (*values, *parameters)
        elif query == "period":
            clauses.extend(("fact_date >= ?", "fact_date <= ?"))
            values = (*values, *parameters)
        else:
            raise Gate4FinancialCaseCacheError("gate4_cache_query_invalid")
        return self._connection.execute(
            f"""
            SELECT * FROM {_FACT_TABLE}
            WHERE {' AND '.join(clauses)}
            ORDER BY fact_date IS NULL, fact_date, financial_type, fact_id
            """,
            values,
        ).fetchall()

    def _insert_fact(self, fact: dict[str, Any]) -> None:
        binding = fact["gate3_binding"]
        canonical = binding["canonical_binding"]
        self._connection.execute(
            f"""
            INSERT INTO {_FACT_TABLE}(
                fact_id, user_id, case_id, workspace_model_key,
                document_id, financial_annotations_artifact_id,
                canonical_version_id, annotation_index, financial_type,
                fact_status, asset_value, fact_date, fact_json,
                cache_schema_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact["fact_id"],
                *self._scope.parameters,
                canonical["document_id"],
                binding["financial_annotations_artifact_id"],
                canonical["canonical_version_id"],
                binding["annotation_index"],
                fact["financial_type"],
                fact["status"],
                _role_value(fact, "asset"),
                _role_value(fact, "date"),
                _canonical_json(fact),
                GATE4_FINANCIAL_CASE_CACHE_SCHEMA_VERSION,
            ),
        )


def _scope(context: ArtifactAccessContext) -> _CacheScope:
    if not isinstance(context, ArtifactAccessContext):
        raise Gate4FinancialCaseCacheError("gate4_trusted_context_required")
    if (
        not context.user_id
        or not context.case_id
        or not context.allow_private
    ):
        raise Gate4FinancialCaseCacheError(
            "gate4_private_case_context_required"
        )
    return _CacheScope(
        user_id=context.user_id,
        case_id=context.case_id,
        workspace_model_key=context.workspace_model_id or "",
    )


def _validate_fact_for_cache(
    *,
    fact: dict[str, Any],
    scope: _CacheScope,
    materialization: Gate4FinancialCaseMaterialization,
) -> None:
    if not isinstance(fact, dict):
        raise Gate4FinancialCaseCacheError("gate4_fact_contract_invalid")
    binding = fact.get("gate3_binding")
    canonical = binding.get("canonical_binding") if isinstance(binding, dict) else None
    if (
        fact.get("schema_version")
        != GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION
        or fact.get("fact_id") != gate4_financial_case_fact_id(fact)
        or fact.get("case_binding")
        != {"scope_kind": "case", "scope_id": scope.case_id}
        or not isinstance(canonical, dict)
        or binding.get("financial_annotations_artifact_id")
        != materialization.financial_annotations_artifact_id
        or canonical.get("document_id") != materialization.document_id
        or canonical.get("canonical_version_id")
        != materialization.canonical_version_id
    ):
        raise Gate4FinancialCaseCacheError("gate4_fact_contract_invalid")


def _fact_from_row(*, row: sqlite3.Row, scope: _CacheScope) -> dict[str, Any]:
    try:
        fact = json.loads(str(row["fact_json"]))
    except (TypeError, json.JSONDecodeError) as exc:
        raise Gate4FinancialCaseCacheError("gate4_cache_corrupt") from exc
    if not isinstance(fact, dict):
        raise Gate4FinancialCaseCacheError("gate4_cache_corrupt")
    binding = fact.get("gate3_binding")
    canonical = binding.get("canonical_binding") if isinstance(binding, dict) else None
    if (
        fact.get("schema_version")
        != GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION
        or fact.get("fact_id") != str(row["fact_id"])
        or fact.get("fact_id") != gate4_financial_case_fact_id(fact)
        or fact.get("case_binding")
        != {"scope_kind": "case", "scope_id": scope.case_id}
        or not isinstance(canonical, dict)
        or binding.get("financial_annotations_artifact_id")
        != str(row["financial_annotations_artifact_id"])
        or binding.get("annotation_index") != int(row["annotation_index"])
        or canonical.get("document_id") != str(row["document_id"])
        or canonical.get("canonical_version_id")
        != str(row["canonical_version_id"])
        or fact.get("financial_type") != str(row["financial_type"])
        or fact.get("status") != str(row["fact_status"])
        or _role_value(fact, "asset") != row["asset_value"]
        or _role_value(fact, "date") != row["fact_date"]
    ):
        raise Gate4FinancialCaseCacheError("gate4_cache_corrupt")
    return copy.deepcopy(fact)


def _role_value(fact: dict[str, Any], role: str) -> str | None:
    matches = [
        item
        for item in fact.get("roles", [])
        if isinstance(item, dict) and item.get("role") == role
    ]
    if len(matches) > 1:
        raise Gate4FinancialCaseCacheError("gate4_fact_contract_invalid")
    if not matches or matches[0].get("status") == "missing":
        return None
    value = matches[0].get("value")
    if not isinstance(value, str) or not value:
        raise Gate4FinancialCaseCacheError("gate4_fact_contract_invalid")
    return value


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise Gate4FinancialCaseCacheError(
            "gate4_fact_contract_invalid"
        ) from exc


def _iso_date(value: str) -> str:
    if not isinstance(value, str):
        raise Gate4FinancialCaseCacheError("gate4_period_invalid")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise Gate4FinancialCaseCacheError("gate4_period_invalid") from exc
    if parsed.isoformat() != value:
        raise Gate4FinancialCaseCacheError("gate4_period_invalid")
    return value


__all__ = [
    "CASE_COMPLETE_FOR_CURRENT_INPUT_SET",
    "CASE_INCOMPLETE",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE4_FINANCIAL_CASE_CACHE_SCHEMA_VERSION",
    "Gate4FinancialCaseAssembly",
    "Gate4FinancialCaseCacheError",
    "Gate4FinancialCaseRuntime",
    "Gate4FinancialCaseRuntimeFactory",
    "Gate4FinancialCaseSource",
    "Gate4FinancialCaseSqlCache",
    "Gate4FinancialCaseSqlCacheFactory",
]
