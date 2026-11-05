FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Server-side preparation is the only supported video normalization path.
# Keep ffmpeg in the isolated STT sidecar, never in browser-injected code.
RUN sed -i \
      -e 's|http://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/20261007T000000Z https://snapshot-cloudflare.debian.org/archive/debian-security/20261007T000000Z|' \
      -e 's|http://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/20261007T000000Z https://snapshot-cloudflare.debian.org/archive/debian/20261007T000000Z|' \
      -e '/^Signed-By:/a Check-Valid-Until: no' \
      /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' '' 'Types: deb' 'URIs: https://deb.debian.org/debian' 'Suites: trixie trixie-updates' 'Components: main' 'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' 'Check-Valid-Until: yes' \
      '' 'Types: deb' 'URIs: https://deb.debian.org/debian-security' 'Suites: trixie-security' 'Components: main' 'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' 'Check-Valid-Until: yes' >> /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' 'Package: *' 'Pin: origin "deb.debian.org"' 'Pin-Priority: -1' > /etc/apt/preferences.d/99snapshot-archive-only.pref \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get -o APT::Default-Release= -o Acquire::Retries=3 --error-on=any update \
    && apt-cache -o APT::Default-Release= policy \
    && apt-cache -o APT::Default-Release= policy ffmpeg \
    && apt-get -o APT::Default-Release= -o Acquire::Retries=3 install --no-install-recommends -y ffmpeg \
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
