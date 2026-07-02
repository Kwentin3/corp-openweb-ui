from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage2_stt.config import SttConfig, load_stt_config
from stage2_stt.output_profiles import available_output_profile_ids


BROWSER_CONFIG_VERSION = "stage2-stt-browser-normalization-v1"


def build_browser_normalization_config(config: SttConfig) -> dict[str, object]:
    base_url = config.ffmpeg_core_base_url.rstrip("/")
    return {
        "version": BROWSER_CONFIG_VERSION,
        "generated_from_env": True,
        "input_accept_mode": config.input_accept_mode.value,
        "declared_input_mime_prefixes": list(config.declared_input_mime_prefixes),
        "declared_input_extensions": list(config.declared_input_extensions),
        "ffmpeg_probe_required": config.ffmpeg_probe_before_action,
        "require_audio_stream": config.require_audio_stream,
        "selected_output_profile": config.output_profile.value,
        "fallback_output_profile": config.fallback_output_profile.value,
        "available_output_profiles": available_output_profile_ids(),
        "max_browser_input_mb": config.browser_max_input_mb,
        "max_browser_duration_minutes": config.browser_max_duration_minutes,
        "max_prepared_audio_mb": config.max_prepared_audio_mb,
        "ffmpeg_asset_mode": config.ffmpeg_asset_mode,
        "ffmpeg_package_version": config.ffmpeg_package_version,
        "ffmpeg_core_version": config.ffmpeg_core_version,
        "ffmpeg_util_version": config.ffmpeg_util_version,
        "ffmpeg_core_base_url": base_url,
        "ffmpeg_script_url": f"{base_url}/ffmpeg.js",
        "ffmpeg_util_script_url": f"{base_url}/ffmpeg-util.js",
    }


def render_browser_normalization_config(path: Path) -> None:
    config = build_browser_normalization_config(load_stt_config())
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config, ensure_ascii=False, indent=2)
    path.write_text(f"{text}\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_path")
    args = parser.parse_args()
    render_browser_normalization_config(Path(args.output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
