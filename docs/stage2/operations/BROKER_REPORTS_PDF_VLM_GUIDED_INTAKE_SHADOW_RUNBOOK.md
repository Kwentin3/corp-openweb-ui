# Broker Reports PDF VLM-Guided Intake Shadow Runbook

Status: operator procedure for a default-disabled research shadow. The current
proof boundary is partial until a one-call development runner, a new unseen
holdout, a passing live canary, and repository/live parity all exist.

## 1. Scope

This runbook covers:

- local contract and regression verification;
- development-only PDF evidence;
- a new source-frozen unseen holdout;
- one synthetic default-disabled live shadow canary;
- exact provider accounting;
- cleanup, rollback, and bundle parity;
- evidence required for the final readiness decision.

It does not authorize production Gate 2 selection, customer-document testing,
OCR, Knowledge/RAG/vector use, an OpenWebUI core patch, or permanent enabling of
the intake shadow.

The controlling contract is
`docs/stage2/contracts/BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE.v1.md`.

## 2. Fixed safety rules

1. The original PDF and parser source references remain exact-value authority.
2. The VLM proposes structure only.
3. Deterministic materialization and validation remain fail-closed.
4. Each intake invocation allows one `countTokens` call, at most one generate
   call, zero retries, and zero provider failover.
5. The page proposal path sends one page and zero source atoms before region
   proposal. The candidate path sends one crop and at most 1,000 bounded atoms
   containing exact parser text, anonymous ids, bbox, and source order.
6. Page-level zero model atoms still requires an exact non-empty text-layer word
   projection. The binder validates its persisted result again against that
   caller-owned projection and the exact crop manifests.
7. Human references stay sealed until all provider work and deterministic
   terminals are complete.
8. All shadow flags are false before and after the live canary.
9. Production Gate 2 selection remains unchanged.
10. Only public development PDFs and a generated synthetic live PDF are allowed
   in this procedure. Do not upload customer documents.

Any failed invariant ends the run. Do not compensate with a retry, a different
provider, a substituted target, a larger budget, or a weakened validator.

## 3. Repository and runtime locations

Repository root:

```text
D:\Users\Roman\Desktop\Проекты\corp-openweb ui
```

Service root:

```text
D:\Users\Roman\Desktop\Проекты\corp-openweb ui\services\broker-reports-gate1-proof
```

Local proof artifacts belong under:

```text
local/stage2/
```

Private crops, provider payloads, atom text, references, and rollback content
stay under a proof directory's `private/` subdirectory. They must not be copied
into documentation or a safe report.

## 4. Current proof boundary

Before starting, distinguish existing evidence from evidence this run must
create:

- the audited public v5 PDFs and all derived labels are development-only;
- the existing `local_pdf_structural_repair_holdout.py` uses two attempts and
  fixed v1-v5 hash policies, so it cannot certify the one-call intake contract;
- the structural live canary has a locally tested candidate-crop one-call mode,
  but it has not passed live on this frozen implementation;
- the persisted 2026-07-15 semantic/structural canary attempt failed during
  evidence collection and rolled back; its postmortem is cleanup evidence, not
  a passed canary or parity result;
- no new unseen intake holdout is present at this boundary.

Do not call the feature ready based on old structural-repair or v5 artifacts.

## 5. Preconditions

The operator confirms all of the following without printing secret values:

- `.env` exists at repository root and contains `OPENWEBUI_HOST`,
  `WEBUI_ADMIN_EMAIL`, and `WEBUI_ADMIN_PASSWORD`;
- the live SSH host identity is already verified in `known_hosts`;
- the OpenWebUI Function `broker_reports_gate1_pipe` is active;
- Workspace Model `test` is active, allows file upload, has file context
  disabled, and has no Knowledge attachment;
- `pdf_vlm_guided_intake_shadow_enabled` is false or absent;
- `pdf_vlm_guided_intake_shadow_page_allowlist` is empty or absent;
- legacy structural and semantic shadow flags are false or absent;
- the intended output directory does not exist;
- the exact provider profile and model are frozen before any provider call;
- there is an approved maximum cost for the bounded run.

