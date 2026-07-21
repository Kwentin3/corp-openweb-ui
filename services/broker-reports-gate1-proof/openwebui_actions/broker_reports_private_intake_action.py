"""
title: Broker Reports Private Intake Action
author: Alpha Soft
version: 2.0.0
required_open_webui_version: 0.9.6
"""

from __future__ import annotations

import hashlib
from typing import Any

from open_webui.env import WEBUI_SECRET_KEY
from open_webui.routers.broker_reports_intake_contract import (
    ACTION_ATTESTATION_KEY,
    ACTION_ATTESTATION_SCHEMA_VERSION,
    PROTECTED_ACTION_ID,
    verify_action_attestation,
)


class Action:
    """Production intake handoff; generic OpenWebUI file refs are never read."""

    async def action(
        self,
        body: dict,
        __id__: str | None = None,
        __user__: dict | None = None,
        __event_emitter__=None,
    ) -> dict[str, Any]:
        await self._emit(__event_emitter__, "Verifying private intake receipts...", done=False)
        try:
            sources = self._verified_sources(
                body,
                action_id=__id__,
                authenticated_user_id=str((__user__ or {}).get("id") or ""),
            )
        except Exception:
            await self._emit(
                __event_emitter__,
                "Private intake receipt verification rejected.",
                done=True,
            )
            raise
        await self._emit(
            __event_emitter__,
            f"Accepted {len(sources)} receipt-backed source(s).",
            done=True,
        )

        public_documents = [
            {
                "document_id": "broker_source_"
                + hashlib.sha256(source["receipt_id"].encode("ascii")).hexdigest()[:16],
                "intake_eligibility": "server_verified",
                "native_processing": False,
                "knowledge_rag_vectorization": False,
            }
            for source in sources
        ]
        return {
            "content": (
                "Broker Reports private intake verified.\n\n"
                f"Eligible sources: {len(sources)}\n\n"
                "Native OpenWebUI processing, Knowledge, RAG, embeddings and "
                "vectorization remain disabled."
            ),
            "broker_reports_private_intake": {
                "schema_version": ACTION_ATTESTATION_SCHEMA_VERSION,
                "run_status": "receipt_verified",
                "eligible_sources_total": len(sources),
                "documents": public_documents,
            },
        }

    def _verified_sources(
        self,
        body: Any,
        *,
        action_id: str | None,
        authenticated_user_id: str,
    ) -> list[dict[str, str]]:
        if action_id != PROTECTED_ACTION_ID:
            raise ValueError(
                "This Action must be installed with the protected Broker Reports action id."
            )
        if not isinstance(body, dict):
            raise ValueError("Server intake attestation is required.")

        attestation = body.get(ACTION_ATTESTATION_KEY)
        return verify_action_attestation(
            attestation,
            action_id=action_id,
            authenticated_user_id=authenticated_user_id,
            server_secret=WEBUI_SECRET_KEY,
        )

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is not None:
            await emitter(
                {
                    "type": "status",
                    "data": {"description": description, "done": done, "hidden": False},
                }
            )
