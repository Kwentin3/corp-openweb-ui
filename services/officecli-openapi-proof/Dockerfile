FROM python:3.11-slim

ARG OFFICECLI_VERSION=1.0.148
ARG OFFICECLI_SHA256=e424210bce9355f498eeaf692b4d2b13f1f3422e1db34636c41f54c36025249b

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OFFICECLI_EXPECTED_VERSION=${OFFICECLI_VERSION}
ENV OFFICECLI_BINARY=/usr/local/bin/officecli
ENV OFFICECLI_SKIP_UPDATE=1
ENV OFFICECLI_NO_AUTO_RESIDENT=1
ENV HOME=/tmp

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl \
    && curl --fail --location --silent --show-error \
      --output /usr/local/bin/officecli \
      "https://github.com/iOfficeAI/OfficeCLI/releases/download/v${OFFICECLI_VERSION}/officecli-linux-x64" \
    && echo "${OFFICECLI_SHA256}  /usr/local/bin/officecli" | sha256sum --check \
    && chmod 0755 /usr/local/bin/officecli \
    && test "$(/usr/local/bin/officecli --version)" = "${OFFICECLI_VERSION}" \
    && /usr/local/bin/officecli load_skill word > /tmp/officecli-word-skill.md \
    && test -s /tmp/officecli-word-skill.md \
    && rm -rf /var/lib/apt/lists/* /tmp/officecli-word-skill.md

COPY services/officecli-openapi-proof/pyproject.toml ./pyproject.toml
COPY services/officecli-openapi-proof/officecli_openapi_proof ./officecli_openapi_proof

RUN python -m pip install --no-cache-dir .

EXPOSE 8080

CMD ["uvicorn", "officecli_openapi_proof.app:app", "--host", "0.0.0.0", "--port", "8080"]
