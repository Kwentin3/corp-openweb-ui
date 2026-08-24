# Issue #306 — live OpenWebUI 3-NDFL goal report

Date: 2026-08-24

Base: `db199ce082a5b40cade538e46f674c83a14b4d43`

Dependency: PR #305 merged unchanged from approved head
`34c459dd53e66ae9edc0baf6feb3838345faf060`

Branch: `agent/issue-306-live-openwebui-goal`

Final generated bundle SHA-256:
`0eb6cad18963dff003e7d0fd92eefbf90537a0717f32b169cbbab9ea2cd6542a`

Live-tested code head: `f9c3a4ce1fa08fb905f0c96f8a2b89217440458b`

Mechanically verified safe receipt:
`c67b11bd69f192abf25fb73e8e74b17887c5db8a4c41be338c887696490326ad`

## Verdict

The supported 2025 resident ordinary-trade profile now completes in an actual
isolated OpenWebUI through rendered browser controls only. Two clean runs with
different temporary users/cases produced the same downloaded XML bytes. The
file passed the existing official-XSD projection owner and the values shown to
the user matched the values independently extracted from the downloaded XML.

This proves preparation and private download, not filing or acceptance by FNS.
No official external FNS importer was available in the test boundary, so no
import/submission claim is made.

## Environment and role separation

- Dedicated OpenWebUI container, database and storage volume.
- Remote service exposed only through remote loopback and an operator SSH
  tunnel to local `127.0.0.1:18080`; no public route and no shared production
  database.
- Maintained generated Function/model: `broker_reports_ndfl`.
- Legacy Function `broker_reports_gate1_pipe` inactive during every proof
  window.
- User mode read only the UI, synthetic truth card and permitted source file.
- Developer mode began only after a user-mode failure was saved. It inspected
  test logs/store and owner artifacts, added a regression, rebuilt and started
  a new user/case.
- Runtime LLM/provider calls for source, identity, tax or authority decisions:
  zero.
- The two proof windows carry different control-owner-issued run ids; each
  browser receipt binds its exact prepared receipt and each cleanup receipt
  binds that prepared predecessor.

## Final clean evidence

| Proof | Run A | Run B |
|---|---:|---:|
| New users and case | yes | yes |
| Invalid-checksum INN rejected | yes | yes |
| Invalid calendar date rejected | yes | yes |
| Deferred fill-only answer | yes | yes |
| DRAFT_READY before XML | yes | yes |
| Accepted date corrected | yes | yes |
| Private browser download | yes | yes |
| Reload/resume | yes | yes |
| Concurrent retry kept one logical link | yes | yes |
| Cross-user file/case denial | yes | yes |
| Final four-part note | yes | yes |
| Downloaded bytes | 1102 | 1102 |
| XML SHA-256 | `655c2d5d…e79c5d5` | `655c2d5d…e79c5d5` |
| Official XSD owner | valid | valid |

Independent extraction from each downloaded XML returned income `100.00`,
accepted expenses `61.00`, tax base `39.00`, calculated tax `5`, and payable
`5`. Those are the same values rendered in the final user note. The two files
were byte-equal.

The final note explicitly distinguishes:

- values extracted from the report;
- values calculated by Tax Model and reconciled with XML;
- facts confirmed by the user;
- fields and completeness the user must check before filing, plus an explicit
  statement that nothing was submitted to FNS.

## Retry, file and cancellation evidence

- Reload returned to the current case without re-reading the source.
- Two simultaneous final `Continue` turns retained the same visible private
  download URL; the existing OpenWebUI Files/Storage owner kept one logical
  file and no orphan was observed.
- User B could not see the NDFL model, could not download the guessed private
  file URL, and could not see user A's chat result.
- Closing a tab on an unanswered Human Fact question did not retain the source
  workload lease: a second independent case reached its question in `5044 ms`
  without answering the first; the proof fails at `30000 ms`.
- Persisted queued callers now hold renewable leases; cancellation is persisted
  and expired orphan waiters recover fail-closed after restart.

## Representative source result

A permitted public representative T-Bank broker-report sample was uploaded by
the same browser file-input path. The current Canonical/source route did not
produce the owner facts required by the supported declaration profile. The UI
therefore stopped before declaration, created no XML/download, and displayed a
plain-language source blocker. No labels, facts or artifacts were injected.
The public source was the four-page sample linked by T-Bank at
`https://cdn.tbank.ru/static/documents/7b9ccdee-5a02-4ed6-9499-c76082cd8d30.pdf`;
the downloaded proof input was `639417` bytes with SHA-256
`25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67`.

