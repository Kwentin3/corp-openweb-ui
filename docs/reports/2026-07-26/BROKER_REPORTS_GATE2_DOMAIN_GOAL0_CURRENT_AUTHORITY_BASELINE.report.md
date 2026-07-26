# Broker Reports Gate 2 Managed Financial Domain — Goal 0 Current Authority Baseline

Date: 2026-07-26
Status: `COMPLETED_WITH_EXPLICIT_LIVE_REPOSITORY_DRIFT`
Base revision: `485ab1a9deeda6e9fa644b55e75d2289638df884`
Implementation revision: `9fa25351910d6a2360725686ae235279ff4ab61d`
Branch: `codex/broker-reports-gate2-domain-goal0-current-authority-baseline`
Draft PR: `https://github.com/Kwentin3/corp-openweb-ui/pull/143`

## 1. Goal boundary

This Goal freezes the current repository successor implementation and the
read-only live OpenWebUI state. It does not define the managed domain contract,
create a Semantic Pack, change a model prompt, call a provider, process customer
data, mutate stage, or activate a production route.

The next Goal is not permitted until this Goal is merged and accepted.

## 2. Executive finding

There are two distinct paths and they must not be reported as one:

1. The repository contains a newer successor proof path with deterministic
   scope v2, code-owned typed admission v1, bounded source context v2, model
   input/prompt/provider projection v3, canonical decision v1, deterministic
   materialization, financial context v1, and successor artifact family v2.
2. Live stage still runs the older Registry-driven
   `Gate2FinancialEvidenceProductionRuntime` path. Its domain Function contains
   the production-run-v1 marker and does not contain the successor v2/v3
   markers.

All three live Broker Reports pipe Functions are active but differ from current
repository bundles. Twelve managed Prompts are exact. No managed Skills exist.
The read-only verifier therefore correctly returns `failed` for whole-bundle
repository/live parity.

This is a pinned baseline, not a release defect correction. Production change
in this Goal is zero.

## 3. Repository authority map

### 3.1 Deterministic scope

The current successor scope authority is
`Gate2DeterministicFinancialScopeFromGate1V2Factory`.

- Scope schema:
  `broker_reports_gate2_deterministic_financial_scope_package_v2`
- Batch schema:
  `broker_reports_gate2_deterministic_financial_scope_batch_v2`
- Policy:
  `gate2_deterministic_financial_scope_from_gate1_v2`
- Factory boundary:
  `Gate2DeterministicFinancialScopeFromGate1V2Factory.create`
- Source SHA-256:
  `d9fdf30e21b8ff240568e168b9b865f067753ae8f30adb90fc3cea963ccbd883`

Evidence:
`gate2_deterministic_financial_scopes.py:49-66,541-621`.

### 3.2 Current Registry and initial catalog

- Registry ID: `broker_reports_gate2_financial_evidence_registry`
- Registry version: `broker_reports_gate2_financial_evidence_registry_v1`
- Canonical registry hash:
  `0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8`
- Declarations: 2 active types
  - `cash_balance_snapshot_v1`
  - `printed_financial_metric_v1`
- Initial catalog version:
  `broker_reports_gate2_initial_financial_catalog_v1`

The earlier 12-candidate Fact Registry research remains non-production
research. It is not this runtime Registry and is not promoted by this baseline.

Evidence:
`gate2_financial_evidence_registry.py:10-20,113-153`;
`gate2_financial_evidence_catalog.py:12,64-268`.

### 3.3 Decision contract

- Schema: `broker_reports_gate2_financial_evidence_decision_v1`
- Dispositions:
  - `typed_input`
  - `unclassified_financial_input`
  - `no_financial_input`
  - `unsupported`
- Canonical factory:
  `Gate2FinancialEvidenceDecisionContractFactory`
- Source SHA-256:
  `747d83552f394f4bd56249820e9630adc97a4d2435da60cbd9b2b376685eb5be`

This contract remains frozen and is reused by the successor path.

