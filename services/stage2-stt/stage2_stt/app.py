from __future__ import annotations

from fastapi import FastAPI, HTTPException

from stage2_stt.config import SttConfigError, load_stt_config
from stage2_stt.contracts import TranscriptionRuntimeCapabilitiesV1
from stage2_stt.runtime import build_runtime_capabilities
from stage2_stt.storage import StorageModeError


def create_app() -> FastAPI:
    app = FastAPI(title="OpenWebUI Stage 2 STT Backend", version="0.1.0")

    @app.get(
        "/stage2-api/transcription/capabilities",
        response_model=TranscriptionRuntimeCapabilitiesV1,
    )
    def transcription_capabilities() -> TranscriptionRuntimeCapabilitiesV1:
        try:
            config = load_stt_config()
            return build_runtime_capabilities(config)
        except (SttConfigError, StorageModeError) as exc:
            raise HTTPException(
                status_code=500,
                detail={"code": "stage2_stt_config_invalid", "message": str(exc)},
            ) from exc

    return app


app = create_app()
