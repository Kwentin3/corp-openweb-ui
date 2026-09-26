#!/usr/bin/env python3
"""Install only the media release sources into the existing VPS checkout."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


FILES = (
    "deploy/openwebui-patches/Dockerfile",
    "deploy/openwebui-patches/apply_native_broker_pdf_upload_patch.py",
    "deploy/openwebui-patches/apply_stage2_streaming_upload_patch.py",
    "deploy/openwebui-patches/apply_stage2_video_composer_patch.py",
    "deploy/openwebui-patches/google_openai_tool_compat.py",
    "deploy/openwebui-patches/apply_google_openai_tool_protocol_patch.py",
    "deploy/openwebui-patches/verify_google_openai_tool_protocol.py",
    "deploy/openwebui-media-lifecycle/stage2_media_lifecycle.py",
    "deploy/openwebui-media-lifecycle/stage2_video_intake.py",
    "deploy/openwebui-media-lifecycle/audit_legacy_media.py",
    "deploy/openwebui-media-lifecycle/backfill_legacy_media.py",
    "deploy/openwebui-media-lifecycle/activate_audio_filter.py",
    "deploy/openwebui-media-lifecycle/patch_production_compose.py",
    "deploy/openwebui-media-lifecycle/verify_media_backup.py",
    "deploy/openwebui-media-lifecycle/verify_legacy_media.py",
    "deploy/openwebui-media-lifecycle/smoke_video_intake.py",
    "deploy/openwebui-media-lifecycle/smoke_production_video.py",
    "deploy/openwebui-media-lifecycle/stub_chat_provider.py",
    "services/stage2-stt/stage2_stt/app.py",
    "services/stage2-stt/stage2_stt/lemonfox.py",
    "services/stage2-stt/stage2_stt/media_preparation.py",
    "services/stage2-stt/stage2_stt/provider.py",
    "services/stage2-stt/openwebui_filters/stage2_audio_context_filter.py",
    "services/stage2-stt/openwebui_actions/stage2_media_transcription_action.py",
)


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"Expected one source anchor: {old[:80]!r}")
    return text.replace(old, new)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    staged = [(args.candidate / name, args.production / name, args.backup / name)
              for name in FILES]
    for source, _, _ in staged:
        if not source.is_file():
            raise RuntimeError(f"Missing release source: {source}")
    compose = args.production / "compose/openwebui.compose.yml"
    env = args.production / ".env"
    ignore = args.production / ".dockerignore"
    compose_new = replace_once(compose.read_text(encoding="utf-8"),
                               "dockerfile: deploy/openwebui-native-web-stt-patch/Dockerfile",
                               "dockerfile: deploy/openwebui-patches/Dockerfile")
    env_new = replace_once(env.read_text(encoding="utf-8"),
                           "OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6",
                           "OPENWEBUI_BASE_IMAGE=corp-openwebui/openwebui:v0.9.6-native-web-stt-native-pdf-21545c1")
    ignore_new = ignore.read_text(encoding="utf-8")
    if "!deploy/openwebui-patches/**" not in ignore_new:
        ignore_new += "\n!deploy/openwebui-patches/\n!deploy/openwebui-patches/**\n"
    if args.dry_run:
        print(json.dumps({"source_files": len(staged), "production_anchors": "valid"}))
        return
    for source, target, backup in staged:
        if target.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise RuntimeError(f"Source copy differs: {target}")
    for target, content in ((compose, compose_new), (env, env_new), (ignore, ignore_new)):
        backup = args.backup / target.relative_to(args.production)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
        target.write_text(content, encoding="utf-8")
    print(json.dumps({"source_files": len(staged), "compose_source": "media-release", "base_image": "pinned"}))


if __name__ == "__main__":
    main()
