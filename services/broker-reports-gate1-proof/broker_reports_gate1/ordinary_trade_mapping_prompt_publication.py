"""Publish closed repository-owned Broker Reports Prompts through OpenWebUI.

This is a release-time composition boundary.  It deliberately delegates
versioning and grants to OpenWebUI's Prompt owners: ``Prompts`` creates or
updates the row, and its native history lifecycle creates the active
``prompt_history`` revision.  The Pipe consumes only the returned safe pin.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .ordinary_trade_mapping_prompt import (
    DOCUMENT_OPENING_INPUT_SCHEMA_VERSION,
    INPUT_SCHEMA_VERSION,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_COMMAND,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_REQUIRED_TAG,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_ID,
    GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_KIND,
    GOAL391_GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_KIND,
    ORDINARY_TRADE_MAPPING_V15_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V15_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V15_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V15_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V15_PROMPT_TEMPLATE_KIND,
    ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_KIND,
    ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_KIND,
    OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND,
    PROMPT_CONTRACT_ID,
    PROMPT_PLACEHOLDER,
    PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    ordinary_trade_mapping_prompt_hash,
)
from .pdf_table_continuation_annotation_prompt import (
    INPUT_SCHEMA_VERSION as PDF_TABLE_CONTINUATION_ANNOTATION_INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_ID as PDF_TABLE_CONTINUATION_ANNOTATION_OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION as PDF_TABLE_CONTINUATION_ANNOTATION_OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND as PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_COMMAND,
    PROMPT_CONTRACT_ID as PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG as PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID as PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND as PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_TEMPLATE_KIND,
)
from .document_passport import (
    INPUT_SCHEMA_VERSION as DOCUMENT_METADATA_PASSPORT_INPUT_SCHEMA_VERSION,
    PASSPORT_JSON_SCHEMA_ID as DOCUMENT_METADATA_PASSPORT_OUTPUT_SCHEMA_ID,
    PASSPORT_SCHEMA_VERSION as DOCUMENT_METADATA_PASSPORT_OUTPUT_SCHEMA_VERSION,
    PROMPT_CONTRACT_ID as DOCUMENT_METADATA_PASSPORT_PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG as DOCUMENT_METADATA_PASSPORT_PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID as DOCUMENT_METADATA_PASSPORT_PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND as DOCUMENT_METADATA_PASSPORT_PROMPT_TEMPLATE_KIND,
)


PROMPT_ASSET_VERSION = "v13"
PROMPT_ASSET_FILENAME = "broker_reports_ordinary_trade_mapping_prompt.v13.md"
PROMPT_PUBLICATION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_mapping_prompt_publication_v1"
)
_PUBLIC_READ_GRANT = {
    "principal_type": "user",
    "principal_id": "*",
    "permission": "read",
}
_LEGACY_V12_NAME = "Broker Reports Ordinary Trade Mapping"
_LEGACY_V12_METADATA = {
    "template_id": PROMPT_TEMPLATE_ID,
    "template_kind": PROMPT_TEMPLATE_KIND,
    "prompt_contract_id": PROMPT_CONTRACT_ID,
    "input_contract": INPUT_SCHEMA_VERSION,
    "output_schema_id": "broker_reports_ordinary_trade_semantic_mapping_response_v12",
    "output_schema_version": "broker_reports_ordinary_trade_semantic_mapping_response_v12",
    "structured_output_required": True,
    "mapping_domain": "ordinary_trade",
}


@dataclass(frozen=True)
class OrdinaryTradeMappingPromptPublicationProfile:
    """One closed native-Prompt identity that this publisher may mutate.

    The publisher is intentionally not a generic Prompt writer: a caller can
    select only one of the repository-owned immutable profiles below.
    The profiles retain their independent domain contracts while sharing only
    the OpenWebUI Prompt/history/grant lifecycle.
    """

    profile_id: str
    command: str
    name: str
    asset_filename: str
    asset_version: str
    template_id: str
    template_kind: str
    prompt_contract_id: str
    input_schema_version: str
    output_schema_id: str
    output_schema_version: str
    required_tag: str
    placeholder: str | None
    is_production: bool
    initial_access_grants: tuple[tuple[str, str, str], ...]
    metadata_extension: Mapping[str, Any] | None = None
    metadata_mapping_domain: str | None = "ordinary_trade"
    commit_message: str | None = None
    legacy_metadata: Mapping[str, Any] | None = None
    legacy_name: str | None = None
    legacy_data: Mapping[str, Any] | None = None


ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE = (
    OrdinaryTradeMappingPromptPublicationProfile(
        profile_id="ordinary_trade_mapping_v13",
        command=PROMPT_COMMAND,
        name="Broker Reports ordinary-trade semantic mapping",
        asset_filename=PROMPT_ASSET_FILENAME,
        asset_version=PROMPT_ASSET_VERSION,
        template_id=PROMPT_TEMPLATE_ID,
        template_kind=PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=OUTPUT_SCHEMA_ID,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        required_tag=PROMPT_REQUIRED_TAG,
        placeholder=PROMPT_PLACEHOLDER,
        is_production=True,
        initial_access_grants=(("user", "*", "read"),),
        legacy_metadata=_LEGACY_V12_METADATA,
        legacy_name=_LEGACY_V12_NAME,
        legacy_data={},
    )
)

GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE = (
    OrdinaryTradeMappingPromptPublicationProfile(
        profile_id="goal391_grouped_mapping_lab_v14",
        command=GOAL391_GROUPED_MAPPING_LAB_PROMPT_COMMAND,
        name="Goal 391 grouped mapping lab v14",
        asset_filename="goal391_grouped_mapping_lab_prompt.v14.md",
        asset_version="v14-lab",
        template_id=GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_ID,
        template_kind=GOAL391_GROUPED_MAPPING_LAB_PROMPT_TEMPLATE_KIND,
        # The native request builder admits the established ordinary-trade
        # mapping operation; only the sealed response schema differs in lab.
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=GOAL391_GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION,
        output_schema_version=GOAL391_GROUPED_MAPPING_RESPONSE_SCHEMA_VERSION,
        required_tag=GOAL391_GROUPED_MAPPING_LAB_PROMPT_REQUIRED_TAG,
        placeholder=PROMPT_PLACEHOLDER,
        is_production=False,
        initial_access_grants=(("user", "*", "read"),),
    )
)

ORDINARY_TRADE_MAPPING_V14_PROFILE = OrdinaryTradeMappingPromptPublicationProfile(
    profile_id="ordinary_trade_mapping_v14",
    command=ORDINARY_TRADE_MAPPING_V14_PROMPT_COMMAND,
    name="Broker Reports ordinary-trade semantic mapping v14",
    asset_filename="broker_reports_ordinary_trade_mapping_prompt.v14.md",
    asset_version="v14",
    template_id=ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_ID,
    template_kind=ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_KIND,
    prompt_contract_id=PROMPT_CONTRACT_ID,
    input_schema_version=INPUT_SCHEMA_VERSION,
    output_schema_id=ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION,
    output_schema_version=ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION,
    required_tag=ORDINARY_TRADE_MAPPING_V14_PROMPT_REQUIRED_TAG,
    placeholder=PROMPT_PLACEHOLDER,
    is_production=True,
    initial_access_grants=(("user", "*", "read"),),
)

ORDINARY_TRADE_MAPPING_V15_PROFILE = OrdinaryTradeMappingPromptPublicationProfile(
    profile_id="ordinary_trade_mapping_v15",
    command=ORDINARY_TRADE_MAPPING_V15_PROMPT_COMMAND,
    name="Broker Reports ordinary-trade semantic mapping v15",
    asset_filename="broker_reports_ordinary_trade_mapping_prompt.v15.md",
    asset_version="v15",
    template_id=ORDINARY_TRADE_MAPPING_V15_PROMPT_TEMPLATE_ID,
    template_kind=ORDINARY_TRADE_MAPPING_V15_PROMPT_TEMPLATE_KIND,
    prompt_contract_id=PROMPT_CONTRACT_ID,
    input_schema_version=INPUT_SCHEMA_VERSION,
    output_schema_id=ORDINARY_TRADE_MAPPING_V15_COMPACT_RESPONSE_SCHEMA_VERSION,
    output_schema_version=ORDINARY_TRADE_MAPPING_V15_COMPACT_RESPONSE_SCHEMA_VERSION,
    required_tag=ORDINARY_TRADE_MAPPING_V15_PROMPT_REQUIRED_TAG,
    placeholder=PROMPT_PLACEHOLDER,
    is_production=True,
    initial_access_grants=(("user", "*", "read"),),
)

ORDINARY_TRADE_MAPPING_V16_PROFILE = OrdinaryTradeMappingPromptPublicationProfile(
    profile_id="ordinary_trade_mapping_v16",
    command=ORDINARY_TRADE_MAPPING_V16_PROMPT_COMMAND,
    name="Broker Reports ordinary-trade semantic mapping v16",
    asset_filename="broker_reports_ordinary_trade_mapping_prompt.v16.md",
    asset_version="v16",
    template_id=ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_ID,
    template_kind=ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_KIND,
    prompt_contract_id=PROMPT_CONTRACT_ID,
    input_schema_version=DOCUMENT_OPENING_INPUT_SCHEMA_VERSION,
    output_schema_id=ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
    output_schema_version=ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
    required_tag=ORDINARY_TRADE_MAPPING_V16_PROMPT_REQUIRED_TAG,
    placeholder=PROMPT_PLACEHOLDER,
    is_production=True,
    initial_access_grants=(("user", "*", "read"),),
)

ORDINARY_TRADE_MAPPING_V17_PROFILE = OrdinaryTradeMappingPromptPublicationProfile(
    profile_id="ordinary_trade_mapping_v17",
    command=ORDINARY_TRADE_MAPPING_V17_PROMPT_COMMAND,
    name="Broker Reports ordinary-trade semantic mapping v17",
    asset_filename="broker_reports_ordinary_trade_mapping_prompt.v17.md",
    asset_version="v17",
    template_id=ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_ID,
    template_kind=ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_KIND,
    prompt_contract_id=PROMPT_CONTRACT_ID,
    input_schema_version=DOCUMENT_OPENING_INPUT_SCHEMA_VERSION,
    output_schema_id=ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION,
    output_schema_version=ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION,
    required_tag=ORDINARY_TRADE_MAPPING_V17_PROMPT_REQUIRED_TAG,
    placeholder=PROMPT_PLACEHOLDER,
    is_production=True,
    initial_access_grants=(("user", "*", "read"),),
)

# A distinct physical-source profile. It reuses only the native
# Prompt/history/grant lifecycle below, not ordinary-trade meaning.
PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE = (
    OrdinaryTradeMappingPromptPublicationProfile(
        profile_id="pdf_table_continuation_annotation_v3",
        command=PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_COMMAND,
        name="Broker Reports PDF physical table continuation annotation",
        asset_filename="broker_reports_native_table_continuation_annotation_prompt.v3.md",
        asset_version="v3",
        template_id=PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_TEMPLATE_ID,
        template_kind=PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_CONTRACT_ID,
        input_schema_version=PDF_TABLE_CONTINUATION_ANNOTATION_INPUT_SCHEMA_VERSION,
        output_schema_id=PDF_TABLE_CONTINUATION_ANNOTATION_OUTPUT_SCHEMA_ID,
        output_schema_version=PDF_TABLE_CONTINUATION_ANNOTATION_OUTPUT_SCHEMA_VERSION,
        required_tag=PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_REQUIRED_TAG,
        placeholder=None,
        is_production=True,
        initial_access_grants=(("user", "*", "read"),),
        metadata_extension={"annotation_domain": "physical_table_continuation"},
        metadata_mapping_domain=None,
        commit_message="Publish Broker Reports PDF table-continuation annotation Prompt v3",
    )
)

# A separate document-intake Prompt, sharing only the native Prompt/history
# lifecycle with the table-mapping profiles.  Its new command avoids silently
# reinterpreting the legacy seeded Prompt and gives the Pipe one exact pin.
DOCUMENT_METADATA_PASSPORT_V1_PROFILE = OrdinaryTradeMappingPromptPublicationProfile(
    profile_id="document_metadata_passport_v1",
    command="broker_gate1_document_passport_v1",
    name="Broker Reports document metadata passport v1",
    asset_filename="broker_reports_document_metadata_passport_prompt.v1.md",
    asset_version="v1",
    template_id=DOCUMENT_METADATA_PASSPORT_PROMPT_TEMPLATE_ID,
    template_kind=DOCUMENT_METADATA_PASSPORT_PROMPT_TEMPLATE_KIND,
    prompt_contract_id=DOCUMENT_METADATA_PASSPORT_PROMPT_CONTRACT_ID,
    input_schema_version=DOCUMENT_METADATA_PASSPORT_INPUT_SCHEMA_VERSION,
    output_schema_id=DOCUMENT_METADATA_PASSPORT_OUTPUT_SCHEMA_ID,
    output_schema_version=DOCUMENT_METADATA_PASSPORT_OUTPUT_SCHEMA_VERSION,
    required_tag=DOCUMENT_METADATA_PASSPORT_PROMPT_REQUIRED_TAG,
    placeholder="{{document_package_json}}",
    is_production=True,
    initial_access_grants=(("user", "*", "read"),),
    metadata_mapping_domain=None,
    metadata_extension={
        "gate": "gate1",
        "forbidden_tasks": [
            "source_fact_extraction",
            "tax_calculation",
            "declaration_generation",
            "xlsx_generation",
            "ocr_vlm",
            "knowledge_loading",
        ],
    },
    commit_message="Publish Broker Reports document metadata passport Prompt v1",
)

_PUBLISHABLE_PROFILES = {
    profile.profile_id: profile
    for profile in (
        ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
        GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE,
        ORDINARY_TRADE_MAPPING_V14_PROFILE,
        ORDINARY_TRADE_MAPPING_V15_PROFILE,
        ORDINARY_TRADE_MAPPING_V16_PROFILE,
        ORDINARY_TRADE_MAPPING_V17_PROFILE,
        PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE,
        DOCUMENT_METADATA_PASSPORT_V1_PROFILE,
    )
}


class OrdinaryTradeMappingPromptPublicationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OrdinaryTradeMappingPromptPublication:
    """Safe release output; it contains no Prompt body or grant detail."""

    prompt_ref: str
    prompt_command: str
    prompt_history_id: str
    prompt_hash: str
    action: str
    schema_version: str = PROMPT_PUBLICATION_SCHEMA_VERSION

    def safe_pin(self) -> dict[str, str]:
        """Return the provider-free immutable native Prompt identity."""

        return {
            "prompt_id": self.prompt_ref,
            "prompt_command": self.prompt_command,
            "prompt_version": self.prompt_history_id,
            "prompt_hash": self.prompt_hash,
        }

    def pipe_valves(self) -> dict[str, str]:
        """The legacy v13 product valve projection."""
        pin = self.safe_pin()
        return {
            "ordinary_trade_mapping_prompt_id": pin["prompt_id"],
            "ordinary_trade_mapping_prompt_command": pin["prompt_command"],
            "ordinary_trade_mapping_prompt_version": pin["prompt_version"],
            "ordinary_trade_mapping_prompt_hash": pin["prompt_hash"],
        }


@dataclass(frozen=True)
class OrdinaryTradeMappingPromptPublicationInput:
    actor_user_id: str
    content: str
    commit_message: str = "Publish Broker Reports ordinary-trade mapping Prompt v13"


def publication_input_from_asset(
    *,
    actor_user_id: str,
    asset_root: Path,
    profile: OrdinaryTradeMappingPromptPublicationProfile = ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
) -> OrdinaryTradeMappingPromptPublicationInput:
    """Load one closed repository Prompt asset and validate its marker."""
    profile = _require_known_profile(profile)
    asset_path = asset_root / profile.asset_filename
    try:
        content = asset_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OrdinaryTradeMappingPromptPublicationError(
            "ordinary_trade_mapping_prompt_asset_unavailable"
        ) from exc
    _require_contract_content(content, profile=profile)
    return OrdinaryTradeMappingPromptPublicationInput(
        actor_user_id=actor_user_id,
        content=content,
        commit_message=profile.commit_message or _default_commit_message(profile),
    )


class OrdinaryTradeMappingPromptPublisher:
    """Native OpenWebUI Prompt publication owner adapter.

    It has no SQLite or HTTP fallback.  A source-only test replaces
    ``_native_owners`` with small async fakes; a live release runs it in the
    OpenWebUI server process, where the imported owners carry out the same
    lifecycle as the Workspace API.
    """

    def __init__(
        self,
        *,
        profile: OrdinaryTradeMappingPromptPublicationProfile = ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
    ) -> None:
        self._profile = _require_known_profile(profile)

    async def publish(
        self, request: OrdinaryTradeMappingPromptPublicationInput
    ) -> OrdinaryTradeMappingPromptPublication:
        actor_user_id = str(request.actor_user_id or "").strip()
        if not actor_user_id:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_actor_required"
            )
        _require_contract_content(request.content, profile=self._profile)
        owners = self._native_owners()
        try:
            async with owners["get_async_db_context"]() as session:
                existing = await owners["prompts"].get_prompt_by_command(
                    self._profile.command, db=session
                )
                if existing is None:
                    published = await owners["prompts"].insert_new_prompt(
                        actor_user_id,
                        self._form(
                            owners=owners,
                            content=request.content,
                            commit_message=request.commit_message,
                            access_grants=_initial_access_grants(self._profile),
                        ),
                        db=session,
                    )
                    action = "created"
                else:
                    existing_row = _model_dict(existing)
                    self._require_existing_public_grant(existing_row)
                    existing_mode = self._existing_metadata_mode(existing_row)
                    if (
                        existing_mode == "current"
                        and existing_row.get("content") == request.content
                    ):
                        published = existing
                        action = "pinned"
                    else:
                        published = await owners["prompts"].update_prompt_by_id(
                            str(existing_row.get("id") or ""),
                            self._form(
                                owners=owners,
                                content=request.content,
                                commit_message=request.commit_message,
                                # ``None`` is intentional.  OpenWebUI preserves
                                # existing user:* grants rather than replacing
                                # them with a release-side projection.
                                access_grants=None,
                            ),
                            actor_user_id,
                            db=session,
                        )
                        action = "migrated" if existing_mode == "legacy" else "updated"
                if published is None:
                    raise OrdinaryTradeMappingPromptPublicationError(
                        "ordinary_trade_mapping_prompt_publication_failed"
                    )
                row = _model_dict(published)
                return await self._verified_publication(
                    owners=owners,
                    session=session,
                    row=row,
                    content=request.content,
                    action=action,
                )
        except OrdinaryTradeMappingPromptPublicationError:
            raise
        except Exception as exc:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_unavailable"
            ) from exc

    async def verify(
        self,
        publication: OrdinaryTradeMappingPromptPublication,
    ) -> OrdinaryTradeMappingPromptPublication:
        """Re-read a released pin through the native Prompt owners.

        This is deliberately read-only.  The release coordinator uses it after
        the Pipe bundle has been installed, so a later Prompt/history drift
        cannot be mistaken for a valid Pipe pin merely because an earlier
        publication receipt was well formed.
        """
        if not isinstance(publication, OrdinaryTradeMappingPromptPublication):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_pin_invalid"
            )
        owners = self._native_owners()
        try:
            async with owners["get_async_db_context"]() as session:
                row = await owners["prompts"].get_prompt_by_command(
                    publication.prompt_command,
                    db=session,
                )
                if row is None:
                    raise OrdinaryTradeMappingPromptPublicationError(
                        "ordinary_trade_mapping_prompt_publication_pin_missing"
                    )
                model = _model_dict(row)
                if str(model.get("id") or "") != publication.prompt_ref:
                    raise OrdinaryTradeMappingPromptPublicationError(
                        "ordinary_trade_mapping_prompt_publication_pin_drift"
                    )
                verified = await self._verified_publication(
                    owners=owners,
                    session=session,
                    row=model,
                    content=str(model.get("content") or ""),
                    action="verified",
                )
                if verified.prompt_hash != publication.prompt_hash:
                    raise OrdinaryTradeMappingPromptPublicationError(
                        "ordinary_trade_mapping_prompt_publication_pin_drift"
                    )
                return verified
        except OrdinaryTradeMappingPromptPublicationError:
            raise
        except Exception as exc:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_unavailable"
            ) from exc

    def _form(
        self,
        *,
        owners: Mapping[str, Any],
        content: str,
        commit_message: str,
        access_grants: list[dict[str, str]] | None,
    ) -> Any:
        profile = self._profile
        values = {
            "command": profile.command,
            "name": profile.name,
            "content": content,
            "data": {"managed_asset_version": profile.asset_version},
            "meta": _metadata(profile=profile),
            "tags": [profile.required_tag],
            "commit_message": str(commit_message or "").strip() or None,
            "is_production": profile.is_production,
        }
        if access_grants is not None:
            values["access_grants"] = access_grants
        return owners["prompt_form"](**values)

    def _require_existing_public_grant(self, row: Mapping[str, Any]) -> None:
        grants = row.get("access_grants")
        if not isinstance(grants, list) or not any(
            _grant_matches(grant, expected)
            for grant in grants
            for expected in _initial_access_grants(self._profile)
        ):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_public_grant_required"
            )

    def _existing_metadata_mode(self, row: Mapping[str, Any]) -> str:
        # OpenWebUI only creates history for selected field changes.  Permit
        # the single v12 form only because its name and new v13 body change
        # together, forcing one complete native history snapshot.  Everything
        # else fails closed instead of attempting a metadata-only repair.
        profile = self._profile
        if row.get("command") != profile.command or row.get("tags") != [
            profile.required_tag
        ]:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_existing_metadata_incompatible"
            )
        if (
            row.get("name") == profile.name
            and row.get("data") == {"managed_asset_version": profile.asset_version}
            and row.get("meta") == _metadata(profile=profile)
        ):
            return "current"
        # A legacy migration is deliberately opt-in per profile.  The v14 lab
        # profile has none, so it can never reinterpret an old product Prompt.
        if (
            profile.legacy_metadata is not None
            and row.get("name") == profile.legacy_name
            and row.get("data") == profile.legacy_data
            and row.get("meta") == profile.legacy_metadata
        ):
            return "legacy"
        raise OrdinaryTradeMappingPromptPublicationError(
            "ordinary_trade_mapping_prompt_existing_metadata_incompatible"
        )

    async def _verified_publication(
        self,
        *,
        owners: Mapping[str, Any],
        session: Any,
        row: Mapping[str, Any],
        content: str,
        action: str,
    ) -> OrdinaryTradeMappingPromptPublication:
        prompt_ref = str(row.get("id") or "").strip()
        profile = self._profile
        if not prompt_ref or row.get("command") != profile.command:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_history_missing"
            )
        self._require_existing_public_grant(row)
        # Some supported OpenWebUI releases retain ``version_id`` from a prior
        # revision after an update.  The native history owner is authoritative:
        # pin its latest immutable snapshot for this Prompt, not the stale row
        # pointer.
        history = await owners["prompt_histories"].get_latest_history_entry(
            prompt_ref, db=session
        )
        history_id = str(getattr(history, "id", "") or "").strip()
        history_prompt_id = str(getattr(history, "prompt_id", "") or "")
        snapshot = getattr(history, "snapshot", None)
        if (
            not history_id
            or history_prompt_id != prompt_ref
            or not isinstance(snapshot, dict)
        ):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_history_missing"
            )
        expected = {
            "name": profile.name,
            "content": content,
            "command": profile.command,
            "data": {"managed_asset_version": profile.asset_version},
            "meta": _metadata(profile=profile),
            "tags": [profile.required_tag],
        }
        if any(snapshot.get(key) != value for key, value in expected.items()):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_history_drift"
            )
        return OrdinaryTradeMappingPromptPublication(
            prompt_ref=prompt_ref,
            prompt_command=profile.command,
            prompt_history_id=history_id,
            prompt_hash=_profile_prompt_hash(content, profile=profile),
            action=action,
        )

    @staticmethod
    def _native_owners() -> dict[str, Any]:
        try:
            from open_webui.internal.db import get_async_db_context
            from open_webui.models.prompt_history import PromptHistories
            from open_webui.models.prompts import PromptForm, Prompts
        except Exception as exc:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_unavailable"
            ) from exc
        return {
            "get_async_db_context": get_async_db_context,
            "prompt_form": PromptForm,
            "prompts": Prompts,
            "prompt_histories": PromptHistories,
        }


def _metadata(
    *,
    profile: OrdinaryTradeMappingPromptPublicationProfile = ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
) -> dict[str, Any]:
    profile = _require_known_profile(profile)
    base = {
        "template_id": profile.template_id,
        "template_kind": profile.template_kind,
        "prompt_contract_id": profile.prompt_contract_id,
        "input_contract": profile.input_schema_version,
        "output_schema_id": profile.output_schema_id,
        "output_schema_version": profile.output_schema_version,
        "structured_output_required": True,
        "mapping_domain": profile.metadata_mapping_domain,
    }
    extension = dict(profile.metadata_extension or {})
    if set(extension) & set(base):
        raise OrdinaryTradeMappingPromptPublicationError(
            "ordinary_trade_mapping_prompt_profile_invalid"
        )
    if profile.metadata_mapping_domain is None:
        base.pop("mapping_domain")
    return {**base, **extension}


def _require_contract_content(
    content: str, *, profile: OrdinaryTradeMappingPromptPublicationProfile
) -> None:
    profile = _require_known_profile(profile)
    if (
        not isinstance(content, str)
        or not content.strip()
        or (
            profile.placeholder is not None
            and content.count(profile.placeholder) != 1
        )
    ):
        raise OrdinaryTradeMappingPromptPublicationError(
            "ordinary_trade_mapping_prompt_asset_contract_invalid"
        )


def _model_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        raise OrdinaryTradeMappingPromptPublicationError(
            "ordinary_trade_mapping_prompt_publication_response_invalid"
        )
    return copy.deepcopy(value)


def _initial_access_grants(
    profile: OrdinaryTradeMappingPromptPublicationProfile,
) -> list[dict[str, str]]:
    return [
        {
            "principal_type": principal_type,
            "principal_id": principal_id,
            "permission": permission,
        }
        for principal_type, principal_id, permission in profile.initial_access_grants
    ]


def _grant_matches(value: Any, expected: Mapping[str, str]) -> bool:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return isinstance(value, dict) and all(
        value.get(key) == expected_value
        for key, expected_value in expected.items()
    )


def _profile_prompt_hash(
    content: str, *, profile: OrdinaryTradeMappingPromptPublicationProfile
) -> str:
    return ordinary_trade_mapping_prompt_hash(
        content,
        prompt_contract_id=profile.prompt_contract_id,
        input_schema_version=profile.input_schema_version,
        output_schema_id=profile.output_schema_id,
        output_schema_version=profile.output_schema_version,
    )


def _default_commit_message(
    profile: OrdinaryTradeMappingPromptPublicationProfile,
) -> str:
    if profile is ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE:
        return "Publish Broker Reports ordinary-trade mapping Prompt v13"
    if profile is GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE:
        return "Publish Goal 391 grouped mapping lab Prompt v14"
    if profile is ORDINARY_TRADE_MAPPING_V14_PROFILE:
        return "Publish Broker Reports ordinary-trade mapping Prompt v14"
    if profile is ORDINARY_TRADE_MAPPING_V15_PROFILE:
        return "Publish Broker Reports ordinary-trade mapping Prompt v15"
    if profile is ORDINARY_TRADE_MAPPING_V16_PROFILE:
        return "Publish Broker Reports ordinary-trade mapping Prompt v16"
    if profile is ORDINARY_TRADE_MAPPING_V17_PROFILE:
        return "Publish Broker Reports ordinary-trade mapping Prompt v17"
    if profile is DOCUMENT_METADATA_PASSPORT_V1_PROFILE:
        return "Publish Broker Reports document metadata passport Prompt v1"
    raise OrdinaryTradeMappingPromptPublicationError(
        "ordinary_trade_mapping_prompt_profile_invalid"
    )


def _require_known_profile(
    profile: OrdinaryTradeMappingPromptPublicationProfile,
) -> OrdinaryTradeMappingPromptPublicationProfile:
    if (
        not isinstance(profile, OrdinaryTradeMappingPromptPublicationProfile)
        or _PUBLISHABLE_PROFILES.get(profile.profile_id) is not profile
    ):
        raise OrdinaryTradeMappingPromptPublicationError(
            "ordinary_trade_mapping_prompt_profile_invalid"
        )
    return profile


__all__ = [
    "OrdinaryTradeMappingPromptPublication",
    "OrdinaryTradeMappingPromptPublicationError",
    "OrdinaryTradeMappingPromptPublicationInput",
    "OrdinaryTradeMappingPromptPublicationProfile",
    "OrdinaryTradeMappingPromptPublisher",
    "ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE",
    "GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE",
    "ORDINARY_TRADE_MAPPING_V14_PROFILE",
    "ORDINARY_TRADE_MAPPING_V15_PROFILE",
    "ORDINARY_TRADE_MAPPING_V16_PROFILE",
    "ORDINARY_TRADE_MAPPING_V17_PROFILE",
    "PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE",
    "DOCUMENT_METADATA_PASSPORT_V1_PROFILE",
    "PROMPT_ASSET_FILENAME",
    "PROMPT_ASSET_VERSION",
    "publication_input_from_asset",
]
