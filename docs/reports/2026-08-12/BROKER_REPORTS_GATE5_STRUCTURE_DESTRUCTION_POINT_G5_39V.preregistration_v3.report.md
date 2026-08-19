# G5.39V blind-probe preregistration v3

Status: `FROZEN_BEFORE_PROVIDER_SUBMISSION`
Date: `2026-08-12`

V2 produced seven terminal pre-inference contract failures,
`gate2_model_request_invalid`, with exactly `0` provider submissions. The v2
slot IDs are permanently retired. Inspection found one setup defect: the
current Gemini Gate 3 adapter requires the response schema's existing
`$defs.roleBinding.properties.target_alias` seam. The v2 research schema used
an equivalent `ref` field outside that seam.

V3 changes only the response field name and adapter-required schema location:

```text
role
target_alias = exact visible structural ref or alias
literal = exact visible literal
```

No representation, source, fact, reviewed region, prompt authority, model,
oracle or adjudication rule changed. This is a new seven-slot version, not a
resubmission. The exact local factory -> builder -> Gemini projection seam was
executed successfully for all seven complete prepared requests before this
freeze, without transport.

## Frozen v3 identities

- Trace SHA-256:
  `18407e17a19b50568950bc93c21dc0be5fc7b7ed8172218355854910c86f5766`.
- Probe code SHA-256:
  `0b93f35482dd24e413446c8a9ef75765dcf9e8a1b50c38c7c039fbca966e7e29`.
- Probe plan SHA-256:
  `18210b0bdfda72c38a090c620b1d2a15b8dd47227b1aaf5dde58e055645b8516`.
- Neutral task SHA-256:
  `5f2453f9a1e29f5bae32714119d6880a174800e7138c13a82dc7538f7e7f3854`.
- Closed response schema SHA-256:
  `becc04df42e58a95269d6b2082babd2975cbe1eab363b7204dd3f7d010400fa1`.
- Route: `Gate2StructuredModelClientFactory.create.label_gate3_once`.
- Profile/model: `google_gemini` / `models/gemini-3.5-flash`.
- Calls: at most `7`; retry `0`; repair `0`; best-of-N `false`; merge `false`.
- Temperature parameter: absent, as required by the exact sealed Gate 3 route.

The seven representation hashes and sizes are byte-identical to v2. New slot
IDs carry the `_v3` suffix. Each is claimed once before its only possible
submission. Private readable requests and responses remain ignored under
`local/`.
