# Broker Reports Gate 5 Full-target XML Projection v0

Status: `INACTIVE_PROOF_ONLY`
Terminal: `FULL_TARGET_XML_VALID`
Owner: `Gate5FullTargetXmlProjectionRuntimeFactory.create`
Date: `2026-08-11`

## Boundary

The runtime accepts exactly one sealed
`broker_reports_gate5_declaration_semantic_input_v0` value and resolves exactly
one hash-pinned full-target Projection Definition. It emits a complete XML tree
for the bounded supplied synthetic case, serializes that tree without adding
meaning, validates the serialized bytes against the pinned official XSD, and
returns a receipt that binds the XML to its semantic and definition sources.

The runtime does not read Gate 4, SQL, ArtifactStore, documents, provider output,
an LLM, user input, or the network at case time. It does not calculate tax,
decide applicability, compose prior XML fragments, emit PDF, file a declaration,
or activate a product path.

## Exact authorities

The one trusted Projection Definition is:

```text
resource   gate5_full_target_xml_projection.ru_3ndfl_2025.v0.json
id         ru_3ndfl_2025_full_target_supplied_case
version    2026-08-11.0-proof
sha256     48109cc6b3de6fd4d242346648660d99b40863310e622ab2cec44dc641ec7b26
status     trusted_hash_bound_inactive_proof
```

The official target is the 3-NDFL electronic format for tax period 2025,
approved by FNS Order No. ED-7-11/913@ of 20 October 2025:

```text
KND                  1151020
format version       5.20
XSD                  NO_NDFL3_1_033_00_05_20_01.xsd
XSD sha256           083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484
procedure sha256     7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc
format DOCX sha256   f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2
Schematron           not published with this target; null
```

The official XSD bytes are stored closed-world as an ASCII base64 package
resource. The factory decodes them and verifies the decoded byte hash before it
constructs the validator.

## Definition-driven execution

The Projection Definition owns:

- the complete target tree and element order;
- all source paths and repeat paths;
- target attributes and text nodes;
- constants, enum maps and representation transforms;
- target encoding;
- the exact supplied-case domain-state profile;
- all 25 obligation outcomes and their target paths;
- official evidence references.

Python owns only generic operations: strict resource validation, path lookup,
tree construction, representation transforms, serialization, XSD invocation,
hashing and fail-closed receipt assembly. Target codes, target element names,
tax classifications and format-specific constants do not live in Python.

The tree is constructed before serialization. The serializer receives an XML
tree and an encoding from the trusted Definition; it performs no lookup,
calculation, mapping, defaulting or applicability decision.

## Supplied-case completeness

The runtime checks the Definition against the exact domain-state profile of the
sealed semantic input. It accounts for all 25 Definition obligations:

```text
projected activated obligations       8
terminal non-projected obligations   17
unaccounted obligations               0
mapping ids                          49
mapping occurrences                  49
```

An optional target structure is omitted only when its semantic obligation has
the exact terminal state declared by the Projection Definition. A resolved
obligation must have a non-empty target-path binding.

## Upstream completeness correction

The first full-target pass found values already required by the trusted Full
Declaration Definition but lost by the G5.31/G5.33 component/view boundary. The
local loop restored them and replayed package assembly and semantic-input
compilation. It did not change the Full Declaration Definition.

Restored meanings are: declaration date and tax-authority code; taxpayer legal
identity and declarant category; source-party identity and source OKTMO; budget
KBK and OKTMO; the simplified-procedure returned-or-credited amount; non-taxable
income and tax deductions; and per-obligation domestic/foreign source states.

## Fail-closed outcomes

The loop rejects at least:

- a changed or unavailable Projection Definition resource;
- a changed or unavailable XSD resource;
- an invalid or foreign semantic-input contract;
- a changed supplied-case domain profile;
- an unaccounted or state-mismatched obligation;
- a missing source value;
- an enum value absent from the Definition;
- a non-integral semantic amount for an integral target field;
- malformed XML or serialized XML rejected by the official XSD.

There is no retry, best-of-N, manual XML repair, placeholder fallback or
expected-value injection in the projection loop.

## Terminal receipt

Success is possible only with empty blockers and both independent proofs passed:

```text
semantic mapping proof   passed
XSD conformance proof    passed
terminal                 FULL_TARGET_XML_VALID
```

The final receipt binds:

```text
xml_sha256
  -> projection_definition_sha256
  -> semantic_input_sha256
  -> definition_sha256
  -> package_sha256
```

The safe evidence receipt is
`docs/reports/2026-08-11/BROKER_REPORTS_GATE5_FULL_TARGET_XML_PROJECTION_G5_34.receipt.safe.json`.
It contains hashes and aggregate counts only; raw XML and synthetic identity
values remain outside the report.

## Stop

This contract closes G5.34 only. It does not authorize PDF projection, filing,
submission transport, product activation, push, PR, or a dependent Gate goal.
