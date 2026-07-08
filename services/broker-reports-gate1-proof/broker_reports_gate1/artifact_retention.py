from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .artifact_models import RETENTION_MODES, RetentionPolicy


DEFAULT_TTL_SECONDS = {
    "synthetic_dev": 7 * 24 * 60 * 60,
    "api_smoke": 24 * 60 * 60,
    "customer_approved_test": 14 * 24 * 60 * 60,
    "expires_after_ttl": 24 * 60 * 60,
}

EXPLICIT_POLICY_REQUIRED = {"customer_approved_test", "production_case"}


class RetentionPolicyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def build_retention_policy(
    *,
    mode: str,
    explicit: bool = False,
    ttl_seconds: int | None = None,
    now: datetime | None = None,
    source_delete_cascades: bool = True,
    chat_delete_cascades: bool = True,
    keep_redacted_tombstone: bool = True,
    requires_manual_purge: bool | None = None,
) -> RetentionPolicy:
    if mode not in RETENTION_MODES:
        raise RetentionPolicyError("retention_policy_missing", f"Unsupported retention mode: {mode}")
    if mode in EXPLICIT_POLICY_REQUIRED and not explicit:
        raise RetentionPolicyError(
            "retention_policy_missing",
            f"{mode} requires an explicit retention policy",
        )
    manual = mode == "manual_purge_required" if requires_manual_purge is None else requires_manual_purge
    if mode == "production_case" and ttl_seconds is None:
        raise RetentionPolicyError(
            "retention_policy_missing",
            "production_case requires explicit ttl_seconds or a future contract policy",
        )
    resolved_ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL_SECONDS.get(mode)
    resolved_now = now or datetime.now(timezone.utc)
    expires_at = None
    if not manual and resolved_ttl is not None:
        expires_at = (resolved_now + timedelta(seconds=resolved_ttl)).isoformat()
    return RetentionPolicy(
        mode=mode,
        ttl_seconds=resolved_ttl,
        expires_at=expires_at,
        source_delete_cascades=source_delete_cascades,
        chat_delete_cascades=chat_delete_cascades,
        keep_redacted_tombstone=keep_redacted_tombstone,
        requires_manual_purge=manual,
        explicit=explicit,
    )
