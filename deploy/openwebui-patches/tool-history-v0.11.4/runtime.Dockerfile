# CI uses pinned upstream. Production must pass its preserved media image as base.
ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.11.4@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f
FROM ${OPENWEBUI_BASE_IMAGE}
COPY apply_upstream.py verify_history.py apply_transport.py verify_transport.py /usr/local/lib/openwebui-tool-history/
RUN python /usr/local/lib/openwebui-tool-history/apply_upstream.py \
    && python /usr/local/lib/openwebui-tool-history/apply_transport.py \
    && python -m unittest discover -s /usr/local/lib/openwebui-tool-history -p verify_history.py \
    && python -m unittest discover -s /usr/local/lib/openwebui-tool-history -p verify_transport.py
LABEL corp.upstream.tool-history="e88e1f8119fa88110beca57ffa7f0578d97ce699"