This is an honest current MVP source-extraction limit. The synthetic source
proves the supported vertical product route; it is not presented as proof that
arbitrary production broker PDFs are supported.

## Defects found and bounded fixes

1. The NDFL model was layered over the legacy Pipe identity instead of being a
   direct installed execution entrypoint. The existing domain id remains
   unchanged; only the OpenWebUI Function/model stable id is direct.
2. An owner-produced source blocker omitted `user_actions` and the adapter
   raised `KeyError`. The adapter now treats the typed owner blocker as final.
3. Human think time retained a Gate 1 workload lease. Publication finalizes
   before the Human Fact modal is awaited.
4. An abandoned queued caller could persist forever and block FIFO after
   restart. Queue leases are now issued, renewed by a live waiter, cancelled on
   caller cancellation, and recovered typed fail-closed after expiry.
5. The legacy active Function loaded a second memory-heavy bundle. The bounded
   control deactivates it during proof and restores its exact prior state.
6. The supported synthetic fixture lacked a real direct disposal commission
   and correctly stopped at the existing expense owner. A genuine source
   expense was added to the fixture; no owner was bypassed.
7. Standalone chat derived `normalization_run_id` from message text, so owner-
   equal XML could acquire different Scope/Package receipts and file ids. The
   composition boundary now derives execution identity from the current
   source-owner projection set; a source successor changes it, retries do not.
8. The final user answer lacked the required four-part explanation. The
   presentation reads only already owner-reconciled XML values and adds no
   calculation authority.
9. Source safe-report diagnostics leaked internal handoff/run references. The
   direct NDFL presentation now renders a bounded plain-language source result.
10. Workload progress exposed `brjob_*`. Direct NDFL progress now hides job id
    and internal state; the browser proof fails on either diagnostic family.
11. The first concurrent browser oracle compared every historical download
    link rendered by OpenWebUI's virtualized branch DOM. It reported a false
    duplicate although developer evidence showed exactly the expected
    pre-correction and corrected owner receipts/files and no third artifact.
    The proof now binds both concurrent replies and post-reload current state to
    the corrected link explicitly.
12. The final note called `accepted_expenses` an extracted report value even
    though it is a Tax Model result. All five numeric outputs now stay in the
    Tax Model plus independent XML-reconciliation section; the source section
    contains no calculated number.
13. Human questions exposed owner-internal English codes. The Human Adapter now
    maps only the exact current owner `answer_contract.allowed` set to bounded
    Russian labels; raw codes and an unknown future code fail closed.
14. The first committed interaction trace summarized hand-checked booleans. A
    narrow builder now validates two genuine browser receipts, downloaded XML
    bytes through the existing XML owner, current bundle/driver/control bytes,
    cleanup predecessors and the aggregate receipt hash.
15. Retest showed that two different controls could produce byte-equal safe
    receipts. The control owner now issues a random technical `control_run_id`;
    the final proof requires two different ids and two prepared-to-restored
    chains. The earlier A run was discarded and both runs were repeated.
16. Delegated exact-head review at
    `3300bfa17f13633f4b5df3a7cb9e4acac6f68421` found that an entirely unknown
    Human Fact `fact_key` still fell back to raw owner question/allowed values.
    The representation adapter now treats every unrecognized USER_FACT
    presentation as unavailable and returns the typed
    `OWNER_REQUEST_INVALID` result before answer adaptation. An adversarial
    `future_owner_fact` / `RAW_UNKNOWN` regression proves that neither raw
    question nor code is rendered or accepted. The generated bundle was rebuilt
    and both browser runs plus the representative-source run were repeated on
    `f9c3a4ce1fa08fb905f0c96f8a2b89217440458b`.

No new questionnaire engine, owner, registry, Tax Model, Scope/Package/XML
meaning, LLM authority, or artifact mutation path was added.

## Adversarial coverage

- genuine current-source execution identity across two chat transports;
- source successor changes the execution binding;
- concurrent identical XML publication retains one physical/logical file;
- Human Fact wait releases source workload lease first;
- expired queued waiter cannot block FIFO after restart;
- cancelled queue wait persists cancellation;
- live queued waiter renews until admitted;
- direct source blocker and progress do not expose internal identifiers;
- browser driver statically forbids app API bypass;
- raw machine answers and unknown owner codes fail closed;
- an unknown Human Fact request family cannot expose or accept raw owner
  vocabulary;
