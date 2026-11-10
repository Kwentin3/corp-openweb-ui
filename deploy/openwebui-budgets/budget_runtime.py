"""Release registration for the existing native Usage policy.

The release environment owns its restricted native operator credential.
Validate it at registration and retrieve it again for native management access.
"""

import os

from unknown_usage_guard import CCStreamUsageGuard, ResponsesUsageGuard, UnknownUsageGuard


def operator_key() -> str:
    key = os.environ.get("OWUI_BUDGET_OPERATOR_KEY", "")
    if not key.startswith("sk-") or len(key) <= 3 or any(char.isspace() for char in key):
        raise ValueError("invalid_budget_operator_key")
    return key


operator_key()
handler = UnknownUsageGuard(operator_key=operator_key, base_url="http://127.0.0.1:4000")
responses_handler = ResponsesUsageGuard(operator_key=operator_key, base_url="http://127.0.0.1:4000")
cc_stream_handler = CCStreamUsageGuard(operator_key=operator_key, base_url="http://127.0.0.1:4000")
