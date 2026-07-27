# Broker Reports Gate 2 Financial Semantic V6 Execution Identity

Status: Goal 8 contract for Candidate Records By Construction.

## Boundary

`Gate2FinancialSemanticV6ExecutionIdentityFactory.create` is the only boundary
that admits captured provider execution metadata into the V6 qualification
harness.

The boundary validates independent identities for:

- the exact provider profile and its computed route revision;
- adapter, transport and structured-output mode;
- the full response-format envelope and the canonical schema inside it;
- the V6 qualification request profile;
- requested and provider-resolved model IDs;
- latency, token accounting and cost metadata.

The adapter-owned `canonical_request_schema_hash` is compared with the
canonical semantic-choice schema hash. The separately captured
`response_format_hash` is compared with the full response-format envelope
hash. These two identities must not be conflated.

## Normalization

Provider execution metadata is normalized into one deterministic V6 identity.
Optional cached-input and reasoning-token counts normalize to zero. Required
token totals, latency and cost remain exact and must be non-negative.

The safe summary exposes only aggregate accounting and a hash of the provider
response ID. Provider calls are forbidden in the dry proof.

## Failure classes

The harness keeps these terminal defect classes distinct:

- `provider_metadata_defect`;
- `schema_defect`;
- `model_decision_defect`;
- `validator_defect`;
- `materializer_defect`.

Any real profile, route, transport, model, usage or cost mismatch fails closed.
Any response-format or canonical-schema mismatch fails closed as a schema
defect. There is no repair, fallback or identity inference.
