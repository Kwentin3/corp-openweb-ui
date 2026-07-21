"""Compatibility import for the promoted maintained dual-VLM provider stack.

The implementation moved into ``broker_reports_gate1``.  Historical benchmark
runners keep this module name, but no second adapter or transport lives here.
"""

from broker_reports_gate1.pdf_dual_vlm_fact_providers import *  # noqa: F401,F403
