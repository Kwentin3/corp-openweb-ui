from __future__ import annotations

from io import BytesIO
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from .blockers import corrupt_file, parser_failed
from .contracts import profile_id, slice_id


def profile_docx(run_id: str, document_id: str, content_bytes: bytes) -> tuple[dict, list[dict], list[dict]]:
    current_profile_id = profile_id(document_id)
    try:
        with ZipFile(BytesIO(content_bytes)) as archive:
            if "word/document.xml" not in archive.namelist():
                blocker = parser_failed(run_id, document_id, "docx_document_xml_missing")
                return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]
            root = ET.fromstring(archive.read("word/document.xml"))
    except BadZipFile:
        blocker = corrupt_file(run_id, document_id, "bad_docx_zip")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]
    except ET.ParseError as exc:
        blocker = corrupt_file(run_id, document_id, f"docx_xml_invalid:{exc.__class__.__name__}")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    paragraphs = []
    headings_count = 0
    for paragraph in _iter_local(root, "p"):
        text = "".join(node.text or "" for node in _iter_local(paragraph, "t")).strip()
        if text:
            paragraphs.append(text)
        styles = [node.attrib.get(_w_attr("val"), "") for node in _iter_local(paragraph, "pStyle")]
        if any(style.lower().startswith("heading") for style in styles):
            headings_count += 1
    tables_count = sum(1 for _ in _iter_local(root, "tbl"))

    private_slices = []
    normalized_slice_refs = []
    if paragraphs:
        snippet = "\n".join(paragraphs[:20])[:2000]
        private_slice = {
            "slice_id": slice_id(document_id, "docx_text_001"),
            "document_id": document_id,
            "profile_id": current_profile_id,
            "slice_type": "text_excerpt",
            "source_location": {
                "kind": "docx_paragraphs",
                "paragraph_start": 1,
                "paragraph_end": min(len(paragraphs), 20),
            },
            "location": {
                "kind": "docx_paragraphs",
                "paragraph_start": 1,
                "paragraph_end": min(len(paragraphs), 20),
            },
            "bounded": True,
            "characters_in_slice": len(snippet),
            "chars_count": len(snippet),
            "truncated": len(paragraphs) > 20 or len("\n".join(paragraphs[:20])) > len(snippet),
            "parser": "python_stdlib_docx_zip_xml",
            "created_for_gate": "gate1",
            "text": snippet,
        }
        private_slices.append(private_slice)
        normalized_slice_refs.append(private_slice["slice_id"])

    profile = {
        "profile_id": current_profile_id,
        "document_id": document_id,
        "container_format": "docx",
        "parser": "python_stdlib_docx_zip_xml",
        "parser_version": "1",
        "profile_status": "profiled",
        "machine_readable": "conditional",
        "machine_readable_table": tables_count > 0,
        "document_readable": True,
        "paragraphs_count": len(paragraphs),
        "headings_count": headings_count,
        "tables_count": tables_count,
        "role_candidate": "source_broker_report" if _has_broker_signal(paragraphs) else "unknown_or_needs_review",
        "normalized_slice_refs": normalized_slice_refs,
        "warnings": [],
        "blocker_refs": [],
    }
    return profile, private_slices, []


def _iter_local(root: ET.Element, local_name: str):
    return (node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == local_name)


def _w_attr(local_name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{local_name}"


def _has_broker_signal(paragraphs: list[str]) -> bool:
    text = "\n".join(paragraphs).lower()
    return "broker" in text or "account" in text


def _blocked_profile(document_id: str, blocker_refs: list[str]) -> dict:
    return {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "docx",
        "parser": "python_stdlib_docx_zip_xml",
        "parser_version": "1",
        "profile_status": "blocked",
        "machine_readable": "unknown",
        "machine_readable_table": False,
        "document_readable": False,
        "paragraphs_count": 0,
        "headings_count": 0,
        "tables_count": 0,
        "role_candidate": "unknown_or_needs_review",
        "normalized_slice_refs": [],
        "warnings": ["parser_failed"],
        "blocker_refs": blocker_refs,
    }
