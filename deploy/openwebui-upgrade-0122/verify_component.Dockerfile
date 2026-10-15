# Backend component source/runtime check, not a production image or UI acceptance.
FROM ghcr.io/open-webui/open-webui:v0.12.2@sha256:10e6a78ba2d172493460a9e8a92c496aaa7a64dc4d26d622a2e95e0c736081c9
COPY deploy/openwebui-patches/tool-context-v0.12.2/apply_context.py \
     deploy/openwebui-patches/tool-context-v0.12.2/verify_context.py \
     /component-check/tool-context/
COPY deploy/openwebui-patches/media-upload-v0.12.2/apply_media.py \
     deploy/openwebui-patches/media-upload-v0.12.2/manifest.json \
     deploy/openwebui-patches/media-upload-v0.12.2/verify_backend.py \
     /component-check/media-upload/
RUN python /component-check/tool-context/apply_context.py --check \
    && python /component-check/tool-context/apply_context.py \
    && python /component-check/tool-context/verify_context.py -v \
    && python /component-check/media-upload/apply_media.py /app --backend-only --check \
    && python /component-check/media-upload/apply_media.py /app --backend-only \
    && python /component-check/media-upload/verify_backend.py /app
