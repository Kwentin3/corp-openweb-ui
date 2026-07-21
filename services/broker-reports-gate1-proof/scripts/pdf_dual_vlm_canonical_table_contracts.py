"""Compatibility import for the promoted canonical-table contract.

Historical benchmark runners retain their import path while the sole contract
implementation is bundled from ``broker_reports_gate1``.
"""

from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import *  # noqa: F401,F403
