"""Stand composition only: native guardrail plus the existing private operator."""
from unknown_usage_guard import UnknownUsageGuard
from provision_webui import OPERATOR_STATE, PROXY_URL, read_private
from prove_native_budgets import require


def operator_key():
    token = read_private(OPERATOR_STATE).get('operator_token')
    require(isinstance(token, str) and token.startswith('sk-'),
            'Usage guard requires the existing native operator')
    return token


# The secret is read on an eligible missing-Usage call, after native bootstrap.
handler = UnknownUsageGuard(operator_key=operator_key, base_url=PROXY_URL)
