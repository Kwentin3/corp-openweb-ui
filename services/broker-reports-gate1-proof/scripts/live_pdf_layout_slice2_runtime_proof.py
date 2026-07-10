#!/usr/bin/env python3
"""Prove pinned PDF layout imports and bundled execution in live OpenWebUI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions/broker_reports_gate1_pipe_bundled.py"

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import (  # noqa: E402
    _default_ssh_target,
    _read_env,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--ssh-target", default=None)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    ssh_target = (
        args.ssh_target
        or env.get("OPENWEBUI_SSH_TARGET")
        or _default_ssh_target(env)
    )
    runner = r'''
import io
import json
import pdfminer
import pdfplumber
import pypdf
from broker_reports_gate1 import (
    PDFMINER_PINNED_VERSION,
    PDFPLUMBER_PINNED_VERSION,
    PYPDF_PINNED_VERSION,
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)

buffer = io.BytesIO()
writer = pypdf.PdfWriter()
writer.add_blank_page(width=320, height=240)
writer.write(buffer)
parser = PdfTextLayerParserFactory().create(
    PdfParserCapabilityRequest(capability="table_candidates")
)
parsed = parser.parse(buffer.getvalue())
summary = {
    "status": "passed",
    "bundle_version": getattr(__import__("broker_reports_gate1"), "__bundle_version__", ""),
    "versions": {
        "pypdf": pypdf.__version__,
        "pdfplumber": pdfplumber.__version__,
        "pdfminer.six": pdfminer.__version__,
    },
    "pins_match": (
        pypdf.__version__ == PYPDF_PINNED_VERSION
        and pdfplumber.__version__ == PDFPLUMBER_PINNED_VERSION
        and pdfminer.__version__ == PDFMINER_PINNED_VERSION
    ),
    "requested_capability": parsed.requested_capability,
    "layout_status": parsed.layout_projection_status,
    "pages_total": len(parsed.pages),
    "ocr_vlm_used": False,
    "page_rendering_used": False,
    "customer_documents_used": False,
}
if not summary["pins_match"] or summary["pages_total"] != 1:
    raise RuntimeError("live_pdf_layout_runtime_proof_failed")
print(json.dumps(summary, sort_keys=True))
'''
    code = BUNDLE_PATH.read_text(encoding="utf-8") + "\n" + runner
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "StrictHostKeyChecking=no",
            ssh_target,
            "docker",
            "exec",
            "-i",
            "openwebui",
            "python",
            "-",
        ],
        input=code.encode("utf-8"),
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "live_pdf_layout_runtime_command_failed: "
            + completed.stderr.decode("utf-8", errors="replace").strip()[-1000:]
        )
    stdout = completed.stdout.decode("utf-8", errors="strict")
    result = json.loads(stdout.strip().splitlines()[-1])
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
