# Broker Reports OpenWebUI Financial Domain Asset Family v2

Status: `ADDITIVE_DRAFT_NOT_LIVE`

Family ID: `broker_reports_gate2_financial_domain_assets`

Family semantic version: `1.1.0`

Manifest schema:
`broker_reports_financial_domain_managed_asset_manifest_v2`

## 1. Successor boundary

This contract is the additive successor of
[Financial Domain Asset Family v1](./BROKER_REPORTS_OPENWEBUI_FINANCIAL_DOMAIN_ASSET_FAMILY.v1.md).
It remains the same family and uses the same deterministic builder. It is not
a second registry, asset family, packet builder, GUI or release mechanism.

The immutable v1 repository manifest remains byte-exact and continues to be
the default active profile consumed by current callers. Family v2 remains a
repository draft, now packaged only as a separately selected non-active
candidate profile through the same closed-world model-assets loader.

## 2. Exact delta from v1

The v2 manifest retains, without modification:

- the same three managed Skill, Prompt and Workspace Tool entries;
- the same OpenWebUI `v0.9.6` API identities;
- the same Financial Semantic Pack and Pack schema;
- the same consumer schema and decision-contract source;
- the same Prompt placeholder and strict decision output contract;
- the same empty supporting Knowledge set;
- the same bans on RAG, Knowledge, Python and Prompt type-meaning authority.

It adds exactly three dependencies:

1. the versioned Financial Decision Reason Catalog JSON;
2. its Python-generated GUI/validation schema;
3. the build-time Python factory that generates and checks that schema.

Composition links all three to the existing family. Authority remains split:
the decision contract owns codes, the catalog owns human meanings, and the
factory owns catalog structure/checking. Financial type meaning remains in the
unchanged Pack.

## 3. Manifest identity

Repository manifest:
[broker_reports_financial_domain_assets.v2.manifest.json](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v2.manifest.json)

Repository schema:
[broker_reports_financial_domain_assets.v2.manifest.schema.json](../../../services/broker-reports-gate1-proof/managed_assets/broker_reports_financial_domain_assets.v2.manifest.schema.json)

```text
FAMILY_SEMANTIC_VERSION: 1.1.0
AUTHORITY_STATUS: target_normative_not_live
RUNTIME_ACTIVATION: false
ASSETS_TOTAL: 3
DEPENDENCIES_TOTAL: 7
SUPPORTING_KNOWLEDGE_TOTAL: 0

MANIFEST_SHA256:
4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d

MANIFEST_GIT_BLOB_SHA256:
4ef70eba07bea24332a0909e4c9cb68c82854197a11fb2e78f47c3d88cf3d586

MANIFEST_SCHEMA_GIT_BLOB_SHA256:
dde15c7d523141b0301dfe8721b2eb2746d043e19768db14d40206545f4dbfd7
```

All hashes use LF-normalized UTF-8 Git-blob bytes. Manifest semantic integrity
omits only top-level `manifest_sha256`.

## 4. Inactive lifecycle

The manifest lifecycle is:

```text
status: draft
previous family semantic version: 1.0.0
live publisher implemented: false
```

Draft rollback is `discard_without_runtime_mutation`. The exact prior
repository baseline is pinned as:

```text
V1_MANIFEST_SCHEMA_VERSION:
broker_reports_financial_domain_managed_asset_manifest_v1

V1_MANIFEST_SHA256:
b2d1d51f5894012871d9603b59b2a4dd597c9b83ac4d1b7714bf100468728b59

V1_MANIFEST_GIT_BLOB_SHA256:
2399bfdb3734e18814ce6380d70b5a865a5cc9fca2bb3a8e03068ca5ddb8e315
```

Future active rollback is defined as selecting the previous validated
immutable family version. This is a policy definition, not evidence that a
live full-family publisher/readback/rollback path exists. That lifecycle gap
from GOAL 0 remains open.

## 5. Deterministic build

