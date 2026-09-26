ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6
FROM ${OPENWEBUI_BASE_IMAGE}

ARG BROKER_REPORTS_SOURCE_REVISION=untracked
LABEL org.opencontainers.image.revision=${BROKER_REPORTS_SOURCE_REVISION}

# Controlled overlays only. Application behaviour remains in native OpenWebUI
# extensions; this image does not patch the Web Speech/STT recorder.
COPY deploy/openwebui-patches/apply_native_broker_pdf_upload_patch.py /usr/local/bin/apply_native_broker_pdf_upload_patch.py
RUN python /usr/local/bin/apply_native_broker_pdf_upload_patch.py --root /app/build/_app/immutable/chunks
COPY deploy/openwebui-patches/apply_stage2_video_composer_patch.py /usr/local/bin/apply_stage2_video_composer_patch.py
RUN python /usr/local/bin/apply_stage2_video_composer_patch.py
COPY deploy/openwebui-patches/apply_stage2_streaming_upload_patch.py /usr/local/bin/apply_stage2_streaming_upload_patch.py
RUN python /usr/local/bin/apply_stage2_streaming_upload_patch.py

# OpenWebUI owns the derived audio File and atomic chat attachment replacement.
COPY deploy/openwebui-media-lifecycle/stage2_media_lifecycle.py /app/backend/open_webui/services/stage2_media_lifecycle.py
COPY deploy/openwebui-media-lifecycle/stage2_video_intake.py /app/backend/open_webui/services/stage2_video_intake.py
RUN python -m py_compile /app/backend/open_webui/services/stage2_media_lifecycle.py /app/backend/open_webui/services/stage2_video_intake.py

# Google's compatible endpoint omits stream indices and requires opaque tool
# signatures. Keep the native loop/state owner and reject unknown source bytes.
COPY deploy/openwebui-patches/google_openai_tool_compat.py /app/backend/open_webui/utils/google_openai_tool_compat.py
COPY deploy/openwebui-patches/apply_google_openai_tool_protocol_patch.py /usr/local/bin/apply_google_openai_tool_protocol_patch.py
RUN python /usr/local/bin/apply_google_openai_tool_protocol_patch.py
COPY deploy/openwebui-patches/verify_google_openai_tool_protocol.py /usr/local/bin/verify_google_openai_tool_protocol.py
RUN python /usr/local/bin/verify_google_openai_tool_protocol.py
