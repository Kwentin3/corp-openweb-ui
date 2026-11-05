FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9

ARG OFFICECLI_VERSION=1.0.152
ARG OFFICECLI_SHA256=e54d3c1d248372365f0634aac56d6f1918bd04d6e71afc792ad50e075f56cfe9

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OFFICECLI_EXPECTED_VERSION=${OFFICECLI_VERSION}
ENV OFFICECLI_BINARY=/usr/local/bin/officecli
ENV OFFICECLI_SKIP_UPDATE=1
ENV OFFICECLI_NO_AUTO_RESIDENT=1
ENV HOME=/tmp

WORKDIR /app

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
    && apt-cache -o APT::Default-Release= policy ca-certificates curl libicu76 chromium fonts-dejavu-core \
    && apt-get -o APT::Default-Release= -o Acquire::Retries=3 install --no-install-recommends -y ca-certificates curl libicu76 chromium fonts-dejavu-core \
    && curl --fail --location --silent --show-error \
      --output /usr/local/bin/officecli \
      "https://github.com/iOfficeAI/OfficeCLI/releases/download/v${OFFICECLI_VERSION}/officecli-linux-x64" \
    && echo "${OFFICECLI_SHA256}  /usr/local/bin/officecli" | sha256sum --check \
    && chmod 0755 /usr/local/bin/officecli \
    && test "$(/usr/local/bin/officecli --version)" = "${OFFICECLI_VERSION}" \
    && /usr/local/bin/officecli load_skill word > /tmp/officecli-word-skill.md \
    && test -s /tmp/officecli-word-skill.md \
    && /usr/local/bin/officecli load_skill excel > /tmp/officecli-excel-skill.md \
    && test -s /tmp/officecli-excel-skill.md \
    && /usr/local/bin/officecli load_skill pptx > /tmp/officecli-pptx-skill.md \
    && test -s /tmp/officecli-pptx-skill.md \
    && /usr/local/bin/officecli help pptx > /tmp/officecli-pptx-help.md \
    && test -s /tmp/officecli-pptx-help.md \
    && rm -rf /var/lib/apt/lists/* /tmp/officecli-word-skill.md /tmp/officecli-excel-skill.md /tmp/officecli-pptx-skill.md /tmp/officecli-pptx-help.md

COPY services/officecli-openapi-proof/pyproject.toml ./pyproject.toml
COPY services/officecli-openapi-proof/requirements.lock ./requirements.lock
COPY services/officecli-openapi-proof/officecli_openapi_proof ./officecli_openapi_proof

RUN python -m pip install --no-cache-dir -r requirements.lock \
    && python -m pip install --no-cache-dir --no-build-isolation --no-deps . \
    && python -m pip check

EXPOSE 8080

CMD ["uvicorn", "officecli_openapi_proof.app:app", "--host", "0.0.0.0", "--port", "8080"]
