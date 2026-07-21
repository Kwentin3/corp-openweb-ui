"""
title: Broker Reports Private Intake Action
author: Alpha Soft
version: 1.0.0
required_open_webui_version: 0.9.6
"""

from __future__ import annotations

import hashlib
from typing import Any


PROTECTED_ACTION_ID = "broker_reports_private_intake_action"
ACTION_ATTESTATION_KEY = "broker_reports_server_intake_attestation"
ACTION_ATTESTATION_SCHEMA_VERSION = "broker_reports_action_intake_attestation_v1"
RECEIPT_SCHEMA_VERSION = "broker_reports_private_source_receipt_v1"
FACTORY_REQUIRED = "broker_reports_private_intake_factory_v1"


class Action:
    """Production intake handoff; generic OpenWebUI file refs are never read."""

    async def action(
        self,
        body: dict,
        __id__: str | None = None,
        __event_emitter__=None,
    ) -> dict[str, Any]:
        await self._emit(__event_emitter__, "Verifying private intake receipts...", done=False)
        sources = self._verified_sources(body, action_id=__id__)
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

    def _verified_sources(self, body: Any, *, action_id: str | None) -> list[dict[str, str]]:
        if action_id != PROTECTED_ACTION_ID:
            raise ValueError(
                "This Action must be installed with the protected Broker Reports action id."
            )
        if not isinstance(body, dict):
            raise ValueError("Server intake attestation is required.")

        attestation = body.get(ACTION_ATTESTATION_KEY)
        if not isinstance(attestation, dict):
            raise ValueError("Generic OpenWebUI file refs are ineligible without a server receipt.")
        if attestation.get("schema_version") != ACTION_ATTESTATION_SCHEMA_VERSION:
            raise ValueError("Server intake attestation schema is invalid.")
        if attestation.get("guard") != FACTORY_REQUIRED:
            raise ValueError("Server intake guard identity is invalid.")

        sources = attestation.get("sources")
        if not isinstance(sources, list) or not sources or len(sources) > 128:
            raise ValueError("Server intake attestation must contain 1-128 sources.")

        verified: list[dict[str, str]] = []
        seen: set[str] = set()
        for source in sources:
            if not isinstance(source, dict):
                raise ValueError("Server intake source receipt is invalid.")
            source_id = str(source.get("source_id") or "")
            receipt_id = str(source.get("receipt_id") or "")
            if not source_id.startswith("br-"):
                raise ValueError("Generic OpenWebUI file ref is ineligible.")
            if source.get("receipt_schema_version") != RECEIPT_SCHEMA_VERSION:
                raise ValueError("Server receipt schema is invalid.")
            if len(receipt_id) != 64 or any(ch not in "0123456789abcdef" for ch in receipt_id):
                raise ValueError("Server receipt identity is invalid.")
            if source_id in seen:
                raise ValueError("Duplicate server receipt source is invalid.")
            seen.add(source_id)
            verified.append({"source_id": source_id, "receipt_id": receipt_id})
        return verified

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is not None:
            await emitter(
                {
                    "type": "status",
                    "data": {"description": description, "done": done, "hidden": False},
                }
            )
