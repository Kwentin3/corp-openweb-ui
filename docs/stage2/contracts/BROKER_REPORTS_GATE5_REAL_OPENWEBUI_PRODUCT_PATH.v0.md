# Broker Reports Gate 5 Real OpenWebUI Product Path v0

Status: `HISTORICAL CONTROLLED-STAGING PROOF`

Proof status: `PROVEN_IN_CONTROLLED_STAGING`

Activation status: `INACTIVE_AFTER_PROOF`

Current product authority: `NONE`. This synthetic supplied-case adapter is
absent from the current Pipe bundle and is not a fallback. The current route is
owned by `BROKER_REPORTS_PIPELINE_GATES.v1.md` and continues from Gate 4 through
`Gate5DeclarationPreparationRuntimeFactory.create`.

Machine terminal:

```text
REAL_PRODUCT_PATH_XML_VALID
blockers = 0
```

This contract owns only the G5.36 product-integration boundary. It does not
change Gate 1–5 tax, completeness, declaration-package, semantic-input,
projection or official-XSD authorities.

## One product route

The only admitted flow is:

```text
authenticated OpenWebUI user
→ native file upload
→ broker-reports-ndfl Workspace Model
→ broker_reports_gate1_pipe
→ Gate 1 persistence / Gate 2 canonical reader
→ Gate 3 configured provider and validation
→ Gate 4 Financial Case
→ existing Gate 5 owners
→ unchanged G5.34 PROJECT
→ private OpenWebUI XML file
→ native authenticated download
```

There is no G5.36 HTTP endpoint, parser, provider client, Tax Model, target
mapping or XML serializer outside this route.

## Product adapter owner

`Gate5OpenWebUIProductRuntimeFactory.create` is the sole G5.36 adapter owner.
It may:

- parse the explicit `3-НДФЛ факты:` response marker;
- persist private, case-bound fact submissions;
- compose product input from uploaded bytes, trusted application context and
  explicit supplied-case facts;
- delegate only to
  `Gate5EndToEndFullTargetXmlRuntime.continue_from_validated_gate3`;
- persist the exact XML bytes and delivery receipt;
- ask OpenWebUI `Storage` and `Files` owners to publish a native private file.

It must not load
`gate5_end_to_end_supplied_case.proof.v0.json`, call a provider directly,
read SQL, build target mappings, serialize XML manually or infer tax/legal
facts.

## Authenticated case authority

Client-provided `chat_id`, `case_id`, user ID and model ID are not lifecycle
authority.

OpenWebUI-injected metadata is accepted directly. If the native completion
boundary omits `chat_id`, the Pipe may recover it from the request only after
`Chats.get_chat_by_id_and_user_id` confirms that the authenticated user owns
the chat. The stored chat must bind the stable `broker-reports-ndfl` model
before the chat becomes the natural bounded case.

The same owner-bound native Chat lookup is used to recover a structured human
answer when the completion form does not expose the current message text.

## Human residual continuation

The first pass uses only uploaded source data and trusted application context.
No G5.35 supplied-case resource is bundled or loaded.

Missing supplied-case sections or fields are returned by the existing
machine blocker. Every accepted answer is an immutable private artifact of
type:

```text
broker_reports_gate5_openwebui_case_fact_submission_v0
```

On a later human-residual turn, the Pipe resolves the one validated Gate 3
sidecar through `ArtifactResolver` for the same authenticated user, case,
workspace and normalization run. It does not repersist the sealed Gate 1 run
and does not call Gate 3 again. The continuation enters the unchanged Gate
4→5 composition owner.

An exact repeated fact/XML artifact may be reused only when its artifact ID,
type, scope and complete payload are equal. Any semantic difference remains a
fail-closed conflict; overwrite is forbidden.

The authenticated user identity is already trusted context. For
`signer_capacity=taxpayer_self`, `signer_ref` is therefore bound from that
context instead of asking the user to guess an internal ID. Filing facts such
as `declaration_date` are never defaulted.

## Persistence and delivery

The successful route creates private, validated records:

```text
broker_reports_gate5_openwebui_case_fact_submission_v0
broker_reports_gate5_openwebui_xml_artifact_v0
broker_reports_gate5_openwebui_xml_delivery_receipt_v0
```

The XML record contains the exact XML bytes, semantic-input hash, Projection
Definition binding, official-XSD conformance receipt and upstream Gate 5
receipt. OpenWebUI file publication must preserve the XML hash. The user-facing
link is the native owner-checked route:

```text
/api/v1/files/{id}/content?attachment=true
```

## Required negative behavior

- missing source financial value: machine blocker, no XML artifact;
- missing mandatory filing fact: bounded acquisition, no default and no XML;
- malformed/conflicting human facts: fail closed;
- missing or ambiguous validated Gate 3 sidecar: fail closed;
- wrong user: source, chat and XML access denied by native OpenWebUI ACL;
- XSD failure or byte/hash mismatch: no terminal success.

## Live-provider proof

At least one fresh product case must use the configured
`google_gemini / models/gemini-3.5-flash` transport through
`Gate2StructuredModelClientFactory.create`. A private external audit may retain
the raw synthetic provider response, but the repository-safe report may expose
only aggregate counts, hashes and validation status.

## Determinism

Two product turns with the same parsed semantic fact patch but different
transport whitespace must create byte-identical downloaded XML. The second
turn may reuse exact private semantic artifacts, but it must still traverse
the native chat and download boundaries.

## Activation boundary

The proof may temporarily grant the stable model to one synthetic User A and
make its existing base Function callable in controlled staging. The grant,
Function-global flag, proof valve, audit valve and temporary users must be
restored or removed after the run.

Final required state:

```text
ndfl_full_product_enabled = false
ndfl_gate3_private_audit_enabled = false
broker_reports_gate1_pipe.is_global = false
broker-reports-ndfl = private
temporary G5.36 users = 0
```

## Anti-drift and scope stop

G5.36 admits no second pipeline, hidden case fixture, direct provider path,
Gate-owner bypass, UI tax logic, manual XML, ACL relaxation, Knowledge/RAG,
PDF, FNS submission, real-taxpayer pilot or production-wide activation.

After `REAL_PRODUCT_PATH_XML_VALID`, stop. A later goal requires separate
authorization.
