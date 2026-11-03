"""Presentation-only native budget failures; mount beside the LiteLLM config.

Configure ``litellm_settings.callbacks: ["budget_errors.handler"]``. Native
authentication, common checks and reservation remain the only budget owners.
This exact 1.105.1 failure-hook path reuses the original BudgetExceededError
after callbacks return None, preserving its status and budget_exceeded type.
"""

from functools import lru_cache

from litellm import BudgetExceededError
from litellm.integrations.custom_logger import CustomLogger


USER_MESSAGE = ("Недостаточно общего бюджета для этого запроса. Уменьшите запрос "
                "или обратитесь к администратору для изменения лимита.")
MODEL_MESSAGE = ("Недостаточно бюджета этой модели для запроса. Уменьшите запрос, "
                 "выберите другую разрешённую модель или обратитесь к администратору.")
GENERIC_MESSAGE = ("Недостаточно бюджета для этого запроса. Уменьшите запрос "
                   "или обратитесь к администратору.")


@lru_cache(maxsize=1)
def _assignment_matcher():
    # Preserve native config-file loading order and the shared contract owner.
    from litellm.proxy.types_utils.utils import get_instance_fn

    return get_instance_fn("employee_budget_assignment.assignment_matches", config_file_path=__file__)


def _canonical_model_key(error: BudgetExceededError, identity: object) -> bool:
    user_id = getattr(identity, "user_id", None)
    models = getattr(identity, "models", None)
    if not (isinstance(user_id, str) and user_id
            and isinstance(models, list) and len(models) == 1
            and isinstance(models[0], str) and models[0]
            and isinstance(error.entity_id, str) and error.entity_id
            and error.entity_id == getattr(identity, "token", None)):
        return False
    try:
        return _assignment_matcher()(identity, user_id, models[0])
    except Exception:
        # Presentation must remain safe if the optional assignment owner cannot
        # load or its representation is invalid. Native denial still propagates.
        return False


class BudgetErrors(CustomLogger):
    async def async_post_call_failure_hook(
        self, request_data: dict, original_exception: Exception,
        user_api_key_dict: object, traceback_str: str | None = None,
    ) -> None:
        if not isinstance(original_exception, BudgetExceededError):
            return None
        if original_exception.entity_type == "user":
            message = USER_MESSAGE
        elif original_exception.entity_type == "key":
            message = (MODEL_MESSAGE if _canonical_model_key(original_exception, user_api_key_dict)
                       else GENERIC_MESSAGE)
        else:
            return None
        original_exception.message = message
        original_exception.args = (message,)
        return None


handler = BudgetErrors()
