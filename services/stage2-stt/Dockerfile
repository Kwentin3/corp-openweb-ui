FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Server-side preparation is the only supported video normalization path.
# Keep ffmpeg in the isolated STT sidecar, never in browser-injected code.
RUN sed -i \
      -e 's|http://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/20261007T000000Z|' \
      -e 's|http://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/20261007T000000Z|' \
      /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get -o Acquire::Check-Valid-Until=false install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY services/stage2-stt/pyproject.toml ./pyproject.toml
COPY services/stage2-stt/requirements.lock ./requirements.lock
COPY services/stage2-stt/stage2_stt ./stage2_stt
COPY services/stage2-stt/openwebui_actions ./openwebui_actions

RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-build-isolation --no-deps . \
    && python -m pip check

EXPOSE 8080

CMD ["uvicorn", "stage2_stt.app:app", "--host", "0.0.0.0", "--port", "8080"]