Evidence: `gate2_financial_evidence_decision.py:17-56,128-160,375-406`.

### 3.4 Bounded visible source context

- Schema:
  `broker_reports_gate2_financial_evidence_source_context_v2`
- Policy:
  `gate2_financial_evidence_bounded_source_context_v2`
- Factory:
  `Gate2FinancialEvidenceSourceContextFactory`
- Source SHA-256:
  `aaa96670992247f3d3d42b9863312d2bb4726078c0db3c2f86db445ad8baf764`

The contract explicitly forbids document/path/provenance/graph/audit and
expected-answer metadata in model-visible context.

Evidence: `gate2_financial_evidence_source_context.py:18-37,48-97`.

### 3.5 Current successor prompt and model input

- Model input:
  `broker_reports_gate2_financial_evidence_successor_model_input_v3`
- Result:
  `broker_reports_gate2_financial_evidence_successor_result_v3`
- Prompt contract:
  `broker_reports_gate2_financial_evidence_successor_prompt_v3`
- Prompt SHA-256:
  `30c823d2c509294d4634eac1a4084da9b95056b260bdd64e41d5a5598937d9ae`
- Provider projection:
  `broker_reports_gate2_financial_evidence_provider_projection_v3`
- Projection policy:
  `gate2_financial_evidence_unclassified_first_projection_v3`

The current v3 prompt is generic over eligible Registry guidance. The older v2
prompt contains explicit cash/printed-total instructions and is retained only
as historical compatibility evidence.

Evidence:
`gate2_financial_evidence_successor.py:42-63,152-220`;
`gate2_financial_evidence_successor_projection.py:14-27`.

### 3.6 Validator, materializer, and context

- Financial inputs:
  `broker_reports_financial_evidence_inputs_v1`
- Source package:
  `broker_reports_financial_evidence_source_package_v1`
- Validated decision:
  `broker_reports_financial_evidence_validated_decision_v1`
- Materialization policy:
  `broker_reports_financial_evidence_materialization_v1`
- Financial context:
  `broker_reports_gate2_financial_context_v1`
- Context policy:
  `broker_reports_gate2_financial_context_projection_v1`

Source SHA-256:

- decision:
  `747d83552f394f4bd56249820e9630adc97a4d2435da60cbd9b2b376685eb5be`
- materializer:
  `543633b6e133d761f669450402647af80703ab000a3ba5e5132a0888be8eb434`
- materialization contracts:
  `c0b771b376f2b90332d7d0efd2f1912c89ec715b447c79e1b5176913f80f6748`
- context projection:
  `9516f9b3d1dc7171cc85346c79aba46e999a4f33c8b76efb35b808d8df78b7a3`

The materializer itself is Registry/profile driven. A related downstream
type-specific branch remains in the context projection/validator:
`printed_financial_metric_v1` is mapped to `source_printed`; all other typed
records map to `not_aggregate`. This is not typed admission, but it is pinned
for later Goal 6 review.

Evidence:
`gate2_financial_evidence_materialization_contracts.py:15-37`;
`gate2_financial_context.py:278-306`;
`gate2_financial_context_validation.py:244-266`.

### 3.7 Artifact families and compatibility

Current successor proof family:

- package: `broker_reports_gate2_successor_package_artifact_v2`
- run: `broker_reports_gate2_successor_run_artifact_v2`
- receipt: `broker_reports_gate2_successor_execution_receipt_v2`
- policy: `gate2_successor_artifact_family_v2`
- production write admitted: false
- private source context stored: false
- silent legacy upcast: false

Current active production financial family:

- `broker_reports_financial_evidence_inputs_v1`
- `broker_reports_gate2_financial_context_v1`
- `broker_reports_gate2_financial_evidence_production_run_v1`
- `broker_reports_gate2_financial_evidence_production_receipt_v1`

Compatibility remains dual-read and forbids automatic legacy aliases or silent
legacy rewrites.

Evidence:
`gate2_successor_artifacts_v2.py:53-73`;
`gate2_financial_evidence_compatibility.py:37-57,119-133`;
`gate2_financial_evidence_production_runtime.py:52-80`.

