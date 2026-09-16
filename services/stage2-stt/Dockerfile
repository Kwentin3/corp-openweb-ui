FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Server-side preparation is the only supported video normalization path.
# Keep ffmpeg in the isolated STT sidecar, never in browser-injected code.
RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY services/stage2-stt/pyproject.toml ./pyproject.toml
COPY services/stage2-stt/stage2_stt ./stage2_stt
COPY services/stage2-stt/openwebui_actions ./openwebui_actions

RUN python -m pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "stage2_stt.app:app", "--host", "0.0.0.0", "--port", "8080"]
