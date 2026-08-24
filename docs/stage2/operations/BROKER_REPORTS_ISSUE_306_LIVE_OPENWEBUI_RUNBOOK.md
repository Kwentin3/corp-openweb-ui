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

From the repository root, prepare two temporary users, bounded grants, exact
release valves and the generated bundle:

```powershell
python services/broker-reports-gate1-proof/scripts/live_gate5_openwebui_product_path_control.py `
  --base-url http://127.0.0.1:18080 prepare `
  --output-dir local/issue306/control-run
```

The safe receipt must report:

- `function_id=broker_reports_ndfl`;
- `workspace_model_id=broker_reports_ndfl`;
- `legacy_function_inactive=true`;
- `release_valves_exact=true`;
- two temporary users, with the model visible only to user A.

## Browser-only supported-profile proof

```powershell
$env:ISSUE306_PLAYWRIGHT_MODULE='C:\path\to\node_modules\playwright'
Remove-Item Env:ISSUE306_SOURCE_SMOKE_ONLY -ErrorAction SilentlyContinue
node services/broker-reports-gate1-proof/scripts/live_issue306_openwebui_browser_goal.js `
  local/issue306/control-run/control.private.json `
  services/broker-reports-gate1-proof/tests/fixtures/issue306_synthetic_taxpayer_truth.txt `
  services/broker-reports-gate1-proof/tests/fixtures/issue306_supported_ordinary_trade.csv `
  local/issue306/blackbox-run
```

The driver uses rendered controls only. It uploads through the file input,
answers the visible Human Fact modal, downloads the visible private link,
reloads the chat, performs concurrent retry, and verifies denial for user B.
It intentionally exercises invalid date, invalid-checksum INN, deferred
identity, correction, and DRAFT-before-XML.

Validate the downloaded bytes with the existing XML projection owner:

```powershell
@'
from pathlib import Path
from broker_reports_gate1.gate5_full_target_xml_projection import Gate5FullTargetXmlProjectionRuntimeFactory
xml = Path(r'..\..\local\issue306\blackbox-run\3-ndfl-2025.xml').read_bytes()
result = Gate5FullTargetXmlProjectionRuntimeFactory.create().extract_supported_profile_values(xml_bytes=xml)
assert result['status'] == 'extracted'
assert result['xsd_valid'] is True
'@ | python -
```

## Representative public source smoke

Set `ISSUE306_SOURCE_SMOKE_ONLY=1` and replace the source argument with the
locally held permitted representative PDF. A source that does not produce the
supported owner facts must end in a user-visible blocker, with no XML or
private download. Do not inject labels or facts through an API.

```powershell
$env:ISSUE306_SOURCE_SMOKE_ONLY='1'
node services/broker-reports-gate1-proof/scripts/live_issue306_openwebui_browser_goal.js `
  local/issue306/control-run/control.private.json `
  services/broker-reports-gate1-proof/tests/fixtures/issue306_synthetic_taxpayer_truth.txt `
  local/path/to/permitted-representative-report.pdf `
  local/issue306/representative-source-run
```

## Cleanup

Always restore valves, grants, legacy Function state and delete the two
temporary users:

```powershell
python services/broker-reports-gate1-proof/scripts/live_gate5_openwebui_product_path_control.py `
  cleanup --state local/issue306/control-run/control.private.json
```

Require `status=restored` and `state_restored=true`. Delete or stop the
dedicated test container/volume only after preserving the redacted safe
receipt; never target a shared OpenWebUI database or storage path.
