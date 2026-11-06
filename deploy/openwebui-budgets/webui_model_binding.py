"""Native connection binding shared by the cost signing/admin adapters.

Check existing server model/cache/config owners; no catalog or inference calls.
Callers retain their guards and receive the selected native key/wire model.
"""


async def native_connection(body, model, request, ledger_base_url, *, require):
    from open_webui.models.models import Models
    from open_webui.routers.openai import get_openai_connection
    from open_webui.utils.model_ids import strip_provider_model_prefix

    require(isinstance(model, dict) and model.get("owned_by") == "openai"
            and model.get("id") == body.get("model"), "model_owner")
    record = await Models.get_model_by_id(body["model"])
    base_id = body["model"]
    if record is not None and record.base_model_id:
        base_id = getattr(request, "base_model_id", record.base_model_id)
    # Native router uses this same model record and existing cached connection row.
    entry = getattr(request.app.state, "OPENAI_MODELS", {}).get(base_id)
    require(isinstance(entry, dict) and type(entry.get("urlIdx")) is int, "native_connection")
    url, key, config = await get_openai_connection(entry["urlIdx"])
    expected = ledger_base_url.rstrip("/")
    require(bool(expected) and url.rstrip("/") in (expected, expected + "/v1")
            and config.get("auth_type", "bearer") == "bearer"
            and isinstance(key, str) and bool(key), "gateway_configuration")
    require(not config.get("azure") and config.get("provider", "") not in ("azure", "anthropic"),
            "unsupported_provider")
    return key, strip_provider_model_prefix(base_id, config.get("prefix_id"))
