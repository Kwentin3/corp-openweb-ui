"""Server-only read DTOs of native scalar budgets; no allocation policy.

key_hash is a native object identifier for management calls, never a credential.
Callers must project DTOs before sending data to HTML, model context or receipts.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


class BudgetAdminError(Exception):
    """Fixed safe code only; never include HTTP bodies, URLs or credentials."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelBudget:
    model: str
    key_hash: str | None
    key_alias: str | None
    max_budget: Decimal | None
    spend: Decimal | None
    budget_duration: str | None
    budget_reset_at: str | None
    blocked: bool | None
    pending: bool = False


@dataclass(frozen=True)
class EmployeeBudget:
    user_id: str
    max_budget: Decimal | None
    spend: Decimal
    budget_duration: str | None
    budget_reset_at: str | None
    models: tuple[ModelBudget, ...]


@dataclass(frozen=True)
class EmployeeBudgetInspection:
    """Read-only observation, never permission to create or repair native state.

    Only ready carries a budget; other states carry fixed safe codes. Absence
    requires both native user/info 404 and a complete, empty exact key/list.
    """

    user_id: str
    allowed_wire_models: tuple[str, ...]
    kind: Literal["absent", "ready", "incomplete", "conflict"]
    employee_budget: EmployeeBudget | None = None
    code: str | None = None
