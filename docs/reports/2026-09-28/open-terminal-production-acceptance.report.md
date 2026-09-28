# Open Terminal Office workflow production acceptance

Date: 2026-09-28.
Status: deployed and accepted on the production OpenWebUI route.

This report records the production state reached after the private candidate
reports [Office workflow completion](office-workflow-completion.report.md) and
[Terminal file handoff](terminal-file-handoff.report.md). Statements in those
reports that the candidate was not shared or deployed describe their earlier
qualification point and are no longer the current production status.
The customer-facing result is summarized in
[the delivery addendum](../../commercial/COMPLETED_WORK_2026-09-28_OPEN_TERMINAL_OFFICE_WORKFLOW.md).

## Released source and runtime

- Implementation: PR [#541](https://github.com/Kwentin3/corp-openweb-ui/pull/541),
  merge commit `5da32ea119fccad57ab03eb08effcdc5356864e7`.
- Proxy and health follow-up: PR
  [#542](https://github.com/Kwentin3/corp-openweb-ui/pull/542), merge commit
  `8b25a9ac2c580ffe459d3f3714066e157f6e3581`.
- PR #542 required CI completed successfully before merge.
- Production root: `/opt/openwebui-prd0`.
- OpenWebUI image:
  `corp-openwebui/openwebui:office-workflow-release-5da32ea1`.
- Official Open Terminal image pinned by digest:
  `ghcr.io/open-webui/open-terminal@sha256:81a5394b3cd4ae32adb600f2135f09ee124de37f26b0a780e2f5692472c0fc5c`.
- Both containers were healthy with restart count zero at final acceptance.
  The public OpenWebUI route, internal Terminal `/health`, and Terminal
  `/openapi.json` returned HTTP 200.

The release keeps upstream OpenWebUI and Open Terminal cores unmodified. The
installed extension layer is limited to the existing global Office Filter, the
`artifact-workflow` Skill, the `terminal_file_transfer` Tool, and the
`office-linux` Terminal connection.

## Installed contract

The Filter activates the workflow only for configured direct model IDs when the
current user request contains an Office attachment. Existing OfficeCLI remains
available. The agent can choose the specialized OfficeCLI operation or use the
general Linux environment when the operation is absent or unsuitable.

`stage_chat_file(file_id)` requires an explicitly authorized native chat file,
copies it into a fresh Terminal input directory, and verifies the transferred
bytes. It does not mutate or delete the source. `publish_terminal_file(path)`
snapshots a completed output, uploads it to native OpenWebUI Files, verifies the
bytes, emits the native attachment events, and returns the real result file ID
and download URL.

Only transient reads are retried once: HTTP 429/502/503/504 or an interrupted
connection, payload, or timeout. Writes are never retried blindly. Displayed
links are repaired only from a successful publication receipt with matching
native identifiers; unknown or model-invented locations remain untrusted.

The Skill requires a full source/part inventory, an explicit plan and completion
contract, progress checkpoints, preservation of inputs, final completeness and
content checks, and honest clarification or partial-result reporting when the
requested semantics cannot be preserved.

## Ordinary-user end-to-end acceptance

All document work and independent checks ran on the server Linux route. Local
Windows was used only for control and browser access.

### XLSX

The ordinary-user chat executed
`stage_chat_file -> run_command -> publish_terminal_file`. The output workbook
was independently reopened as OOXML. It contained sheet `Продажи`, zero formulas,
and values `D2=3000`, `D3=1500`, `D4=4500`. The output was a valid XLSX ZIP and
the source hash still matched the original.

### DOCX

The ordinary-user chat executed
`stage_chat_file -> run_command/get_process_status -> publish_terminal_file`.
The original heading, code, and table remained present; the requested paragraph
`Обработано в Linux` was added. The output was independently reopened with
`python-docx`, and the source hash still matched the original.

### PPTX

The ordinary-user chat executed
`stage_chat_file -> run_command -> publish_terminal_file`. The original slide and
code remained present. A second slide containing `Обработано в Linux` and
`PPTX Linux route verified` was added. Independent `python-pptx` inspection found
two slides, and the source hash still matched the original.

For each format, OpenWebUI created a durable native File and attachment with a
real `result_file_id` and working download path. This acceptance therefore covers
the user-visible route rather than only the Terminal API or filesystem.

## Defect found during acceptance

The first Linux attempt failed honestly with HTTP 502 and published no invented
result. The application-wide outbound proxy intercepted the internal request to
`http://open-terminal-office:8000`. A direct comparison showed the default request
failed with 502 while the same request with `NO_PROXY` succeeded with HTTP 200.

PR #542 adds `open-terminal-office` and `open-terminal-office:8000` to both
`NO_PROXY` and `no_proxy`, and accepts the actual Open Terminal health payload
`{"status":"ok"}`. After deployment, the existing chat resumed without
re-uploading the source and completed the three format checks. Final log review
found 19 successful OpenWebUI Terminal route responses and no route 5xx or
Terminal OpenAPI errors; Terminal recorded 76 successful responses and no 5xx.

## Multi-user boundary

`OPEN_TERMINAL_MULTI_USER=true` provides a distinct Linux home directory per
OpenWebUI user. Two ordinary users with the same session header received different
absolute home paths during acceptance.

All 23 current users were explicitly confirmed as mutually trusted, so the free
built-in shared-container mode was accepted. The users still share the container
kernel, process list, network, root-capable system state, and 2 GiB resource pool.
This mode is not an isolation boundary for mutually untrusted tenants. Such a
deployment requires separately isolated Terminals and, where required, network
policy.

## Rollback, evidence, and cleanup

Production evidence is stored under
`/opt/openwebui-prd0/releases/office-workflow-5da32ea1/`:

- `acceptance.json`;
- `release-state.json` with state `active_and_accepted`;
- `office-workflow-before.json`;
- `.env.before-terminal-no-proxy`;
- exact follow-up source archive `source-followup-8b25a9ac.tar`, SHA-256
  `bf8eb711902a631b94b696a2584198735f880a0e0c16a84671cee529d605d8d4`;
- previous image tag
  `corp-openwebui/openwebui:officecli-all-models-release-20260926`.

The installer rollback restores the previous global Filter first and then only
the owned `terminal_file_transfer`, `artifact-workflow`, and `office-linux`
resources. It preserves unrelated Terminal connections and the named user-home
volume unless deletion is separately reviewed.

Disposable users, chats, files, tags, local fixtures, and test Terminal homes were
removed after acceptance. A read-only database audit confirmed no rows remained
for the disposable user. Required production connection secret files remain
server-local with mode 0600 and are not included in Git.

## Acceptance limit

This release qualifies the generic transfer, execution, publication, and
verification workflow with representative XLSX, DOCX, and PPTX artifacts. It does
not qualify every possible Office construct or every model. Macro-enabled files,
protected content, external links, stale formula caches, or document-specific
layout constraints can still require clarification, a different method, or an
explicitly partial result.