## 4. Full inventory of type-specific Python semantic admission debt

The current successor target path contains two hardcoded type-specific
admission predicates. They are migration debt, not frozen target authorities.

### 4.1 Cash predicate

- Hardcoded type ID: `cash_balance_snapshot_v1`
- Regex categories:
  - English `cash`
  - Russian forms for money/funds
  - Russian forms for cash balance
- Predicate: `_cash_signal`
- Reads:
  `literal_value`, `column_meaning`, `visible_label`
- Admission branch requires:
  one amount, one date, one currency, exactly one cash signal, and one shared
  association group.
- Failure reason:
  `cash_positive_discriminator_not_proven`

### 4.2 Printed-total predicate

- Hardcoded type ID: `printed_financial_metric_v1`
- Regex categories:
  `total`, `subtotal`, `summary`, and Russian total/subtotal forms
- Hardcoded row roles:
  `summary`, `summary_row`, `subtotal`, `subtotal_row`, `total`, `total_row`
- Predicate: `_printed_signal`
- Reads:
  `row_role`, `literal_value`, `column_meaning`, `visible_label`
- Admission branch requires:
  one amount, one date, one currency, a printed signal, and one shared
  association group.
- Failure reason:
  `printed_positive_discriminator_not_proven`

### 4.3 Conflict behavior

If both predicates admit a candidate, all typed branches are removed and the
reason `conflicting_positive_discriminators` is recorded. With no admitted
candidate, the reason is `no_safe_typed_admission`.

Inventory totals:

- hardcoded financial type IDs in admission: 2
- financial-language regexes: 2
- type-specific predicate functions: 2
- hardcoded semantic row-role sets: 1
- type-specific admission branches: 2
- post-response typed-to-unclassified repair branches: 0

Evidence:
`gate2_financial_evidence_typed_admission.py:25-60,153-220,245-314,475-505`.

## 5. Model qualification receipts

### 5.1 Current successor v2 workload

Frozen benchmark:

- benchmark: `gate2_financial_successor_v2`
- cases: 12
- canonical benchmark hash:
  `430bea21d0a36e993bc50184d971f36dfc75a1d2be12bcf5e43fba7436797d66`
- local contract/product proof: passed
- provider calls in local proof: 0

Exact model outcomes:

- `gpt-5.4-nano-2026-03-17`: terminal failed, 10/12 cases passed,
  no unsafe typed input, no literal loss, not qualified.
- `claude-haiku-4-5-20251001`: terminal failed, 6/12 cases passed,
  four provider schema rejections, incomplete product proof, not qualified.

Therefore no model is qualified for the current successor v2 workload.

### 5.2 Older production workload policy

The current repository workload policy is version `1.4.0`, hash
`3d3531d060dacf189c9c82701b5d0a71e93d102cbce8c64aa7093677071373de`.
Its `gate2_financial_evidence` production admission list is empty.

Older synthetic qualification for the predecessor decision workload must not be
transferred to the successor v2 workload.

## 6. Frozen full-scope baseline

The predecessor shadow baseline is preserved as the required future comparison
target:

- selected source refs: 455
- accounted source refs: 455
- uncovered source refs: 0
- duplicate interpretations: 0
- ownership conflicts: 0
- unclassified candidate values: 147
- unclassified bound values: 147
- unclassified value retention: 100%
- fallback: 0
- hidden repair: 0

Authority boundary: this is a frozen predecessor product baseline from
`BROKER_REPORTS_GATE2_GOAL7_FULL_SCOPE_SHADOW_QUALIFICATION`. It is not current
successor-v2 actual-corpus qualification and is not production admission.

## 7. Live OpenWebUI readback

Observed read-only at `2026-07-26T10:11:21+03:00`.

### 7.1 Functions