Record `git status --short --branch` in the operator notes. A dirty tree does not
invalidate a byte-level source freeze, but unrelated changes must not be
presented as part of this delivery.

When a page route is required, use the canonical allowlist token
`document_ref::page_ref`. A plain `page_ref` is allowed only when it is globally
unique in the current package; an ambiguous plain ref deliberately selects no
page. Never widen an unresolved ref into an all-page scan.

## 6. Phase A — build and repository tests

Run from the service root:

```powershell
Set-Location 'D:\Users\Roman\Desktop\Проекты\corp-openweb ui\services\broker-reports-gate1-proof'

python scripts/build_openwebui_pipe_bundle.py --target gate1
if ($LASTEXITCODE -ne 0) { throw 'Gate 1 bundle build failed' }

python -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw 'Broker Reports service tests failed' }

Get-FileHash -Algorithm SHA256 -LiteralPath `
  'openwebui_actions/broker_reports_gate1_pipe_bundled.py'
```

The build must include the intake contract, proposal, materialization,
validation, and shadow modules through the maintained bundle order. Bundle
tests must prove closed-world imports and a default-false intake valve.

Minimum focused evidence includes:

- independent detection, processability, and holdout-selection outcomes;
- hard-gate failures versus routing metadata;
- candidate-crop and page-level closed proposal schemas;
- one-call, no-retry, no-failover provider behavior;
- exact atom inclusion and exclusion accounting after bbox adjustment;
- no invention, duplication, mutation, or separator crossing;
- ambiguity preserved when more than one hypothesis validates;
- legacy production Gate 2 selection unchanged;
- bundle and live-canary anti-drift tests.

The document-inventory regression is:

```powershell
python -m pytest -q `
  tests/test_broker_reports_pdf_layout_slice2.py `
  -k document_inventory_overflow_preserves_completed_prefix_and_accounts_tail
