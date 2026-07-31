# Broker Reports PR #232 Extraction Ledger v1

Status: accepted extraction scope; PR closure pending green KT1 acceptance

PR: `https://github.com/Kwentin3/corp-openweb-ui/pull/232`

Base: `9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`

Head: `d6954f401ae4734fc1573c7560c981cf084c278c`

Disposition: `CLOSE_AFTER_EXTRACTION`

Future branch rule: start from then-current `main`; do not merge, rebase, or
retarget PR #232 into the product route.

## Preserved commit references

| Commit | Historical purpose |
| --- | --- |
| `003e1d2e73857455eaf0672b4bc976c24670ae23` | inactive contract |
| `7846c918b2a27b2df16272e9ed9b4f36b21c6283` | inactive implementation |
| `a5b29c9c7d50f942c04d75fc7a41d3274e552884` | zero-call proof |
| `e15a7650a793cbcc698e8a64794834c7c87ad7bc` | closed-world seal correction |
| `d6954f401ae4734fc1573c7560c981cf084c278c` | cross-platform authority-hash correction |

These references preserve historical evidence. They are not current runtime
admissions.

## Extraction ledger

| PR #232 element | Preserve | Future target owner | Do not transfer | Reason |
| --- | ---: | --- | ---: | --- |
| Rich Pack-backed type cards | Yes | `Gate2FinancialSemanticContractFactory` plus existing packet/projection owner | No | Keeps managed type meaning and explicit evidence under the current Pack authority. |
| Plural `plausible_types` | Yes | Existing source-fact product boundary and V6 Choice contract | No | Makes false-singleton uncertainty visible without creating a route. |
| Opaque local type keys | Yes | Existing packet mapping receipt and Choice owner | No | Prevents model-visible global authority identifiers. |
| Type-First response schema | Yes | `Gate2FinancialSemanticV6ChoiceContractFactory` | No | Reuse only the bounded plural response idea and forbidden-field rules. |
| Parser behavior | Yes | Existing Choice owner | No | Preserve strict shape, duplicate rejection, byte budget, and fail-closed parsing. |
| Code-owned reason table | Yes | `Gate2FinancialSemanticV6DecisionExpansionFactory` | No | The model must not author canonical reason policy. |
| Deterministic prebound options | Yes | Existing packet/projection and candidate compiler owners | No | Options remain complete, code-owned, and source-bound. |
| Exact restoration | Yes | Existing Choice owner plus packet-owned private mapping receipt | No | Local keys must restore exactly before canonical validation. |
| False-singleton comparator | Yes | Existing evidence/replay authority and future inactive acceptance tests | No | Preserves the principal safety signal that motivated convergence. |
| Replay | Yes | `Gate2FinancialSemanticV6DecisionEvidenceFactory` | No | Reuse exact serialize/restore/replay instead of creating another framework. |
| One-call economy accounting | Yes | Existing economy budget/session owner | No | Retain one-call/no-retry/no-fallback accounting as an acceptance invariant. |
| Request sealing requirements | Yes | Existing Context Linter and Request Builder owners | No | Reuse exact sealed-request integrity; do not admit transport. |
| Synthetic source projection | Evidence only | None; future input is the existing validated Gate 2 package | Yes | Synthetic fixtures prove mechanics but cannot become product source authority. |
| Type-First packet candidate method | Design evidence only | Existing packet/projection owner if a future contract authorizes an additive method | Yes | Do not copy the PR implementation wholesale or create a second packet path. |
| Type-First Choice profile | Contract/test idea only | Existing Choice owner | Yes | Future work must rebuild against current `main` and one source-fact boundary. |
| Type-First Context Linter method | Contract/test idea only | Existing Context Linter owner | Yes | No separate product request or transport route is accepted. |
| Type-First Expansion profile | Reason-table idea only | Existing Expansion owner | Yes | Preserve deterministic outcome rules, not a parallel orchestration profile. |
| Coordinator / zero-call chain | Tests and accounting only | No future product coordinator; compose through the existing product boundary | Yes | A second coordinator would become a second semantic route. |
| Generated Function bundles | No | Existing deterministic bundle builder after authorized maintained-source changes | Yes | PR #232 bundles contain the rejected parallel implementation and are not transferable. |
| Valve/admission assumptions | No | Explicit future product decision only | Yes | KT1 and PR #232 authorize no valves, admissions, activation, or live rollout. |

## Required no-transfer boundary

The following must not be carried into a future product route:

- synthetic source projection as product input;
- separate product runtime, Pipe, or coordinator;
- new valves or production admissions;
- duplicate request, materializer, or replay authority;
- parallel V6 product orchestration;
- PR #232 generated bundles;
- any claim that zero-call proof equals qualification or activation.

## Closure record

```text
approved_architecture = OPTION_A
approved_reuse_scope = contract_and_test_ideas_only
pr_232_disposition = CLOSE_AFTER_EXTRACTION
pr_232_final_state = PENDING_GREEN_KT1_ACCEPTANCE
branch_retention = RETAIN_FOR_HISTORICAL_REFERENCE
kt2_authorized = false
```

PR #232 must be closed without merge only after this ledger is committed, KT1
architecture and byte/hash parity tests are green, and the closing comment
preserves the architecture decision and historical references.
