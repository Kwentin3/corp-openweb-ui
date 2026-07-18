#!/usr/bin/env python3
"""Run the maintained mixed document-memory proof inside the stage container."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
BUNDLE_PATH = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
)
PROOF_PATH = SCRIPT_DIR / "prove_gate1_document_memory_v1.py"

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import _default_ssh_target, _read_env


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
    bundle = BUNDLE_PATH.read_text(encoding="utf-8")
    bundle_sha = hashlib.sha256(bundle.encode("utf-8")).hexdigest()
    proof = PROOF_PATH.read_text(encoding="utf-8")
    proof = proof.replace("from __future__ import annotations\n\n", "", 1)
    bundle_hash_expression = """hashlib.sha256(
                    GATE1_BUNDLE.read_bytes()
                ).hexdigest()"""
    if bundle_hash_expression not in proof:
        raise RuntimeError("document_memory_proof_bundle_hash_expression_missing")
    proof = proof.replace(bundle_hash_expression, repr(bundle_sha), 1)
    proof = proof.replace(
        "synthetic_mixed_supported_profile_v1",
        "stage_container_synthetic_mixed_supported_profile_v1",
    )
    remote_code = bundle + "\n" + proof

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
        input=remote_code.encode("utf-8"),
        capture_output=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "live_gate1_document_memory_v1_command_failed: "
            + completed.stderr.decode("utf-8", errors="replace").strip()[-2000:]
        )
    output = json.loads(completed.stdout.decode("utf-8", errors="strict"))
    output["stage_execution"] = {
        "container": "openwebui",
        "execution_mode": "ephemeral_synthetic_bundle_proof",
        "repository_bundle_sha256": bundle_sha,
        "customer_documents_used": False,
        "operator_acceptance_performed": False,
        "product_representative_stage_proof": False,
    }
    if output.get("proof_status") != "passed":
        raise RuntimeError("live_gate1_document_memory_v1_proof_failed")
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