- committed receipt hashes and current code manifest are revalidated in CI;
- two independent control ids and prepared-to-cleanup chains are required;
- public representative source must block without XML;
- existing Human Fact currentness, correction, conflict and fail-closed rules
  remain covered by their owner suites.

Final active-route command: `236 passed` across production candidate/release,
deterministic consumption, declaration preparation, Human Facts, Tax Model,
Category/declaration assembly, XML projection, declaration MVP, installed
Pipe, workload authority, workspace model, the committed Issue #306 trace and
frozen evidence. The generated bundle rebuilt byte-equal at the SHA recorded
above; JavaScript syntax, Python compilation, lint, JSON parsing and
`git diff --check` passed.

The first final-head Linux CI run correctly rejected a Windows mixed-EOL
working-tree hash that could not be reconstructed from the clean checkout.
The proof now binds browser-driver, control and receipt-builder source to their
exact clean tested Git blobs; the deployed generated bundle remains byte-exact.
Both browser runs are repeated after this proof-boundary correction.

The first run on the newly created replacement staging instance is rejected:
after cold file processing the browser UI never emitted its chat request and
the first question timed out. Its control window was fully restored. The
accepted A2 and B runs started with new users/cases after the instance was warm;
neither contains developer intervention or a retry of the rejected case.

After the first exact-head CI exposed one stale Gate 3 workflow fixture still
using the domain workflow id as its OpenWebUI workspace id, that fixture was
bound to `NDFL_WORKSPACE_MODEL_STABLE_ID`. The exact CI Gate 2 architecture
command then passed locally: `292 passed`.

An earlier broad local suite exposed the existing architecture assertion
`test_projection_decimal_use_is_representation_validation_only`: its expected
function set already differs from the untouched
`gate5_full_target_xml_projection.py` on the merged base. Neither that module
nor the guard test is changed by this branch, so this report does not turn the
broad attempt into a green claim. Required final exact-head CI remains the
publication gate and is reported on the PR/Issue receipt rather than guessed
in this report.

## Self-review answers

1. Yes. Questions and answers use ordinary user language; hidden owner terms
   are now rejected by the browser proof.
2. No. The black-box driver classifies only visible question text and uses the
   supplied truth card; it does not read code/store/artifact fields.
3. Yes. The generated bundle was installed as `broker_reports_ndfl` in an
   actual OpenWebUI and driven through Chromium.
4. Yes. The downloaded 1102-byte files were hashed and passed the official-XSD
   projection owner, rather than relying on a Files row.
5. Closing the tab leaves the unanswered Human Fact request current but frees
   the source workload lease; return can resume, and another case is admitted.
6. Concurrent retry retained one logical link/file. Owner-level race and queue
   recovery regressions cover duplicate and orphan failure modes.
7. No. User B was denied model visibility, guessed file URL and case content.
8. Invalid answers are rejected and not stored; deferred stays fill-only;
   unsupported source stops before XML in plain language.
9. No placeholder was observed in wire XML; official XSD extraction and
   semantic reconciliation passed.
10. No. The representative PDF currently blocks; the synthetic fixture is
    explicitly limited to the supported vertical route.
11. No. Source, Human Facts, Tax Model, Scope/Package/release/XML and Files keep
    their existing owners.
12. Yes. Both final runs used only user-visible UI and no diagnostic rights.
13. Yes. Run B used new users/case with no DB repair or developer intervention.
14. FNS import acceptance, filing, delivery and legal acceptance remain
    unproven; no FNS submission occurred.
15. Yes for the bounded supported preparation goal: a non-architect user can
    upload, answer, correct, inspect, privately download and resume. Broad
    production broker-PDF extraction remains outside that proof.

## Cleanup and residual limits

All temporary users, grants and proof valves were restored by the maintained
control. After preserving this safe report, the exact test-only container and
its sole-consumer volume were removed, and the local SSH tunnel was closed.
Production was not modified.

Residual limits are unchanged: period 2025, resident individual, non-IP,
single ordinary organized-market security sale, outside IIS, RUB, initial
filing, self-signing, no representative and no FNS submission. External FNS
import is the exact unavailable validation boundary.

Safe trace:
`BROKER_REPORTS_ISSUE_306_INTERACTION_TRACE.safe.json`.

Reproduction runbook:
`../../stage2/operations/BROKER_REPORTS_ISSUE_306_LIVE_OPENWEBUI_RUNBOOK.md`.
