ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.11.4@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f
FROM ${OPENWEBUI_BASE_IMAGE}
COPY provider_context_capture.py /app/backend/open_webui/utils/provider_context_capture.py
COPY apply_capture.py verify_capture.py /usr/local/lib/openwebui-provider-capture/
RUN python /usr/local/lib/openwebui-provider-capture/apply_capture.py \
    && python -m unittest discover -s /usr/local/lib/openwebui-provider-capture -p verify_capture.py
LABEL corp.diagnostic="scoped-final-provider-context-0.11.4"
