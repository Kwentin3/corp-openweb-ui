#!/usr/bin/env python3
"""Switch only the stage OpenWebUI service to a proven private-intake image."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
IMAGE_RE = re.compile(r"^corp-openwebui/openwebui:[A-Za-z0-9_.-]+$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")

sys.path.insert(0, str(SCRIPT_DIR))

from live_no_rag_source_intake_smoke import (  # noqa: E402
    _default_ssh_target,
    _read_env,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--image", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not IMAGE_RE.fullmatch(args.image):
        raise RuntimeError("delivery_image_name_invalid")
    if not REVISION_RE.fullmatch(args.source_revision):
        raise RuntimeError("delivery_source_revision_invalid")

    env = _read_env(Path(args.env_file))
    ssh_target = args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    result = _remote_delivery(
        ssh_target=ssh_target,
        image=args.image,
        source_revision=args.source_revision,
        apply=args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _remote_delivery(
    *, ssh_target: str, image: str, source_revision: str, apply: bool
) -> dict[str, Any]:
    remote_code = r'''
import json
import os
import re
import subprocess
import tempfile
import time

IMAGE = __IMAGE__
SOURCE_REVISION = __SOURCE_REVISION__
APPLY = __APPLY__
ROOT = "/opt/openwebui-prd0"
ENV_PATH = ROOT + "/.env"
COMPOSE_PATH = ROOT + "/compose/openwebui.compose.yml"


def run(args, *, env=None, check=True):
    return subprocess.run(
        args,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        env=env,
    )


def inspect_image(target):
    data = json.loads(run(["docker", "image", "inspect", target]).stdout)[0]
    return {
        "id": data["Id"],
        "revision": (data.get("Config", {}).get("Labels") or {}).get(
            "org.opencontainers.image.revision"
        ),
        "intake": (data.get("Config", {}).get("Labels") or {}).get(
            "ai.alpha-soft.broker-reports-private-intake"
        ),
    }


def inspect_running():
    data = json.loads(run(["docker", "inspect", "openwebui"]).stdout)[0]
    return {
        "image_id": data["Image"],
        "configured_image": data.get("Config", {}).get("Image"),
        "running": bool(data.get("State", {}).get("Running")),
    }


def wait_healthy():
    deadline = time.time() + 120
    last = "not_started"
    while time.time() < deadline:
        running = inspect_running()
        if running["running"]:
            health_probe = run(
                [
                    "docker",
                    "exec",
                    "openwebui",
                    "python",
                    "-c",
                    (
                        "import urllib.request; "
                        "r=urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=5); "
                        "assert r.status==200"
                    ),
                ],
                check=False,
            )
            api_probe_code = """\
import urllib.error
import urllib.request
request = urllib.request.Request(
    'http://127.0.0.1:8080/api/v1/auths/signin',
    data=b'{}',
    headers={'Content-Type': 'application/json'},
    method='POST',
)
try:
    urllib.request.urlopen(request, timeout=5)
except urllib.error.HTTPError as error:
    assert error.code in {400, 401, 422}
"""
            api_probe = run(
                [
                    "docker",
                    "exec",
                    "openwebui",
                    "python",
                    "-c",
                    api_probe_code,
                ],
                check=False,
            )
            if health_probe.returncode == 0 and api_probe.returncode == 0:
                return
            last = "application_routes_not_ready"
        else:
            last = "container_not_running"
        time.sleep(2)
    raise RuntimeError("openwebui_health_timeout:" + last)


def compose_up(target):
    process_env = dict(os.environ)
    process_env["OPENWEBUI_IMAGE"] = target
    run(
        [
            "docker",
            "compose",
            "--env-file",
            ENV_PATH,
            "-f",
            COMPOSE_PATH,
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "openwebui",
        ],
        env=process_env,
    )


def configured_image(text):
    values = re.findall(r"(?m)^OPENWEBUI_IMAGE=(.*)$", text)
    return values[-1].strip().strip('"').strip("'") if values else None


def persist_image(original, target):
    replacement = "OPENWEBUI_IMAGE=" + target
    if re.search(r"(?m)^OPENWEBUI_IMAGE=.*$", original):
        updated = re.sub(r"(?m)^OPENWEBUI_IMAGE=.*$", replacement, original)
    else:
        separator = "" if original.endswith("\n") else "\n"
        updated = original + separator + replacement + "\n"
    directory = os.path.dirname(ENV_PATH)
    fd, temp_path = tempfile.mkstemp(prefix=".env.broker-intake.", dir=directory)
    try:
        mode = os.stat(ENV_PATH).st_mode
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, ENV_PATH)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


with open(ENV_PATH, "r", encoding="utf-8") as handle:
    original_env = handle.read()
before = inspect_running()
desired = inspect_image(IMAGE)
if desired["revision"] != SOURCE_REVISION:
    raise RuntimeError("delivery_image_revision_mismatch")
if desired["intake"] != "server-authoritative-v2":
    raise RuntimeError("delivery_image_contract_label_mismatch")
rollback_image = configured_image(original_env) or before["configured_image"]
if not rollback_image:
    raise RuntimeError("delivery_rollback_image_missing")

receipt = {
    "status": "validated" if not APPLY else "passed",
    "applied": APPLY,
    "source_revision": SOURCE_REVISION,
    "desired_image": IMAGE,
    "desired_image_id": desired["id"],
    "previous_configured_image": before["configured_image"],
    "previous_image_id": before["image_id"],
    "rollback_image": rollback_image,
}
if APPLY:
    try:
        compose_up(IMAGE)
        wait_healthy()
        after = inspect_running()
        if after["configured_image"] != IMAGE or after["image_id"] != desired["id"]:
            raise RuntimeError("delivery_running_image_mismatch")
        persist_image(original_env, IMAGE)
        receipt["running_image_id"] = after["image_id"]
        receipt["health"] = "passed"
        receipt["environment_persisted"] = True
    except Exception:
        compose_up(rollback_image)
        wait_healthy()
        raise
print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
'''
    replacements = {
        "__IMAGE__": json.dumps(image),
        "__SOURCE_REVISION__": json.dumps(source_revision),
        "__APPLY__": "True" if apply else "False",
    }
    for needle, replacement in replacements.items():
        remote_code = remote_code.replace(needle, replacement)
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=10",
            ssh_target,
            "python3",
            "-",
        ],
        cwd=ROOT,
        input=remote_code,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=360,
    )
    data = json.loads(completed.stdout)
    if not isinstance(data, dict):
        raise RuntimeError("delivery_receipt_invalid")
    return data


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:200],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
