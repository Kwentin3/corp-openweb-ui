#!/usr/bin/env python3
"""Pin the tested media images and memory bounds in the existing VPS Compose."""

import argparse
from pathlib import Path


WEBUI_IMAGE = "corp-openwebui/openwebui:media-intake-release-20260925"
STT_IMAGE = "corp-openwebui/stage2-stt:media-intake-release-20260925"


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"Expected exactly one production anchor: {old[:80]!r}")
    return source.replace(old, new)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compose", type=Path, required=True)
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    compose = args.compose.read_text(encoding="utf-8")
    env = args.env.read_text(encoding="utf-8")
    compose = replace_once(compose, "    mem_limit: 2g\n    mem_reservation: 1g\n", "    mem_limit: 2g\n    memswap_limit: 4g\n    mem_reservation: 1g\n")
    compose = replace_once(compose, "      WEBUI_SECRET_KEY: ${WEBUI_SECRET_KEY}\n", "      WEBUI_SECRET_KEY: ${WEBUI_SECRET_KEY}\n      STAGE2_STT_INTERNAL_API_KEY: ${STAGE2_STT_INTERNAL_API_KEY:-}\n")
    compose = replace_once(compose, "  stage2-stt:\n    build:\n      context: ..\n      dockerfile: services/stage2-stt/Dockerfile\n    container_name: stage2-stt\n", "  stage2-stt:\n    build:\n      context: ..\n      dockerfile: services/stage2-stt/Dockerfile\n    image: ${STAGE2_STT_IMAGE:-compose-stage2-stt}\n    container_name: stage2-stt\n    mem_limit: 768m\n    memswap_limit: 1g\n")
    env = replace_once(env, "OPENWEBUI_IMAGE=corp-openwebui/openwebui:v0.9.6-native-web-stt-native-pdf-21545c1", f"OPENWEBUI_IMAGE={WEBUI_IMAGE}")
    if "STAGE2_STT_IMAGE=" in env:
        raise RuntimeError("STT image is already pinned in the production env")
    env += f"\nSTAGE2_STT_IMAGE={STT_IMAGE}\n"
    if not args.dry_run:
        args.compose.write_text(compose, encoding="utf-8")
        args.env.write_text(env, encoding="utf-8")
    print("production media Compose anchors valid; write=" + str(not args.dry_run).lower())


if __name__ == "__main__":
    main()
