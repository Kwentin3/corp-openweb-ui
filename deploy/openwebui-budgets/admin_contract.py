"""Server-only read DTOs of native scalar budgets; no allocation policy.

key_hash is a native object identifier for management calls, never a credential.
Callers must project DTOs before sending data to HTML, model context or receipts.
"""

from dataclasses import dataclass
from decimal import Decimal


class BudgetAdminError(Exception):
    """Fixed safe code only; never include HTTP bodies, URLs or credentials."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ModelBudget:
    model: str
    key_hash: str
    key_alias: str
    max_budget: Decimal | None
    spend: Decimal
    budget_duration: str | None
    budget_reset_at: str | None
    blocked: bool | None


@dataclass(frozen=True)
class EmployeeBudget:
    user_id: str
    max_budget: Decimal | None
    spend: Decimal
    budget_duration: str | None
    budget_reset_at: str | None
    models: tuple[ModelBudget, ...]