| Function | Active | Live SHA-256 | Repository SHA-256 | Exact |
|---|---:|---|---|---:|
| `broker_reports_gate1_pipe` | yes | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` | `19406e0300f821328d6625877e5d0c393803231472a7a6b92a294223ed1012b2` | no |
| `broker_reports_gate2_source_fact_pipe` | yes | `d3ba38ed554d87e01a97d7dceaffee71eaa02c88375706477d819f4ccc83d503` | `507bf34b4467de5d500055853c36d544a8e0b278b55c294eadaf44d92f6a6bb2` | no |
| `broker_reports_gate2_domain_source_fact_pipe` | yes | `4f5424f269e88f6e18064565afa70e11e7380033a1b6c9affc349f760a3bb0d5` | `05c56b1599910b33dfe17473727a7ea6f950a61b8bb73438a57469175a4da621` | no |

The live domain Function contains the production-run-v1 marker. It does not
contain deterministic scope v2, typed admission v1, bounded source context v2,
successor model input/prompt v3, or successor artifact family v2 markers.

The qualification Action is active and exact to repository text:

- ID: `broker_reports_gate2_economy_qualification_action`
- live/repository normalized-text SHA-256:
  `f178b142403e52897d2caf74ad75576162331efa85b0da85d472d8301ad24932`
- metadata source revision:
  `cb5817584ab1307fc30e8b8b4292301e62bb8289`

### 7.2 Managed Prompts

Twelve of twelve expected managed Prompts are present, active, version exact,
metadata exact, and content-hash exact:

- document passport and Gate 1 clarification: 2
- source-fact prompt: 1
- legacy domain extractor prompts: 9

There is no managed successor Semantic Pack prompt in this set. The current
successor v3 prompt is code-owned only.

### 7.3 Managed Skills

The live OpenWebUI `skill` table contains zero rows. There is no managed
Financial Domain Skill and no Skill identity to pin beyond `absent`.

### 7.4 Domain valves

- `candidate_binding_enabled`: false
- `financial_evidence_enabled`: true
- `financial_evidence_registry_version`:
  `broker_reports_gate2_financial_evidence_registry_v1`
- `financial_evidence_maximum_scopes`: 64
- `max_repair_attempts`: 1
- `gate3_context_manifest_enabled`: false
- `answer_context_selection_enabled`: true

The repair valve belongs to the older domain runtime. The successor proof and
qualification receipts report repair 0.

### 7.5 Live verification verdict

- managed Prompts exact: yes, 12/12
- required Function markers present: yes
- repository factory boundary: passed
- all Function bundles exact: no, 0/3
- whole read-only verifier status: failed
- stage mutations: 0
- provider calls: 0
- customer calls: 0
- tokens: 0
- cost: USD 0

## 8. Receipt freshness rules

Stale receipts used as current authority: 0.

Explicit non-current evidence:

1. The predecessor 455/455 full-scope receipt is used only as a frozen product
   baseline.
2. The earlier successor-v1 exact-model qualification is superseded by
   successor-v2 benchmark and terminal model receipts.
3. Old production migration receipts are not used for current repository/live
   parity; live Functions, Prompts, Skills, and valves were refreshed read-only.

## 9. Verification

- Focused repository tests: 153 passed in 5.00 seconds.
- Full repository suite:
  1522 passed, 20 skipped, 5 warnings in 110.84 seconds.
- Read-only stage verifier:
  expected failure due to 0/3 Function bundle parity; all other reported
  managed-prompt, provider-profile, operational, and factory-boundary checks
  passed.
- Provider calls: 0
- Customer calls: 0
- Stage mutations: 0
- Production changes: 0

## 10. Acceptance

`AUTHORITIES: PINNED`

`TYPE_SPECIFIC_PYTHON_SEMANTICS: FULLY_INVENTORIED`

`STALE_RECEIPTS: ZERO_USED_AS_CURRENT`

`PRODUCTION_CHANGE: ZERO`

`REPOSITORY_LIVE_PARITY: FALSE_AND_EXPLICIT`

`NEXT_PERMITTED_GOAL: GOAL_1_AFTER_MERGE_AND_ACCEPTANCE`
