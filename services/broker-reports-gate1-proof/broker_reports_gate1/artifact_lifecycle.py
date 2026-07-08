from __future__ import annotations

from .artifact_models import LIFECYCLE_STATUSES


ALLOWED_TRANSITIONS = {
    "created": {"validated", "blocked", "privacy_failed"},
    "validated": {"visible_safe", "private_ready", "expired", "purge_pending"},
    "visible_safe": {"expired", "purge_pending"},
    "private_ready": {"expired", "purge_pending"},
    "blocked": {"purge_pending"},
    "expired": {"purge_pending"},
    "privacy_failed": {"purge_pending"},
    "purge_pending": {"purged"},
    "purged": set(),
}


class ArtifactLifecycleError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def lifecycle_for_visibility(*, visibility: str, validation_status: str) -> str:
    if validation_status == "privacy_failed":
        return "privacy_failed"
    if validation_status == "blocked":
        return "blocked"
    if visibility == "chat_visible":
        return "visible_safe"
    if visibility == "private_case":
        return "private_ready"
    return "validated"


def assert_transition(current: str, target: str) -> None:
    if current not in LIFECYCLE_STATUSES or target not in LIFECYCLE_STATUSES:
        raise ArtifactLifecycleError("artifact_blocked", f"Unsupported lifecycle transition {current}->{target}")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ArtifactLifecycleError("artifact_blocked", f"Invalid lifecycle transition {current}->{target}")
