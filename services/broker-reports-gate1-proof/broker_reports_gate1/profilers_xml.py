from __future__ import annotations

from .blockers import parser_failed
from .contracts import profile_id
from .xml_source import XmlNeutralMemoryError, XmlNeutralMemoryFactory


def profile_xml(
    run_id: str, document_id: str, content_bytes: bytes
) -> tuple[dict, list[dict], list[dict]]:
    try:
        parsed = XmlNeutralMemoryFactory().create().parse(content_bytes)
    except XmlNeutralMemoryError as exc:
        blocker = parser_failed(run_id, document_id, exc.code)
        return (
            {
                "profile_id": profile_id(document_id),
                "document_id": document_id,
                "container_format": "xml",
                "parser": "python_expat_neutral_events",
                "parser_version": "stdlib",
                "profile_status": "blocked",
                "machine_readable": "no",
                "machine_readable_table": False,
                "xml_neutral_profile_status": "blocked",
                "safe_structural_inventory": {},
                "normalized_slice_refs": [],
                "warnings": [exc.code],
                "blocker_refs": [blocker["blocker_id"]],
            },
            [],
            [blocker],
        )
    return (
        {
            "profile_id": profile_id(document_id),
            "document_id": document_id,
            "container_format": "xml",
            "parser": "python_expat_neutral_events",
            "parser_version": "stdlib",
            "profile_status": "profiled",
            "machine_readable": "yes",
            "machine_readable_table": True,
            "xml_neutral_profile_status": "accepted",
            "safe_structural_inventory": parsed.safe_inventory,
            "normalized_slice_refs": [],
            "warnings": [],
            "blocker_refs": [],
        },
        [],
        [],
    )
