ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6
FROM ${OPENWEBUI_BASE_IMAGE}

COPY deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py /usr/local/bin/apply_native_web_stt_patch.py
RUN python /usr/local/bin/apply_native_web_stt_patch.py --root /app/build/_app/immutable/chunks

COPY deploy/openwebui-broker-reports-intake/broker_reports_intake_contract.py /app/backend/open_webui/routers/broker_reports_intake_contract.py
COPY deploy/openwebui-broker-reports-intake/broker_reports_intake.py /app/backend/open_webui/routers/broker_reports_intake.py
COPY deploy/openwebui-broker-reports-intake/apply_broker_reports_intake_patch.py /usr/local/bin/apply_broker_reports_intake_patch.py
RUN python /usr/local/bin/apply_broker_reports_intake_patch.py --backend-root /app/backend/open_webui \
    && python -m py_compile \
        /app/backend/open_webui/routers/broker_reports_intake_contract.py \
        /app/backend/open_webui/routers/broker_reports_intake.py \
        /app/backend/open_webui/main.py \
        /app/backend/open_webui/routers/retrieval.py
