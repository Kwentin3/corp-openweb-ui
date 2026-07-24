from __future__ import annotations


FINANCIAL_CONTEXT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_context_v1"
)
FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION = (
    "broker_reports_gate2_financial_context_projection_v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialContextProjectionFactory.create is the only production "
    "model-facing financial context projection entrypoint"
)
FORBIDDEN = (
    "Prompts and models must not build, deduplicate or enrich Gate 2 context "
    "with raw Gate 1 representations, tax methodology or answer fields"
)

STATUSES = frozenset(
    {
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    }
)
AGGREGATE_SEMANTICS = frozenset(
    {
        "not_aggregate",
        "not_applicable",
        "source_printed",
        "unclassified",
    }
)


class Gate2FinancialContextProjectionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def fail(code: str) -> None:
    raise Gate2FinancialContextProjectionError(code)
