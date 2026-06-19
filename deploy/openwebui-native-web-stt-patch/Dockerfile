ARG OPENWEBUI_BASE_IMAGE=ghcr.io/open-webui/open-webui:v0.9.6
FROM ${OPENWEBUI_BASE_IMAGE}

COPY deploy/openwebui-native-web-stt-patch/apply_native_web_stt_patch.py /usr/local/bin/apply_native_web_stt_patch.py
RUN python /usr/local/bin/apply_native_web_stt_patch.py --root /app/build/_app/immutable/chunks
