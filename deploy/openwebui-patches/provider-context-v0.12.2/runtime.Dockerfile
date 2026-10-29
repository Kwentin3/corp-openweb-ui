# Build on the exact accepted immutable runtime, outside production.
ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.12.2@sha256:10e6a78ba2d172493460a9e8a92c496aaa7a64dc4d26d622a2e95e0c736081c9
FROM ${OPENWEBUI_BASE_IMAGE}
COPY provider_context_capture.py /app/backend/open_webui/utils/provider_context_capture.py
COPY capture_control.py /app/backend/open_webui/utils/provider_capture_control.py
COPY apply_capture.py verify_capture.py /usr/local/lib/openwebui-provider-capture/
RUN python /usr/local/lib/openwebui-provider-capture/apply_capture.py --check \
    && python /usr/local/lib/openwebui-provider-capture/apply_capture.py \
    && python -m unittest discover -s /usr/local/lib/openwebui-provider-capture -p verify_capture.py -v
LABEL corp.diagnostic="scoped-final-provider-context-0.12.2"
