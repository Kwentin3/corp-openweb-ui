from __future__ import annotations

import copy
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass

from . import blockers as blocker_factory
from .contracts import (
    NORMALIZER_VERSION,
    SUPPORTED_CONTRACTS,
    document_id,
    normalization_run_id,
    profile_id,
    safe_artifact_refs,
    safety_flags,
    taxonomy_candidate_id,
)
from .detectors import detect_container, extension_from_name, machine_readable_baseline
from .domain_ingestion import apply_domain_ingestion_artifacts
from .eligibility import build_document_source_eligibility
from .full_source import FullSourceArtifactConfig, FullSourceArtifactFactory
from .inputs import FileInput
from .profilers_csv_txt import profile_csv, profile_txt
from .profilers_docx import profile_docx
from .profilers_image import profile_image
from .profilers_pdf import profile_pdf
from .profilers_xlsx import profile_xlsx
from .profilers_zip import profile_zip
from .safe_report import render_privacy_failed_report, render_safe_report
from .source_provenance import NormalizedSliceProvenanceFactory
from .taxonomy import classify_document
from .validators import merge_validation_results, validate_artifacts, validate_safe_report


@dataclass
class NormalizationResult:
    package: dict
    safe_report: dict
    private_markers: list[str]


class Gate1Normalizer:
    def normalize(
        self,
        file_inputs: list[FileInput],
        *,
        entrypoint: str = "broker_reports_gate1_backend_core",
        trigger_type: str = "backend_core",
        input_context: dict | None = None,
        extra_private_markers: list[str] | None = None,
    ) -> NormalizationResult:
        input_summaries = [self._input_summary(item) for item in file_inputs]
        run_id = normalization_run_id(input_summaries)
        artifact_refs = safe_artifact_refs(run_id)
        private_markers = []
        for item in file_inputs:
            private_markers.extend(item.private_markers())
        private_markers.extend(extra_private_markers or [])

        documents: list[dict] = []
        profiles: list[dict] = []
        private_slices: list[dict] = []
        private_source_payloads: list[dict] = []
        private_source_units: list[dict] = []
        full_source_document_summaries: list[dict] = []
        taxonomy_candidates: list[dict] = []
        blockers: list[dict] = []
        sha_to_first_doc: dict[str, str] = {}
        sha_counts: Counter[str] = Counter()
        doc_private_slices: dict[str, list[dict]] = defaultdict(list)
        slice_provenance = NormalizedSliceProvenanceFactory().create()
        full_source_builder = FullSourceArtifactFactory(
            FullSourceArtifactConfig(
                enable_pdf_layout_slice2=(
                    (input_context or {}).get("pdf_layout_slice2_enabled") is not False
                )
            )
        ).create()

        if not file_inputs:
            blockers.append(blocker_factory.no_files(run_id))

        for index, file_input in enumerate(file_inputs, start=1):
            extension = extension_from_name(file_input.original_filename_private, file_input.mime_type)
            read_result = file_input.read_bytes()
            content_bytes = read_result.content_bytes if read_result.status == "available" else None
            content_sha256 = hashlib.sha256(content_bytes).hexdigest() if content_bytes is not None else None
            doc_id = document_id(
                index=index,
                content_sha256=content_sha256,
                private_ref_hash=file_input.private_ref_hash,
                extension=extension,
                mime_type=file_input.mime_type,
            )
            detection = detect_container(
                extension=extension,
                mime_type=file_input.mime_type,
                content_bytes=content_bytes,
            )
            container = detection["container_format"]

            doc_blockers: list[dict] = []
            if content_sha256:
                sha_counts[content_sha256] += 1
                duplicate_of = sha_to_first_doc.get(content_sha256)
                duplicate_group_id = f"dupgrp_{content_sha256[:12]}"
                if duplicate_of:
                    duplicate_blocker = blocker_factory.duplicate_review(run_id, doc_id)
                    doc_blockers.append(duplicate_blocker)
                else:
                    sha_to_first_doc[content_sha256] = doc_id
            else:
                duplicate_of = None
                duplicate_group_id = None

            if read_result.status != "available":
                doc_blockers.append(blocker_factory.bytes_unavailable(run_id, doc_id, read_result.reason))

            if container == "unknown":
                doc_blockers.append(blocker_factory.unsupported_format(run_id, doc_id))
            elif container in {"xls"}:
                doc_blockers.append(blocker_factory.unsupported_format(run_id, doc_id))

            profile = None
            new_slices: list[dict] = []
            profile_blockers: list[dict] = []
            if content_bytes is not None:
                if container == "csv":
                    profile, new_slices, profile_blockers = profile_csv(run_id, doc_id, content_bytes)
                elif container == "txt":
                    profile, new_slices, profile_blockers = profile_txt(run_id, doc_id, content_bytes)
                elif container == "html_text":
                    profile, new_slices, profile_blockers = profile_txt(
                        run_id,
                        doc_id,
                        content_bytes,
                        container_format="html_text",
                        text_subtype="html_text",
                    )
                elif container == "zip":
                    profile, new_slices, profile_blockers = profile_zip(run_id, doc_id, content_bytes)
                elif container == "xlsx":
                    profile, new_slices, profile_blockers = profile_xlsx(run_id, doc_id, content_bytes)
                elif container == "pdf":
                    profile, new_slices, profile_blockers = profile_pdf(run_id, doc_id, content_bytes)
                elif container == "docx":
                    profile, new_slices, profile_blockers = profile_docx(run_id, doc_id, content_bytes)
                elif container == "image":
                    profile, new_slices, profile_blockers = profile_image(run_id, doc_id, content_bytes)

            doc_blockers.extend(profile_blockers)
            blockers.extend(doc_blockers)
            if new_slices:
                new_slices = slice_provenance.enrich_slices(
                    normalization_run_id=run_id,
                    document_id=doc_id,
                    source_checksum_sha256=str(content_sha256 or ""),
                    slices=new_slices,
                )
            if profile is not None:
                profile["blocker_refs"] = sorted(
                    set(profile.get("blocker_refs", []))
                    | {item["blocker_id"] for item in doc_blockers}
                )
                profiles.append(profile)
            private_slices.extend(new_slices)
            doc_private_slices[doc_id].extend(new_slices)

            if content_bytes is not None and content_sha256:
                full_source_result = full_source_builder.build(
                    normalization_run_id=run_id,
                    document_id=doc_id,
                    profile_id=profile["profile_id"] if profile else profile_id(doc_id),
                    container_format=container,
                    content_bytes=content_bytes,
                    source_checksum_sha256=content_sha256,
                )
                private_source_payloads.extend(full_source_result.payloads)
                private_source_units.extend(full_source_result.units)
                full_source_document_summaries.append(full_source_result.summary)

            declared_size = file_input.declared_size_bytes
            size_bytes = len(content_bytes) if content_bytes is not None else declared_size
            document = {
                "document_id": doc_id,
                "source_kind": file_input.source_kind,
                "sha256": content_sha256,
                "size_bytes": size_bytes,
                "bytes_status": read_result.status,
                "duplicate_group_id": duplicate_group_id,
                "duplicate_of_document_id": duplicate_of,
                "container_format": container,
                "container_confidence": detection["confidence"],
                "container_detection_basis": detection["basis"],
                "declared_mime_type": file_input.mime_type or None,
                "extension": extension or None,
                "technical_profile_ref": profile["profile_id"] if profile else profile_id(doc_id),
                "taxonomy_candidate_ref": taxonomy_candidate_id(doc_id),
                "readable": "yes" if content_bytes is not None else "conditional",
                "read_error_class": None if content_bytes is not None else "bytes_unavailable",
                "machine_readable": profile.get("machine_readable") if profile else machine_readable_baseline(container),
                "blocker_refs": [item["blocker_id"] for item in doc_blockers],
            }
            documents.append(document)

        blockers_by_doc: dict[str, list[dict]] = defaultdict(list)
        for blocker in blockers:
            doc_id = blocker.get("document_id")
            if doc_id:
                blockers_by_doc[doc_id].append(blocker)

        source_policy_context = self._source_policy_context(input_context or {})
        for document in documents:
            profile = next(
                (item for item in profiles if item.get("document_id") == document["document_id"]),
                None,
            )
            doc_blocker_codes = {item["code"] for item in blockers_by_doc.get(document["document_id"], [])}
            taxonomy_candidate = classify_document(
                document=document,
                profile=profile,
                private_slices=doc_private_slices.get(document["document_id"], []),
                blocker_codes=doc_blocker_codes,
                source_policy_context=source_policy_context,
                source_policy_hint=self._source_policy_hint_for_document(document, source_policy_context),
            )
            if (
                taxonomy_candidate["document_class_candidate"] == "unknown_or_needs_review"
                and "bytes_unavailable" not in doc_blocker_codes
            ):
                role_blocker = blocker_factory.unknown_role(run_id, document["document_id"])
                blockers.append(role_blocker)
                document["blocker_refs"].append(role_blocker["blocker_id"])
                doc_blocker_codes.add(role_blocker["code"])
                taxonomy_candidate["requires_review"] = True
            taxonomy_candidates.append(taxonomy_candidate)

        blocker_ids_by_doc: dict[str, list[str]] = defaultdict(list)
        for blocker in blockers:
            doc_id = blocker.get("document_id")
            if doc_id:
                blocker_ids_by_doc[doc_id].append(blocker["blocker_id"])
        for document in documents:
            document["blocker_refs"] = sorted(set(blocker_ids_by_doc.get(document["document_id"], [])))

        document_source_eligibility, source_eligibility_summary, gate2_handoff = (
            build_document_source_eligibility(
                run_id=run_id,
                documents=documents,
                taxonomy_candidates=taxonomy_candidates,
                blockers=blockers,
                ocr_policy_status=self._ocr_policy_status(input_context or {}),
                input_context=input_context or {},
                criticality_refinement_enabled=self._criticality_refinement_enabled(input_context or {}),
            )
        )
        summary_counts = self._summary_counts(documents, taxonomy_candidates, blockers, sha_counts)
        full_source_coverage_summary = self._full_source_coverage_summary(
            documents=full_source_document_summaries,
            payloads=private_source_payloads,
            units=private_source_units,
        )
        summary_counts["full_source_coverage_counts"] = copy.deepcopy(
            full_source_coverage_summary["status_counts"]
        )
        summary_counts["source_eligibility_counts"] = dict(
            source_eligibility_summary.get("status_counts", {})
        )
        run_status = self._run_status(file_inputs, blockers)
        gate2_handoff_status = gate2_handoff["gate2_handoff_status"]
        gate2_handoff_mode = gate2_handoff["handoff_mode"]
        normalization_run = {
            "schema_version": "normalization_run_v0",
            "run_id": run_id,
            "entrypoint": entrypoint,
            "trigger_type": trigger_type,
            "normalizer_version": NORMALIZER_VERSION,
            "run_status": run_status,
            "files_total": len(file_inputs),
            "artifacts_created": list(artifact_refs.keys()),
            "privacy_validation_status": "pending",
            "gate2_handoff_status": gate2_handoff_status,
            "gate2_handoff_mode": gate2_handoff_mode,
            "safety_flags": safety_flags(),
        }
        package = {
            "schema_version": "broker_reports_gate1_normalization_package_v0",
            "trigger_type": trigger_type,
            "entrypoint": entrypoint,
            "normalizer_version": NORMALIZER_VERSION,
            "input_context": input_context or {},
            "supported_contracts": list(SUPPORTED_CONTRACTS),
            "safe_artifact_refs": artifact_refs,
            "normalization_run": normalization_run,
            "document_inventory": {
                "schema_version": "document_inventory_v0",
                "run_id": run_id,
                "documents": documents,
            },
            "technical_readability_profiles": profiles,
            "private_normalized_slices": private_slices,
            "private_normalized_source_payloads": private_source_payloads,
            "private_normalized_source_units": private_source_units,
            "full_source_coverage_summary": full_source_coverage_summary,
            "taxonomy_candidates": taxonomy_candidates,
            "normalization_blockers": blockers,
            "document_source_eligibility": document_source_eligibility,
            "source_eligibility_summary": source_eligibility_summary,
            "gate2_handoff": gate2_handoff,
            "summary_counts": summary_counts,
            "recommended_next_step": self._recommended_next_step(file_inputs, blockers, gate2_handoff),
        }
        package = apply_domain_ingestion_artifacts(package)
        artifact_validation = validate_artifacts(package)
        package["validation_result"] = artifact_validation
        safe_report = render_safe_report(package)
        safe_validation = validate_safe_report(
            safe_report=safe_report,
            private_markers=private_markers,
            run_id=run_id,
        )
        validation = merge_validation_results(artifact_validation, safe_validation)
        if validation["status"] == "privacy_failed":
            privacy_blocker = validation["privacy_blocker"]
            package["normalization_blockers"].append(privacy_blocker)
            package["normalization_run"]["run_status"] = "privacy_failed"
            package["normalization_run"]["privacy_validation_status"] = "failed"
            package["normalization_run"]["gate2_handoff_status"] = "blocked"
            package["normalization_run"]["gate2_handoff_mode"] = "gate2_blocked_no_eligible_sources"
            package["gate2_handoff"]["handoff_mode"] = "gate2_blocked_no_eligible_sources"
            package["gate2_handoff"]["gate2_handoff_status"] = "blocked"
            package["summary_counts"]["blockers_total"] = len(package["normalization_blockers"])
            package["validation_result"] = validation
            safe_report = render_privacy_failed_report(
                run_id=run_id,
                files_total=len(file_inputs),
                input_context=input_context,
            )
        else:
            package["normalization_run"]["privacy_validation_status"] = validation["status"]
            package["validation_result"] = validation
            safe_report = render_safe_report(package)
        return NormalizationResult(package=package, safe_report=safe_report, private_markers=private_markers)

    def _full_source_coverage_summary(
        self,
        *,
        documents: list[dict],
        payloads: list[dict],
        units: list[dict],
    ) -> dict:
        status_counts = Counter(
            str(item.get("parser_completeness_status") or "blocked") for item in documents
        )
        format_status_counts: dict[str, Counter] = defaultdict(Counter)
        for item in documents:
            format_status_counts[str(item.get("container_format") or "unknown")][
                str(item.get("parser_completeness_status") or "blocked")
            ] += 1
        return {
            "schema_version": "full_source_coverage_summary_v0",
            "documents_total": len(documents),
            "status_counts": dict(sorted(status_counts.items())),
            "format_status_counts": {
                key: dict(sorted(value.items()))
                for key, value in sorted(format_status_counts.items())
            },
            "payloads_total": len(payloads),
            "extraction_units_total": len(units),
            "rows_total": sum(int(item.get("rows_total") or 0) for item in payloads),
            "text_characters_total": sum(
                int(item.get("text_characters_total") or 0) for item in payloads
            ),
            "full_coverage_documents_total": sum(
                1 for item in documents if item.get("full_coverage_available") is True
            ),
            "documents": copy.deepcopy(documents),
            "preview_artifacts_are_coverage_authority": False,
            "customer_docs_loaded_to_knowledge": False,
            "vectorization_performed": False,
        }

    def _input_summary(self, file_input: FileInput) -> dict:
        extension = extension_from_name(file_input.original_filename_private, file_input.mime_type)
        return {
            "private_ref_hash": file_input.private_ref_hash,
            "extension": extension,
            "mime_type": file_input.mime_type,
        }

    def _source_policy_context(self, input_context: dict) -> dict:
        value = input_context.get("source_policy")
        return value if isinstance(value, dict) else {}

    def _source_policy_hint_for_document(self, document: dict, source_policy_context: dict) -> dict:
        hints = source_policy_context.get("safe_registry_role_hints")
        if not isinstance(hints, list):
            return {}
        sha256 = str(document.get("sha256") or "")
        if not sha256:
            return {}
        for hint in hints:
            if not isinstance(hint, dict):
                continue
            full_sha = str(hint.get("sha256") or "")
            prefix = str(hint.get("sha256_prefix") or hint.get("hash_prefix") or "")
            if full_sha and full_sha == sha256:
                return hint
            if prefix and sha256.startswith(prefix):
                return hint
        return {}

    def _summary_counts(
        self,
        documents: list[dict],
        taxonomy_candidates: list[dict],
        blockers: list[dict],
        sha_counts: Counter[str],
    ) -> dict:
        container_counts = Counter(document["container_format"] for document in documents)
        class_counts = Counter(
            item["document_class_candidate"] for item in taxonomy_candidates
        )
        duplicate_hashes = sum(1 for count in sha_counts.values() if count > 1)
        duplicate_count = sum(1 for document in documents if document.get("duplicate_of_document_id"))
        return {
            "files_total": len(documents),
            "container_counts": dict(sorted(container_counts.items())),
            "document_class_counts": dict(sorted(class_counts.items())),
            "duplicate_count": duplicate_count,
            "duplicate_hashes": duplicate_hashes,
            "blockers_total": len(blockers),
        }

    def _run_status(self, file_inputs: list[FileInput], blockers: list[dict]) -> str:
        if not file_inputs:
            return "failed_safe"
        blocking = any(blocker.get("blocks_gate2") for blocker in blockers)
        return "completed_with_blockers" if blocking or blockers else "completed"

    def _recommended_next_step(
        self,
        file_inputs: list[FileInput],
        blockers: list[dict],
        gate2_handoff: dict,
    ) -> str:
        codes = {blocker["code"] for blocker in blockers}
        if not file_inputs:
            return "attach_synthetic_files_and_retry"
        if "bytes_unavailable" in codes:
            return "verify_pipe_byte_access_boundary"
        mode = gate2_handoff.get("handoff_mode")
        if mode == "reduced_subset_ready_for_gate2":
            return "continue_with_reduced_gate2_subset_after_specialist_confirmation"
        if mode == "gate2_blocked_requires_ocr":
            return "route_ocr_candidates_to_future_ocr_gate_or_manual_review"
        if mode == "gate2_blocked_requires_metadata_review":
            return "review_document_metadata_passports"
        if mode == "gate2_blocked_requires_policy_review":
            return "confirm_source_policy_for_candidate_documents"
        if mode == "gate2_blocked_requires_duplicate_resolution":
            return "choose_canonical_duplicate_documents"
        if mode == "gate2_blocked_no_eligible_sources":
            return "attach_supported_source_documents_or_review_package"
        if blockers:
            return "review_gate1_blockers"
        return "ready_for_gui_smoke"

    def _ocr_policy_status(self, input_context: dict) -> str:
        value = (
            input_context.get("ocr_policy_status")
            or input_context.get("ocr_policy")
            or input_context.get("ocr_gate1_policy")
        )
        if value in {"enabled", "ocr_enabled"}:
            return "enabled-not-executed"
        if value in {"required-before-gate2", "manual-review-only", "enabled-not-executed", "disabled"}:
            return str(value)
        return "disabled"

    def _criticality_refinement_enabled(self, input_context: dict) -> bool:
        return bool(
            input_context.get("clarification_criticality_refinement_enabled") is True
            or input_context.get("criticality_refinement_enabled") is True
            or input_context.get("metadata_criticality_refinement_enabled") is True
        )
