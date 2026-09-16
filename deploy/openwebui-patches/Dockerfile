ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6
FROM ${OPENWEBUI_BASE_IMAGE}

ARG BROKER_REPORTS_SOURCE_REVISION=untracked
LABEL org.opencontainers.image.revision=${BROKER_REPORTS_SOURCE_REVISION}

# Controlled overlays only. Application behaviour remains in native OpenWebUI
# extensions; this image does not patch the Web Speech/STT recorder.
COPY deploy/openwebui-patches/apply_native_broker_pdf_upload_patch.py /usr/local/bin/apply_native_broker_pdf_upload_patch.py
RUN python /usr/local/bin/apply_native_broker_pdf_upload_patch.py --root /app/build/_app/immutable/chunks

# The only STT-specific overlay owns atomic replacement of a source-video
# attachment with the OpenWebUI-managed normalized audio file.
COPY deploy/openwebui-media-lifecycle/stage2_media_lifecycle.py /app/backend/open_webui/services/stage2_media_lifecycle.py
RUN python -m py_compile /app/backend/open_webui/services/stage2_media_lifecycle.py
