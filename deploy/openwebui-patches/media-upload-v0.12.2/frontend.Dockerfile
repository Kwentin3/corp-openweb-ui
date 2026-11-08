# syntax=docker/dockerfile:1
# Context: exact official v0.12.2 checkout after apply_media.py.
# Named context media_overlay: this directory. Pin NODE_IMAGE to a digest.
ARG NODE_IMAGE
FROM ${NODE_IMAGE} AS frontend
ARG BUILD_HASH=6a18585ff4c2e5f6805f682222cfbc46dc669ef8
WORKDIR /app
COPY . .
COPY --from=media_overlay manifest.json verify_frontend.mjs /media-overlay/
RUN node /media-overlay/verify_frontend.mjs /app
# Retain native v0.12.2 scripts; Node CUDA is unused by the exported browser build.
RUN ONNXRUNTIME_NODE_INSTALL_CUDA=skip npm ci --force
ENV APP_BUILD_HASH=${BUILD_HASH}
ENV APP_BUILD_CHANNEL=stable
ARG NODE_OPTIONS=""
ENV NODE_OPTIONS=${NODE_OPTIONS}
RUN node --version && npm --version && npm run build

FROM scratch AS export
COPY --from=frontend /app/build /build