if ($LASTEXITCODE -ne 0) { throw 'partial-prefix regression failed' }
```

It must retain only fully completed pre-cap pages, keep the unchanged inventory
limit, emit `pdf_layout_document_inventory_budget_exceeded` at document level,
mark every tail page with
`pdf_layout_page_not_processed_document_inventory_budget`, and perform no
provider call.

## 7. Phase B — development regressions

Use the audited v5 corpus only as development evidence. A conforming local
runner must persist safe and private artifacts for these cases:

| Case | Required route and outcome |
|---|---|
| Betterment p4 | Real unusual table reaches candidate-crop VLM proposal and deterministic validation |
| DriveWealth p7 | Broad table candidate is bounded without losing atom accounting |
| DriveWealth p9 | Sparse/empty-column evidence is metadata, not technical rejection |
| DriveWealth p11 | Fragment is processable but is not automatically a holdout target |
| Moomoo annual p9, p11 | Compound candidate is split into bounded table scope |
| Moomoo annual p10 | Page-level proposal may recover a table outside the candidate bbox |
| Moomoo annual p14 | Page-level proposal returns at most two non-overlapping regions |
| Moomoo midyear p6, p7, p8 | Bounded table regions are separated from broad prose |
| Moomoo midyear p10 | Two table regions remain separate |
| Betterment p2 and obvious prose pages | Normally suppressed with zero provider calls |
| Both IBKR PDFs | Completed prefix and exact missing tail are retained after inventory overflow |

For every case record separately:

- detection assessment and reason;
- processability and exact technical reason;
- holdout selection and policy reason;
- entry path;
- original and proposed scope identities;
- all included and excluded atom counts;
- ownership, provenance, and validation terminal;
- count-token and generate calls;
- counted input, actual input, output, image, JSON, and response bytes;
- requested and resolved model;
- retry and failover counts, both zero.

There is no repository command at the current boundary that performs this
one-call matrix. Do not substitute the old two-attempt structural holdout. If a
bounded development runner and its tests are absent, stop with a partial result.

## 8. Phase C — freeze a genuinely unseen holdout

Do this only after Phase A and Phase B are complete and code is frozen.

Before opening document content or invoking a provider, persist a checksummed
manifest containing:

- preregistered acquisition rule and date window;
- official source URL and acquisition timestamp for every PDF;
- byte size and SHA-256;
- proof that every hash is disjoint from all earlier corpora, reports, local
  experiments, references, and provider journals;
- exact source inventory and revision;
- parser, intake, processability, validation, and holdout policy checksums;
- frozen provider profile, model id, image/token/byte limits, and one-call rule;
- selection policy across the whole corpus;
- required ruled, alignment-based, sparse/separator, compound, negative, and
  upstream-failure coverage.

If the corpus cannot supply the preregistered diversity, terminate as
insufficient. Do not replace a PDF or target after freeze.

The legacy `fresh_holdout_v5` command is not valid for this phase. A conforming
one-call holdout runner must enforce this sequence:

```text
prepare and freeze
-> validate immutable preregistration
-> run one bounded provider invocation per routed scope
-> write attempt journal and deterministic terminal seal
-> stop provider access
-> create or unlock human reference
-> independently score the unchanged terminal
```

The scorer must reopen and hash the terminal before and after reference access.
Reference data must never be accepted by the runner, proposal layer,
materializer, or validator.

If the repository lacks this one-call runner and independent scorer, stop. An
ad hoc command or manual spreadsheet is not certifying evidence.

## 9. Phase D — evaluate the unseen holdout

Report the following metric families independently:

1. Detection: real-table recall, false-candidate suppression, zero-call
   negatives, and upstream-absence accounting.
2. Processability: processable and unsupported scopes by exact technical
   reason.
3. Reconstruction: accepted, blocked, ambiguous, exact topology, atom
   ownership, omissions, duplications, inventions, and provenance failures.
4. Holdout selection: selected, not selected, and not evaluated by frozen
   policy reason.
5. Cost: exact count-token and generate calls, tokens, image/JSON/response
   bytes, retries, and failovers.

Do not merge these into one “success rate”. A provider HTTP success is not a
correct table. A safe abstention is not an exact reconstruction. A processable
scope is not a selected holdout target.

Only continue to live shadow if the preregistered acceptance bar passes without
reference leakage, hidden retry, failover, atom invention, or validator
weakening.

## 10. Phase E — one default-disabled live shadow canary

Before running live, the canary tests must prove that it:

- refuses to start when any shadow flag is enabled;
- enables intake only for its synthetic case and exact allowlist;
- observes exactly one count-token call and at most one generate call for each
  routed intake invocation;
- exercises the declared candidate-crop or page-level entry path;
- checks requested and resolved provider/model identity;
- rejects hidden retry or failover;
- records atom, provenance, and validation summaries;
- asserts `production_gate2_selection_changed=false`;
- restores prior Function and valves before slow cleanup;
- rolls back on body, cleanup, parity, or output failure.

Run from the service root:

```powershell
$runId = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$outputDir = "..\..\local\stage2\broker_reports_gate1_vlm_guided_intake_shadow_canary_$runId"

python scripts/build_openwebui_pipe_bundle.py --target gate1
if ($LASTEXITCODE -ne 0) { throw 'Gate 1 bundle build failed' }

python scripts/live_gate1_structural_shadow_canary.py `
  --env-file '..\..\.env' `
  --output-dir $outputDir
if ($LASTEXITCODE -ne 0) { throw 'live intake shadow canary failed' }

python scripts/live_verify_broker_reports_stage2_delivery.py `
  --env-file '..\..\.env'
if ($LASTEXITCODE -ne 0) { throw 'repository/live parity failed' }
```

Do not run this command while the script still expects two provider attempts or
does not verify `pdf_vlm_guided_intake_shadow_enabled=false` on exit. In that
state the command is an incompatible legacy canary and the result is partial.

## 11. Canary cleanup and automatic rollback

Before any live mutation, the canary writes a private backup containing exact
Function content and SHA, metadata/control state, valves and SHA, and Workspace
Model identity and SHA.

The required terminal sequence is:

1. Temporarily deploy the exact generated Gate 1 bundle.
2. Verify its live SHA and required markers.
3. Upload one generated synthetic PDF with `process=false`.
4. Enable only the bounded canary valves and allowlist.
5. Run one non-streaming synthetic chat request.
6. Collect and validate private and safe evidence.
7. Restore the old Function and valves before slow cleanup.
8. Delete the upload by exact id and verify its unique alias is absent.
9. Purge case artifacts and verify payload-free tombstones.
10. Observe bounded 5, 15, and 30 second quiescence checks for late writes.
11. Verify runtime counters, no Knowledge/RAG/vector delta, and exact Workspace
    Model restoration.
12. Only when every check passes, redeploy the new bundle with all original
    valves restored, including the intake flag left false.
13. If any check fails, retain or restore the old Function and exact valves.

The successful safe artifact must show upload absence, no active private
payload, exact provider totals, no retry/failover, no Gate 2 selection change,
and final default-disabled state.

## 12. Interrupted-process recovery boundary

The current canary has automatic rollback in its `finally` path and stores
`private/function.before.private.json`. That does not by itself cover a process
or host killed outside `finally`.

Do not claim complete operator rollback until one of these exists and is tested:

- a bounded recovery command that validates the private backup checksum,
  restores exact Function/control state and valves, and verifies readback; or
- an approved manual procedure with the same checksum and readback guarantees.

Until then, an interrupted-process recovery gap is a specific partial defect.
Do not improvise restoration from copied chat text or an unverified local
bundle.

## 13. Post-canary verification

The delivery verifier must report all of the following as passed:

- live Gate 1 Function SHA equals the repository bundle SHA;
- required intake modules and contract markers are present;
- Function is active;
- `pdf_vlm_guided_intake_shadow_enabled=false`;
- `pdf_vlm_guided_intake_shadow_page_allowlist` is empty;
- legacy structural and semantic flags are false unless a separate approved
  procedure says otherwise;
- required PyMuPDF version matches;
- managed prompts and unaffected Gate 2 bundles retain their expected parity;
- production Gate 2 candidate binding/selection remains unchanged.

Save verifier stdout as safe evidence. Do not call parity passed from a bundle
hash alone when the valve, Function activity, dependency, prompt, or Gate 2
checks fail.

## 14. Evidence inventory

The closeout must identify, by path and SHA where applicable:

- local test result and generated Gate 1 bundle SHA;
- development safe/private manifest and case summaries;
- unseen corpus manifest and disjointness scan;
- holdout preregistration, run claim, provider journal, terminal seal, reference,
  and independent score;
- live `canary.safe.json`;
- private rollback artifact location without exposing its content;
- cleanup and quiescence evidence;
- delivery-verifier output and live bundle SHA.

The final report must not copy source values, atom text, crops, raw provider
responses, credentials, local absolute private paths, or human reference cells.

## 15. Stop conditions

Stop immediately and preserve the typed terminal when:

- source, policy, manifest, or checksum freeze changes;
- a new PDF hash matches prior evidence;
- countTokens is missing, invalid, or over 20,000;
- a second generate attempt, retry, or failover appears;
- requested and resolved model ids differ;
- a page/crop, atom, JSON, output, or response budget is exceeded;
- ownership, separator, span, source identity, or provenance validation fails;
- two valid alternatives remain ambiguous;
- the reference is accessed before terminal seal;
- cleanup, rollback, quiescence, or parity is incomplete;
- any shadow flag remains enabled;
- production Gate 2 selection changes.

## 16. Final decision

Use exactly one final decision:

```text
BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_READY_FOR_SHADOW_E2E
```

Use it only when local regression, fresh unseen holdout, live canary, cleanup,
rollback, and parity all pass on the same frozen implementation.

Otherwise use:

```text
BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_PARTIAL
<specific remaining defect>
```

or:

```text
BROKER_REPORTS_PDF_VLM_GUIDED_INTAKE_NOT_READY
<specific failed evidence>
```

Missing fresh-holdout accuracy, an incompatible two-attempt canary, missing
interrupted-process recovery, or missing repository/live parity are each
sufficient reasons for `PARTIAL`. A validator failure, reference leak, hidden
retry/failover, source mutation, or Gate 2 authority change requires
`NOT_READY`.
