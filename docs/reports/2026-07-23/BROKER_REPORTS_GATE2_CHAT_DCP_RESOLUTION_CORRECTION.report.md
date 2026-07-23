# Broker Reports Gate 2 Chat DCP Resolution Correction

Date: 2026-07-23

Branch: `codex/broker-reports-native-gate2-continuation-correction-v1`

Base revision: `4899fe3d9fb7a1c108f853fa3a0e3014456fdb2f`

Status: `PASSED_PENDING_ATOMIC_RELEASE`

## Trigger

The terminal native-browser audit in PR `#60` proved that a normal Gate 2 UI
request does not carry the internal DCP ref. The Functions previously required
that low-level ref in the model-facing request and therefore could not use the
already authoritative chat scope.

The triggering report is
[BROKER_REPORTS_NATIVE_BROWSER_CLICKTHROUGH_V2_NOT_CLOSED.report.md](./BROKER_REPORTS_NATIVE_BROWSER_CLICKTHROUGH_V2_NOT_CLOSED.report.md).

## Correction

This slice changes only the Gate 2 server boundary.

A new `Gate2ChatDcpResolverFactory` resolves the DCP from:

- authenticated user ID;
- server chat ID;
- active ArtifactStore lifecycle;
- exact artifact type `domain_context_packet_v0`.

Resolution succeeds only when exactly one record exists. Missing, wrong-owner
and ambiguous scopes fail closed. An explicit DCP ref remains authoritative
for maintained operator and test calls.

Both existing Gate 2 Functions now use this order:

1. accept an explicit ref when present;
2. otherwise read `chat_id` from server metadata or the native request;
3. resolve one owner-scoped active DCP;
4. continue through the existing ArtifactStore, WorkloadAuthority, prompt and
   provider factories.

The resolver is bundled only with the two Gate 2 Functions. The Gate 1 bundle
is byte-identical to the accepted release.

## Scope boundary

Changed:

- Gate 2 source Function;
- Gate 2 domain Function;
- Gate 2-only DCP resolver;
- closed-world Gate 2 bundle allowlist;
- focused tests.

Not changed:

- loader or UI;
- Gate 1 source or bundle;
- private intake Action;
- semantic visual-table JSON;
- VLM prompts;
- provider policy or model selection;
- ArtifactStore schema;
- WorkloadAuthority;
- Knowledge/RAG/vectorization;
- OCR or crop extraction;
- release/rollback implementation.

This slice does not claim to close Goal 2. The UI still needs a separate
correction to preserve and submit the completed Gate 1 chat continuation.

## Tests

Focused resolver suite:

```text
7 passed in 0.89 s
```

Affected Gate 2 and architecture regression:

```text
62 passed in 24.44 s
```

Full Broker Reports service suite:

```text
collected: 1167
passed: 1147
failed: 0
skipped: 20
xfailed: 0
xpassed: 0
warnings: 5
pytest duration: 98.55 s
```

The 20 skips are the existing explicit offline private benchmark cases. No
skip was added by this correction.

Independent checks:

- Ruff on all changed maintained Python files: passed;
- compileall for the package, Functions and scripts: passed;
- repository privacy guard: `3 passed`;
- `git diff --check`: passed;
- factory and closed-world architecture tests: passed;
- Gate 1 bundle exclusion test: passed.

The repository has no accepted repo-wide Ruff contract; the established
changed-file contour was used, matching the final integrated regression
receipt.

## Deterministic bundles

Two consecutive full generations were byte-identical:

| Bundle | SHA-256 |
|---|---|
| Gate 1 | `a042ff14d0bc26a4c207db9b49d10ca3be4e3b2483e60e21a479e1e8f2f70519` |
| Gate 2 source | `45de78ac87f44a7f30d8dacc4d3d1bd3edbbafbc5002708776726d51edf2ce3e` |
| Gate 2 domain | `c26ae568bcaa8987abb581528abe20299ff50d3b853d402d31253211349be6dd` |

Gate 1 equals the accepted live bundle. Both Gate 2 hashes changed as
expected. The bundles contain no workspace-only path or ghost dependency.

## Privacy and runtime

- Customer labels, values and filenames added to Git: `0`.
- Private evidence added to Git: `0`.
- Provider output added to Git: `0`.
- Stage mutations in this correction branch: `0`.
- Semantic contract changes: `0`.
- Prompt changes: `0`.
- Knowledge/RAG/vector changes: `0`.

The next mandatory step after merge is an atomic Gate 2 Function release with
rollback proof, followed by a fresh browser rerun.

`GATE2_CHAT_DCP_RESOLUTION_CORRECTION`:
`PASSED_PENDING_ATOMIC_RELEASE`.
