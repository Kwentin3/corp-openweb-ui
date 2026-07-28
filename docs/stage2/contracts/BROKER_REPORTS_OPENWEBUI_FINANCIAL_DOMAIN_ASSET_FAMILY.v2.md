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
the version consumed by the current closed-world model-assets projection.
Family v2 is a separate repository draft and does not repoint that projection.

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

No second builder was introduced. The active
`build_gate2_financial_semantic_model_assets.py` path remains pinned to v1 and
also passes its unchanged `--check`.

## 6. Runtime and model boundary

Family v2 does not:

- install, update or activate an OpenWebUI record;
- change the current V6 Packet, Prompt, Choice or request route;
- expose the catalog to a model;
- change provider adapters, validators or materializers;
- change the Pack or any financial type meaning;
- call a provider;
- mutate stage or production;
- claim frozen benchmark compatibility.

Context V2 may consume this catalog only after its own versioned contract,
local linter/replay proof and separately authorized activation path.

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
```
