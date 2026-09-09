"""Publish the repository-owned ordinary-trade Prompt through OpenWebUI.

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
    INPUT_SCHEMA_VERSION,
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

    def pipe_valves(self) -> dict[str, str]:
        """The only values that may cross into Pipe configuration."""
        return {
            "ordinary_trade_mapping_prompt_id": self.prompt_ref,
            "ordinary_trade_mapping_prompt_command": self.prompt_command,
            "ordinary_trade_mapping_prompt_version": self.prompt_history_id,
            "ordinary_trade_mapping_prompt_hash": self.prompt_hash,
        }


@dataclass(frozen=True)
class OrdinaryTradeMappingPromptPublicationInput:
    actor_user_id: str
    content: str
    commit_message: str = "Publish Broker Reports ordinary-trade mapping Prompt v13"


def publication_input_from_asset(
    *, actor_user_id: str, asset_root: Path
) -> OrdinaryTradeMappingPromptPublicationInput:
    """Load the sole repository Prompt asset and reject an invalid release body."""
    asset_path = asset_root / PROMPT_ASSET_FILENAME
    try:
        content = asset_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OrdinaryTradeMappingPromptPublicationError(
            "ordinary_trade_mapping_prompt_asset_unavailable"
        ) from exc
    _require_contract_content(content)
    return OrdinaryTradeMappingPromptPublicationInput(
        actor_user_id=actor_user_id,
        content=content,
    )


class OrdinaryTradeMappingPromptPublisher:
    """Native OpenWebUI Prompt publication owner adapter.

    It has no SQLite or HTTP fallback.  A source-only test replaces
    ``_native_owners`` with small async fakes; a live release runs it in the
    OpenWebUI server process, where the imported owners carry out the same
    lifecycle as the Workspace API.
    """

    async def publish(
        self, request: OrdinaryTradeMappingPromptPublicationInput
    ) -> OrdinaryTradeMappingPromptPublication:
        actor_user_id = str(request.actor_user_id or "").strip()
        if not actor_user_id:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_actor_required"
            )
        _require_contract_content(request.content)
        owners = self._native_owners()
        try:
            async with owners["get_async_db_context"]() as session:
                existing = await owners["prompts"].get_prompt_by_command(
                    PROMPT_COMMAND, db=session
                )
                if existing is None:
                    published = await owners["prompts"].insert_new_prompt(
                        actor_user_id,
                        self._form(
                            owners=owners,
                            content=request.content,
                            commit_message=request.commit_message,
                            access_grants=[copy.deepcopy(_PUBLIC_READ_GRANT)],
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
                        action = (
                            "migrated" if existing_mode == "legacy_v12" else "updated"
                        )
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
                if (
                    str(model.get("id") or "") != publication.prompt_ref
                    or str(model.get("version_id") or "")
                    != publication.prompt_history_id
                ):
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

    @staticmethod
    def _form(
        *,
        owners: Mapping[str, Any],
        content: str,
        commit_message: str,
        access_grants: list[dict[str, str]] | None,
    ) -> Any:
        values = {
            "command": PROMPT_COMMAND,
            "name": "Broker Reports ordinary-trade semantic mapping",
            "content": content,
            "data": {"managed_asset_version": PROMPT_ASSET_VERSION},
            "meta": _metadata(),
            "tags": [PROMPT_REQUIRED_TAG],
            "commit_message": str(commit_message or "").strip() or None,
            "is_production": True,
        }
        if access_grants is not None:
            values["access_grants"] = access_grants
        return owners["prompt_form"](**values)

    @staticmethod
    def _require_existing_public_grant(row: Mapping[str, Any]) -> None:
        grants = row.get("access_grants")
        if not isinstance(grants, list) or not any(
            _grant_matches_public_read(grant) for grant in grants
        ):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_public_grant_required"
            )

    @staticmethod
    def _existing_metadata_mode(row: Mapping[str, Any]) -> str:
        # OpenWebUI only creates history for selected field changes.  Permit
        # the single v12 form only because its name and new v13 body change
        # together, forcing one complete native history snapshot.  Everything
        # else fails closed instead of attempting a metadata-only repair.
        if (
            row.get("command") != PROMPT_COMMAND
            or row.get("tags") != [PROMPT_REQUIRED_TAG]
        ):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_existing_metadata_incompatible"
            )
        if (
            row.get("name") == "Broker Reports ordinary-trade semantic mapping"
            and row.get("data") == {"managed_asset_version": PROMPT_ASSET_VERSION}
            and row.get("meta") == _metadata()
        ):
            return "current"
        # This is a deliberately closed migration, not a permissive upgrade:
        # it accepts only the single released v12 representation observed on
        # the product route.  The native update changes the name as well as
        # the body, so OpenWebUI writes one complete v13 history snapshot.
        if (
            row.get("name") == _LEGACY_V12_NAME
            and row.get("data") == {}
            and row.get("meta") == _LEGACY_V12_METADATA
        ):
            return "legacy_v12"
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
        version = str(row.get("version_id") or "").strip()
        if not prompt_ref or not version or row.get("command") != PROMPT_COMMAND:
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_history_missing"
            )
        self._require_existing_public_grant(row)
        history = await owners["prompt_histories"].get_history_entry_by_id(
            version, db=session
        )
        history_prompt_id = str(getattr(history, "prompt_id", "") or "")
        snapshot = getattr(history, "snapshot", None)
        if history_prompt_id != prompt_ref or not isinstance(snapshot, dict):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_history_missing"
            )
        expected = {
            "name": "Broker Reports ordinary-trade semantic mapping",
            "content": content,
            "command": PROMPT_COMMAND,
            "data": {"managed_asset_version": PROMPT_ASSET_VERSION},
            "meta": _metadata(),
            "tags": [PROMPT_REQUIRED_TAG],
        }
        if any(snapshot.get(key) != value for key, value in expected.items()):
            raise OrdinaryTradeMappingPromptPublicationError(
                "ordinary_trade_mapping_prompt_publication_history_drift"
            )
        return OrdinaryTradeMappingPromptPublication(
            prompt_ref=prompt_ref,
            prompt_command=PROMPT_COMMAND,
            prompt_history_id=version,
            prompt_hash=ordinary_trade_mapping_prompt_hash(content),
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


def _metadata() -> dict[str, Any]:
    return {
        "template_id": PROMPT_TEMPLATE_ID,
        "template_kind": PROMPT_TEMPLATE_KIND,
        "prompt_contract_id": PROMPT_CONTRACT_ID,
        "input_contract": INPUT_SCHEMA_VERSION,
        "output_schema_id": OUTPUT_SCHEMA_ID,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "structured_output_required": True,
        "mapping_domain": "ordinary_trade",
    }


def _require_contract_content(content: str) -> None:
    if not isinstance(content, str) or not content.strip() or content.count(
        PROMPT_PLACEHOLDER
    ) != 1:
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


def _grant_matches_public_read(value: Any) -> bool:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    return isinstance(value, dict) and all(
        value.get(key) == expected for key, expected in _PUBLIC_READ_GRANT.items()
    )


__all__ = [
    "OrdinaryTradeMappingPromptPublication",
    "OrdinaryTradeMappingPromptPublicationError",
    "OrdinaryTradeMappingPromptPublicationInput",
    "OrdinaryTradeMappingPromptPublisher",
    "PROMPT_ASSET_FILENAME",
    "PROMPT_ASSET_VERSION",
    "publication_input_from_asset",
]
