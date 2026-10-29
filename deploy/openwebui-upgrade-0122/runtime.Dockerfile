ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.12.2@sha256:10e6a78ba2d172493460a9e8a92c496aaa7a64dc4d26d622a2e95e0c736081c9
FROM ${OPENWEBUI_BASE_IMAGE}
ARG BUILD_HASH
ENV WEBUI_BUILD_HASH=${BUILD_HASH}
ENV WEBUI_BUILD_CHANNEL=unknown
RUN python -c "import os,re; assert re.fullmatch('[0-9a-f]{64}', os.environ['WEBUI_BUILD_HASH'])"
COPY tool-context/ /usr/local/lib/openwebui-tool-context/
COPY media-upload/ /usr/local/lib/openwebui-media-upload/
RUN python /usr/local/lib/openwebui-tool-context/apply_context.py --check \
    && python /usr/local/lib/openwebui-tool-context/apply_context.py \
    && python /usr/local/lib/openwebui-tool-context/verify_context.py -v \
    && python /usr/local/lib/openwebui-media-upload/apply_media.py /app --backend-only --check \
    && python /usr/local/lib/openwebui-media-upload/apply_media.py /app --backend-only \
    && python /usr/local/lib/openwebui-media-upload/verify_backend.py /app
COPY provider-context/ /usr/local/lib/openwebui-provider-capture/
COPY provider-context/provider_context_capture.py provider-context/capture_control.py /app/backend/open_webui/utils/
RUN python /usr/local/lib/openwebui-provider-capture/apply_capture.py --check \
    && python /usr/local/lib/openwebui-provider-capture/apply_capture.py \
    && python /usr/local/lib/openwebui-provider-capture/verify_capture.py -v
RUN python -c "import pathlib,shutil; p=pathlib.Path('/app/build'); assert p.is_dir(); shutil.rmtree(p)"
COPY build/ /app/build/
COPY frontend-receipt.json /usr/local/lib/openwebui-media-upload/frontend-receipt.json
COPY frontend-files.json /usr/local/lib/openwebui-media-upload/frontend-files.json
COPY verify_frontend_artifact.py /usr/local/lib/openwebui-media-upload/verify_frontend_artifact.py
RUN python /usr/local/lib/openwebui-media-upload/verify_frontend_artifact.py
LABEL corp.upstream.version="0.12.2" \
      corp.upstream.commit="6a18585ff4c2e5f6805f682222cfbc46dc669ef8" \
      corp.overlay="native-media-responses-context-and-provider-capture" \
      corp.provider_context_capture="available-default-off" \
      corp.frontend.build="${BUILD_HASH}"