The existing
[`build_openwebui_managed_financial_assets.py`](../../../services/broker-reports-gate1-proof/scripts/build_openwebui_managed_financial_assets.py)
continues to build/check the v1 Tool and v1 manifest byte-exactly. Its additive
v2 path:

1. reads the current decision-contract source;
2. extracts the closed unclassified reason codes through the catalog factory;
3. validates the catalog and its canonical integrity;
4. generates the catalog schema;
5. copies the exact v1 assets/dependencies;
6. appends the three catalog dependencies;
7. renders the v2 manifest and schema deterministically.

No second builder or runtime loader was introduced. The existing
`build_gate2_financial_semantic_model_assets.py` now validates and embeds the
inactive v2 family/reason snapshot used by the historical Context V2.0
completeness projection alongside the unchanged default v1 return profile, and
its single generated module passes `--check`. This is not a managed minimal
projection.

## 6. Runtime and model boundary

Family v2 does not:

- install, update or activate an OpenWebUI record;
- change the current V6 Packet, Prompt, Choice or request route;
- expose the catalog through the active model request route;
- change provider adapters, validators or materializers;
- change the Pack or any financial type meaning;
- call a provider;
- mutate stage or production;
- claim frozen benchmark compatibility.

The non-active
[Context V2.0 contract](./BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.md)
selects this catalog as its sole reason-meaning authority. Its exact packaged
closed-world snapshot and non-active completeness packet projection are
implemented and remain version-pinned historical evidence.

The
[Minimal Model Surface v1](./BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md)
supersedes V2.0 only as the field-eligibility target for future Context V2.1.
GOAL 5 is documentation-only and changes no managed asset, generated module,
loader, packet or runtime bytes. GOAL 6 audits the outcome taxonomy and
count-one stop. GOAL 7 may then implement one versioned minimal Pack/reason
projection through the existing builder, family and closed-world loader; it
must not add a second asset family or projection authority.

The GOAL 5-selected strings already exist: `positive_signal` is exact Pack
`examples[0]`, `negative_signal` is exact `counterexamples[0]`, nearest
distinction is the unique direct rule against the only other current visible
type, and reason `use_when` is the exact first sentence of catalog `meaning`
under the closed sentence rule. GOAL 7 implements only these mappings and may
not author or embed replacement marker/reason wording.

GOAL 8 implemented only one non-active Context V2.1 candidate plus private
receipt through the existing Packet authority. The later explicit program
authorizes GOAL 9 to add the inactive
[Local Choice V2.1](./BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_LOCAL_CHOICE.v2.1.md)
profile through the existing Choice authority. This historical family v2 is
not changed. Linter/sealed request, persistence/replay, provider proof and
activation remain later, separately gated requirements before transport.

## 7. Acceptance

```text
SAME_FAMILY: YES
V1_MANIFEST_AND_ASSETS: BYTE_EXACT
CATALOG_DEPENDENCY: VERSIONED
CATALOG_SCHEMA: PYTHON_GENERATED
CATALOG_VALIDATOR: FACTORY_GUARDED
RUNTIME_ACTIVATION: FALSE
LIVE_PUBLISHER: NOT_IMPLEMENTED
ROLLBACK_BASELINE: EXACT_V1_PIN
SECOND_AUTHORITY: ZERO
PROVIDER_CALLS: ZERO
CONTEXT_V2_0_COMPLETENESS_ASSET_PROFILE: PACKAGED_INACTIVE
CONTEXT_V2_0_PACKET_PROJECTION: IMPLEMENTED_NON_ACTIVE
MINIMAL_MODEL_PROJECTION: NOT_IMPLEMENTED_GOAL_7
CONTEXT_V2_1: NOT_IMPLEMENTED_GOAL_8
CONTEXT_V2_1_RESPONSE_PROFILE: NOT_IMPLEMENTED_SEPARATE_AUTHORIZATION_REQUIRED
CONTEXT_V2_1_LINTER: BLOCKED_BY_RESPONSE_PROFILE_STOP_GOAL_9
ACTIVE_PROFILE_CHANGED: NO
```
