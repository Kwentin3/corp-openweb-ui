# Broker Reports KT1.5 Repository Debt Closure

Date: `2026-07-31`

Status: `LOCAL_AND_GITHUB_CI_ACCEPTANCE_PASSED_PENDING_REVIEW_AND_MERGE`

Scope: KT1.5 Phase 1 repository debt only. Phase 2 LIVE parity repair was not
started. No live read, mutation, deployment, provider call, customer document,
KT2, Type-First implementation, Semantic Pack change, financial-type change,
product-semantic change, OpenWebUI-core change or production admission occurred.

## 1. Authority and delivery identity

- base `origin/main`: `9a4cc2c9f3dce4b4d4c55bff667d12089e62b614`;
- repository acceptance code head:
  `986286a93aa6e06daa84aa133afefee3869e1ea4`;
- branch: `fix/broker-reports-kt15-repository-debt-closure`;
- Draft PR: [#235](https://github.com/Kwentin3/corp-openweb-ui/pull/235);
- exact-head GitHub Actions run:
  [30612635085](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/30612635085);
- job `broker-reports-ci` / `91098678842`: `SUCCESS`;
- run head: `986286a93aa6e06daa84aa133afefee3869e1ea4`.

The post-merge LIVE authority commit does not exist yet because PR #235 is
Draft and unmerged. Phase 2 must bind only to the future exact commit on
`origin/main` after approval and merge. The branch head is not an authorized
LIVE deployment identity.

## 2. Pre-task context and owners

The implementation was bounded by:

- `docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md`;
- `docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md`;
- `docs/stage2/architecture/BROKER_REPORTS_DOMAIN_MAP.v1.md`;
- `docs/stage2/contracts/BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md`;
- `docs/stage2/architecture/BROKER_REPORTS_GATE2_ROUTE_STATUS.v1.md`;
- `docs/stage2/adr/BROKER_REPORTS_GATE2_SEMANTIC_CONVERGENCE.v1.md`;
- `docs/stage2/architecture/BROKER_REPORTS_OWNER_CONTEXT.v1.json`;
- `docs/stage2/agent/BROKER_REPORTS_PRE_TASK_CONTEXT_PROTOCOL.v1.md`;
- `docs/stage2/agent/BROKER_REPORTS_CODE_COMMENT_POLICY.v1.md`;
- `docs/stage2/contracts/BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE.v1.md`;
- `docs/stage2/operations/BROKER_REPORTS_ATOMIC_STAGE_RELEASE.v1.md`;
- Decision Gate 1 closure evidence and GOAL 18 reconciliation audit.

The existing owners remain unchanged:

- product model client construction:
  `Gate2StructuredModelClientFactory.create`;
- provider projection, extraction and the governed GOAL12 direct transport:
  `Gate2ProviderAdapterFactory.create`;
- OpenWebUI connection and credential resolution:
  `Gate2OpenWebUIProviderConnectionResolver`;
- generated closed-world projection:
  `scripts/build_openwebui_pipe_bundle.py`;
- repository/live parity evidence:
  `repository_factory_boundary_checks`;
- historical GOAL9 proof authority:
  its immutable safe receipt plus the Git tree that introduced it.

## 3. Debt A — final KT1 head CI authority

Diff `6c447f431e6f998dc6e3222824f82afcddf6e6c8..09e3c6903240924f94ef293f9520617a69b79bcb`
contains exactly three Markdown documentation/evidence files:

| File | Classification |
| --- | --- |
| `docs/reports/2026-07-31/BROKER_REPORTS_KT1_ARCHITECTURE_DECISION_BRIEF.md` | documentation |
| `docs/reports/2026-07-31/BROKER_REPORTS_KT1_ARCHITECTURE_STABILIZATION.report.md` | safe report evidence |
| `docs/stage2/architecture/BROKER_REPORTS_PR232_EXTRACTION_LEDGER.v1.md` | architecture documentation |

Contracts, tests, runtime/source and executable metadata changed: `0`.

The later accepted KT1 head
`5125ebae590d5da9014a4cfe3392afc9231961ae` adds only three Decision Gate 1
closure report/brief/receipt files. Real pull-request Actions run
[30608549687](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/30608549687)
completed `SUCCESS` on that exact head, including generated-asset checks,
bundle parity, Ruff correctness, Context V2.1 anti-drift and focused tests.

Result: `FINAL_KT1_HEAD_CI_AUTHORITY=PROVEN`.

## 4. Debt B — GOAL12 process-state contamination

Root cause was not a GOAL12 fixture mutation. Both generated-bundle test
modules deleted every `broker_reports_gate1*` entry from `sys.modules`.
`BrokerReportsGate2PipeBundleTest.tearDown` did so after every test, including
tests that never loaded a bundle. Pytest had already collected later GOAL12
tests against the original module objects. A subsequent lazy import therefore
created a second maintained module graph; monkeypatch targets, exception
classes and call counters could point at different module instances.

The deterministic reproduction was:

```text
Gate2 bundle test
→ unconditional sys.modules purge
→ GOAL12 direct-transport test
→ patched build_opener belongs to old module
→ runtime call uses reimported module
→ expected HTTP boundary calls 1, observed 0
```

Fix:

- `tests/test_broker_reports_gate1_pipe_bundle.py` now snapshots the exact
  maintained module objects before bundle isolation;
- `tests/test_broker_reports_gate2_pipe_bundle.py` does the same;
- bundle loading still clears maintained names before executing the generated
  closed-world package;
- teardown clears only the temporary bundled graph and restores the exact
  original module-object mapping.

No process split, skip, xfail, deselection, retry or test weakening is used as
the fix.

Order evidence:

- bundle suites → GOAL12 suites: `139 passed`;
- GOAL12 suites → bundle suites: `139 passed`;
- fresh-process GOAL12 selection: `126 passed`;
- random-order plugin: not installed, so seed execution was not applicable;
- full repository suite, run 1: `2230 passed, 23 skipped`;
- same checkout/environment after `--cache-clear`, run 2:
  `2230 passed, 23 skipped`.

Result:

```text
ORDER_DEPENDENT_FAILURES=0
FULL_SUITE_SETUP_ERRORS=0
NEW_SKIPS=0
```

## 5. Debt C — historical GOAL9 receipt

The historical receipt remains byte-unchanged. The former test used
`git show :<path>`, which reads the current index and incorrectly treated later
contract evolution as historical-evidence corruption.

`scripts/verify_historical_safe_receipt.py` now:

1. validates the receipt and its `base_revision`;
2. finds the unique receipt add-commit whose parent is that base revision;
3. requires the commit and every historical path to exist;
4. verifies the current receipt itself against its historical Git object using
   repository clean-filter semantics;
5. hashes each deliverable from `<historical_commit>:<path>`;
6. observes current `HEAD` equality separately and never requires it.

For GOAL9 the resolved authority is:

- base: `27ee880c30fd5b90bf82528ecb6400c4dc54de96`;
- historical source commit:
  `c49bba056d777b65baaa9969390e32454f4d0468`;
- historical blobs verified: `4`;
- current-head differences observed without failure: `2`.

`tests/test_verify_historical_safe_receipt.py` proves historical pass, current
evolution pass, corrupted historical hash rejection, missing-commit fail
closed, changed-receipt rejection and no current-main equality requirement.
`test_goal9_safe_receipt_hashes_historical_git_blobs` binds the real receipt.

Result:

```text
HISTORICAL_RECEIPT_REWRITE=0
HISTORICAL_AUTHORITY_VERIFICATION=PASSED
```

## 6. Debt D — provider adapter containment

Verdict: verifier false positive, not an architecture leak.

The old check rejected the literal canonical OpenAI and Google hostnames in
`gate2_provider_adapters.py`. GOAL12's approved qualification-only contract
requires those exact endpoints inside the existing provider adapter owner,
after credentials and enabled connection identity are resolved from OpenWebUI.
Hostname presence inside that owner is therefore not a product bypass.

The real product chain remains:

```text
OpenWebUI Pipe
→ Gate2StructuredModelClientFactory
→ Gate2ProviderAdapterFactory
→ Gate2OpenWebUIProviderConnectionResolver
→ adapter-owned transport
```

`_provider_adapter_boundary_invariants` now parses AST/import/call ownership
and proves:

- one connection-resolver class authority;
- adapter construction only under the model-client factory for product paths;
- no direct network import, network call or provider hostname in product
  Pipe/domain runtime consumers;
- OpenWebUI secret configuration keys are read only in the resolver class;
- qualification modules are not product consumers;
- concrete historical adapters are not product-reachable;
- all three generated bundles contain byte-exact maintained provider-adapter
  and model-client modules and exclude qualification modules.

Positive repository fixtures pass. Negative fixtures inject direct provider
transport, duplicate resolver, secret lookup, qualification import, concrete
adapter reachability and bundle drift; each is rejected.

Result: `provider_adapters_stay_inside_openwebui=true` with all seven detailed
invariants `true`.

## 7. Repository acceptance

| Check | Result |
| --- | --- |
| all CI generated managed-asset builders | passed |
| all three generated Function bundles | byte parity passed |
| Context V2.1 / GOAL16 anti-drift | `338 passed, 3 existing skipped`; second selection `9 passed` |
| expanded architecture/GOAL9/GOAL12/ArtifactStore/AnswerContext/release/verifier acceptance | `261 passed, 1 existing skipped` |
| full suite run 1 | `2230 passed, 23 existing skipped, 0 failed, 0 errors` |
| full suite run 2 after cache cleanup | `2230 passed, 23 existing skipped, 0 failed, 0 errors` |
| privacy/integrity selection | `33 passed` |
| targeted full-rule Ruff on changed files | passed |
| repository CI Ruff profile `E9,F63,F7,F82` | passed |
| compileall | passed |
| `git diff --check` | passed |
| exact code-head GitHub CI | passed |

Unrestricted full-repository Ruff reports `264` pre-existing baseline findings,
mainly legacy re-export `F401` and test `E402` findings outside this corrective
slice. Changed files pass unrestricted Ruff, and the repository's mandatory
CI Ruff profile passes. No baseline lint file was altered or hidden.

## 8. Change accounting and stop

```text
historical receipts rewritten: 0
provider calls: 0
customer documents used: 0
product semantic changes: 0
runtime semantic changes: 0
OpenWebUI core changes: 0
production admission changes: 0
generated bundle byte changes: 0
live reads: 0
live changes: 0
KT2 started: no
Phase 2 started: no
```

Repository debt is locally and CI accepted. Review and merge remain external
acceptance steps. LIVE parity debt remains open and Phase 2 is prohibited until
PR #235 is approved and merged, the exact `origin/main` commit is known, the
canonical tree is clean, and deterministic bundles match that commit.

