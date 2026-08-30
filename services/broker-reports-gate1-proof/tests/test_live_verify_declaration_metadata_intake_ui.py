from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNNER = (
    ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "scripts"
    / "live_verify_declaration_metadata_intake_ui.js"
)


def test_browser_runner_is_explicitly_synthetic_and_uses_actual_loader():
    source = RUNNER.read_text(encoding="utf-8")

    assert "synthetic_openwebui: true" in source
    assert "full_openwebui_e2e: false" in source
    assert "synthetic_openwebui_real_chromium_actual_loader" in source
    assert "deploy/openwebui-static/loader.js" in source
    assert "loader_sha256" in source
    assert "page.addScriptTag({ content: loaderSource })" in source


def test_browser_runner_covers_terminal_ui_and_routing_behaviors():
    source = RUNNER.read_text(encoding="utf-8")

    for behavior in (
        "verifySuccessAndMultipart",
        "verifyCancelHasNoLeak",
        "verifyModelRaceFailsClosed",
        "verifyBusyAndDoubleClick",
        "verifyTerminalError(browser, 'error')",
        "verifyTerminalError(browser, 'malformed')",
    ):
        assert behavior in source
    assert "page.waitForEvent('filechooser')" in source
    assert "button.press('Enter')" in source
    assert "chooser.setFiles(" in source
    assert "multipartFieldNames" in source
    assert "assertExactMultipartFile" in source
    assert "['file']" in source
    assert "details.pdf" in source
    assert "application/pdf" in source
    assert "body.subarray(payloadStart, payloadEnd)" in source
    assert "headers['idempotency-key']" in source
    assert "aria-busy" in source
    assert "action_reenabled: true" in source
    assert "focus_returned: true" in source
    assert "duplicate_post_blocked" in source
    assert "verdict: 'PASS'" in source


def test_browser_runner_requires_prepared_local_playwright_without_hidden_install():
    source = RUNNER.read_text(encoding="utf-8")

    assert "BROKER_REPORTS_PLAYWRIGHT_MODULE" in source
    assert "playwright_dependency_missing" in source
    assert "npm install" not in source
    assert "npx playwright install" not in source
    assert "child_process" not in source
    assert "https://" not in source
    assert "Remote-User" not in source
    assert "cookie" not in source.lower()
    assert "production" not in source.lower()
