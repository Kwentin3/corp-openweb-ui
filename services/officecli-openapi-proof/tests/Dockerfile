ARG OFFICECLI_IMAGE=officecli-candidate
FROM ${OFFICECLI_IMAGE}
RUN python -m pip install --no-cache-dir '/app[test]'
COPY services/officecli-openapi-proof/tests /tests
CMD ["python", "/tests/verify_capability_discovery.py"]
