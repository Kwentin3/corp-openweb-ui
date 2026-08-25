# Broker Reports Issue 306: live OpenWebUI runbook

Status: bounded test/staging proof for the supported 2025 ordinary-trade profile.

This runbook records only the live path used for Issue #306. It does not
authorize production deployment, FNS submission, a public route, or use of
real taxpayer data.

## Preconditions

- Start from a dedicated OpenWebUI instance with a dedicated database and
  storage volume.
- Expose it only on operator-controlled loopback or an equivalently isolated
  test route.
- Keep admin credentials in the ignored repository `.env`; never pass them on
  the command line or commit `control.private.json`.
- Build from the reviewed issue branch. The maintained direct Function/model
  id is `broker_reports_ndfl`; the legacy `broker_reports_gate1_pipe` Function
  must be inactive for the proof window.
- Install Playwright locally. The browser driver may be pointed at an absolute
  module path through `ISSUE306_PLAYWRIGHT_MODULE`.

## Build and prepare

From `services/broker-reports-gate1-proof`:

```powershell
python scripts/build_openwebui_pipe_bundle.py --target all
python -m pytest tests/test_broker_reports_issue306_live_control.py -q
```

Commit the tested code first: the browser driver refuses a dirty tracked tree.
From the repository root, prepare two temporary users, bounded grants, exact
release valves and the generated bundle. Use a new output directory for each
clean-room run:

```powershell
python services/broker-reports-gate1-proof/scripts/live_gate5_openwebui_product_path_control.py `
  --base-url http://127.0.0.1:18080 prepare `
  --output-dir local/issue306/control-review-a
```

The safe receipt must report:

- `function_id=broker_reports_ndfl`;
- `workspace_model_id=broker_reports_ndfl`;
- `legacy_function_inactive=true`;
- `release_valves_exact=true`;
- a valid `receipt_sha256`;
- an owner-issued 32-hex `control_run_id`;
- two temporary users, with the model visible only to user A.

## Browser-only supported-profile proof

```powershell
$env:ISSUE306_PLAYWRIGHT_MODULE='C:\path\to\node_modules\playwright'
Remove-Item Env:ISSUE306_SOURCE_SMOKE_ONLY -ErrorAction SilentlyContinue
$env:ISSUE306_CLOSE_TAB_PROOF='1'
node services/broker-reports-gate1-proof/scripts/live_issue306_openwebui_browser_goal.js `
  local/issue306/control-review-a/control.private.json `
  services/broker-reports-gate1-proof/tests/fixtures/issue306_synthetic_taxpayer_truth.txt `
  services/broker-reports-gate1-proof/tests/fixtures/issue306_supported_ordinary_trade.csv `
  local/issue306/blackbox-review-a
```

The driver uses rendered controls only. It uploads through the file input,
answers the visible Human Fact modal, downloads the visible private link,
reloads the chat, performs concurrent retry, verifies denial for user B, and
records the four final-note sections and visible values. With
`ISSUE306_CLOSE_TAB_PROOF=1`, it first closes an unanswered Human Fact tab and
proves that a second independent case reaches its question. It intentionally
exercises invalid date, invalid-checksum INN, deferred identity, correction,
and DRAFT-before-XML. The generated receipt is bound to the installed bundle,
browser-driver bytes, control receipt, and clean tested commit; do not edit it.

After the representative-source smoke below and cleanup of control A, prepare
a fresh `control-review-b`, remove `ISSUE306_CLOSE_TAB_PROOF`, and repeat into
`blackbox-review-b`. There must be no diagnostic intervention between prepare
and either clean run. The two controls must have different `control_run_id`
values and different prepared receipt hashes.

## Representative public source smoke

Set `ISSUE306_SOURCE_SMOKE_ONLY=1` and replace the source argument with the
locally held permitted representative PDF. A source that does not produce the
supported owner facts must end in a user-visible blocker, with no XML or
private download. Do not inject labels or facts through an API.

```powershell
$env:ISSUE306_SOURCE_SMOKE_ONLY='1'
node services/broker-reports-gate1-proof/scripts/live_issue306_openwebui_browser_goal.js `
  local/issue306/control-review-a/control.private.json `
  services/broker-reports-gate1-proof/tests/fixtures/issue306_synthetic_taxpayer_truth.txt `
  local/path/to/permitted-representative-report.pdf `
  local/issue306/representative-source-review
```

Run this before cleanup of control A. The resulting receipt has
`run_kind=representative_source` and must contain a blocker event, not a
manually asserted boolean.

## Cleanup

Always restore valves, grants, legacy Function state and delete the two
temporary users:

```powershell
python services/broker-reports-gate1-proof/scripts/live_gate5_openwebui_product_path_control.py `
  cleanup --state local/issue306/control-review-a/control.private.json
```

Require `status=restored` and `state_restored=true`. Delete or stop the
dedicated test container/volume only after preserving the redacted safe
receipt; never target a shared OpenWebUI database or storage path.

## Build the committed safe proof

After both controls report restored, run the issue-specific verifier. It
validates every input receipt hash, the required browser-event matrix, the two
downloaded byte hashes, official-XSD extraction through the existing XML
owner, visible-value equality, bundle/driver/control byte bindings, and both
cleanup receipts. It then writes the committed trace mechanically:

```powershell
python services/broker-reports-gate1-proof/scripts/build_issue306_safe_interaction_receipt.py `
  --base-sha db199ce082a5b40cade538e46f674c83a14b4d43 `
  --clean-run local/issue306/blackbox-review-a/interaction.safe.json `
  --clean-run local/issue306/blackbox-review-b/interaction.safe.json `
  --xml local/issue306/blackbox-review-a/3-ndfl-2025.xml `
  --xml local/issue306/blackbox-review-b/3-ndfl-2025.xml `
  --source-run local/issue306/representative-source-review/interaction.safe.json `
  --control-restored local/issue306/control-review-a/control-restored.safe.json `
  --control-restored local/issue306/control-review-b/control-restored.safe.json `
  --output docs/reports/2026-08-24/BROKER_REPORTS_ISSUE_306_INTERACTION_TRACE.safe.json
```

Never hand-edit the generated trace. The final CI test rechecks its receipt
chain and current tested-code manifest.
