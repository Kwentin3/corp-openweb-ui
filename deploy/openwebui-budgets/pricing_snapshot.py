"""Copy native request-owned billed rates into the native spend-row metadata.

Source candidate for LiteLLM d665dc1a; not enabled by this module alone.
Observed time is a capture time, never a tariff version or effective interval.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math

from litellm.integrations.custom_logger import CustomLogger
from litellm.litellm_core_utils.core_helpers import get_litellm_metadata_from_kwargs
from litellm.litellm_core_utils.litellm_logging import Logging
from litellm.litellm_core_utils.llm_cost_calc.utils import BilledTokenRates


SNAPSHOT_KEY = "owui_billed_token_rates"
RATE_FIELDS = (
    "input_cost_per_token",
    "output_cost_per_token",
    "cache_read_input_token_cost",
    "cache_read_input_audio_token_cost",
    "cache_creation_input_token_cost",
    "cache_creation_input_token_cost_above_1hr",
    "output_cost_per_reasoning_token",
)


class _RequestSnapshot(CustomLogger):
    """A dynamic native callback belonging to exactly one Logging object."""

    def __init__(self, owner: Logging):
        super().__init__()
        self._owner = owner
        self._snapshot = None

    async def async_logging_hook(self, kwargs, result, call_type):
        # Native Logging passes this object to hooks before ProxyTrackCost runs.
        # A foreign mapping must never receive another request's rates.
        if not isinstance(kwargs, dict) or kwargs is not getattr(self._owner, "model_call_details", None):
            return kwargs, result
        if getattr(self._owner, "stream", False) is True and "async_complete_streaming_response" not in kwargs:
            return kwargs, result
        params = kwargs.get("litellm_params")
        if not isinstance(params, dict):
            return kwargs, result
        metadata = get_litellm_metadata_from_kwargs(kwargs)
        # Reject the native helper's ephemeral empty fallback. Only the actual
        # selected native bucket can feed the same row writer.
        if not isinstance(metadata, dict) or not any(
            metadata is params.get(key) for key in ("metadata", "litellm_metadata")
        ):
            return kwargs, result
        spend_metadata = metadata.get("spend_logs_metadata")
        if not isinstance(spend_metadata, dict):
            return kwargs, result
        if self._snapshot is None:
            native_rates = getattr(self._owner, "billed_token_rates", None)
            rates = dict.fromkeys(RATE_FIELDS)
            if isinstance(native_rates, BilledTokenRates):
                for field in RATE_FIELDS:
                    value = getattr(native_rates, field, None)
                    if type(value) in (int, float):
                        try:
                            if math.isfinite(value):
                                rates[field] = value
                        except OverflowError:
                            pass
            present = sum(value is not None for value in rates.values())
            self._snapshot = {
                "schema": 1,
                "availability": "available" if present == len(RATE_FIELDS) else "partial" if present else "unknown",
                "observed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "rates": rates,
            }
        # Copy the representation so consumers cannot mutate the frozen capture.
        spend_metadata[SNAPSHOT_KEY] = {**self._snapshot, "rates": dict(self._snapshot["rates"])}
        return kwargs, result


class PricingSnapshot(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        owner = data.get("litellm_logging_obj") if isinstance(data, dict) else None
        if not isinstance(owner, Logging):
            return None
        callbacks = getattr(owner, "dynamic_async_success_callbacks", None) or ()
        if not any(isinstance(callback, _RequestSnapshot) and callback._owner is owner for callback in callbacks):
            owner.add_dynamic_callback(_RequestSnapshot(owner))
        return None


handler = PricingSnapshot()
