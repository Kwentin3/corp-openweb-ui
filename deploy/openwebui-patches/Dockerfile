ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6
FROM ${OPENWEBUI_BASE_IMAGE}

ARG BROKER_REPORTS_SOURCE_REVISION=untracked
LABEL org.opencontainers.image.revision=${BROKER_REPORTS_SOURCE_REVISION}

# Controlled overlays only. Application behaviour remains in native OpenWebUI
# extensions; this image does not patch the Web Speech/STT recorder.
COPY deploy/openwebui-patches/apply_native_broker_pdf_upload_patch.py /usr/local/bin/apply_native_broker_pdf_upload_patch.py
RUN python /usr/local/bin/apply_native_broker_pdf_upload_patch.py --root /app/build/_app/immutable/chunks
COPY deploy/openwebui-patches/apply_stage2_streaming_upload_patch.py /usr/local/bin/apply_stage2_streaming_upload_patch.py
RUN python /usr/local/bin/apply_stage2_streaming_upload_patch.py

# OpenWebUI owns the derived audio File and atomic chat attachment replacement.
COPY deploy/openwebui-media-lifecycle/stage2_media_lifecycle.py /app/backend/open_webui/services/stage2_media_lifecycle.py
RUN python -m py_compile /app/backend/open_webui/services/stage2_media_lifecycle.py
