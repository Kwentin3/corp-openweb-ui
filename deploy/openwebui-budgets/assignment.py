"""Neutral representation of existing native user/model key assignments.

The key row owns assignment state. These functions are extracted unchanged from
litellm_auth.py; they neither read a catalog nor authorize or calculate budgets.
Mount as employee_budget_assignment.py beside the native config/auth module.
"""

from collections.abc import Mapping
import hashlib
import json


ASSIGNMENT_NAMESPACE = "user-model-v1"


def assignment_alias(user_id: str, model: str) -> str:
    """Canonical native key alias; this hash is an assignment ID, not a credential."""
    identity = json.dumps([user_id, model], ensure_ascii=True, separators=(",", ":"))
    return "owui-budget-v1-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def assignment_metadata(model: str) -> dict[str, str]:
    return {"owui_budget_namespace": ASSIGNMENT_NAMESPACE, "owui_budget_model": model}


def assignment_matches(record: object, user_id: str, model: str) -> bool:
    metadata = getattr(record, "metadata", None)
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            return False
    return (
        getattr(record, "user_id", None) == user_id
        and getattr(record, "team_id", None) is None
        and getattr(record, "models", None) == [model]
        and getattr(record, "key_alias", None) == assignment_alias(user_id, model)
        and isinstance(metadata, Mapping)
        and all(metadata.get(key) == value for key, value in assignment_metadata(model).items())
    )
