# Broker Reports Issue #310 — OpenWebUI product gate follow-up

## Result

The independent review of PR #311 was addressed in the same PR. The review
started from exact head `b08e74cf8ff8cf8001b1e859a8d6294cca2d2567`.
The accepted code and live-evidence head before this report-only commit is
`bed97a943ab1fafff49b501f4a1a2d45e14e4543`. PR #311 and Issue #310 remain
open and unmerged.

## Boundary correction

The LLM remains the primary presentation layer for explaining the current
owner-produced public context and asking one current question. It no longer
interprets a user answer inside the active Pipe request.

Answer adaptation is deliberately smaller:

- direct owner-accepted input goes straight to the current Human Fact owner;
- otherwise the presentation adapter may recognize exactly one literal
  four-digit year or one exact visible option already emitted by the current
  owner;
- negation, delegated choice, multiple candidates and substring-only matches
  fail closed;
- a recognized candidate creates no fact and is shown for a separate exact
  user confirmation;
- the separate reply is rebound to the server-held current publication and is
  normalized and published only by `Gate5HumanGapClosureRuntime`.

There is no pending-answer registry, second Human Fact owner, workflow engine,
source authority, Tax Model owner or XML path. `ARCHITECTURE_POLICY_VERSION` is
`broker_reports_architecture_policy_v13` and the authority map now names the
presentation context/validator and the Pipe transport separately.

## Review blockers

1. Presentation transport now uses only the administrator-pinned HTTPS
   OpenWebUI origin. Caller `request.base_url`, redirects and responses over
   1 MiB fail closed; a user bearer is never forwarded to a caller-selected
   address.
2. `Не подтверждаю`, `Не 2025 год` and category negation cannot become a
   positive candidate. Even a positive natural phrase requires a separate
   exact confirmation before a fact exists.
3. Public-dialogue and residency suites are part of the required active
   production CI job.
4. The full privacy-safe journals are committed under `issue310-live/`, not
   represented only by receipt hashes. Their mechanical guard checks receipt
   hashes, Git blobs, exact code head, bundle, all routes, event counts,
   T-Bank corpus identity, absence of hidden refs/12-digit values and the
   prepared-to-restored control chain.
5. Workload keepalive performs a synchronous persisted renewal before the
   background loop. The queue test uses persisted SQLite renewal/event proof
   instead of a blind scheduling sleep and passed 25/25 stress repetitions.
6. The active architecture authority map explicitly records the
   representation-only presentation boundary and its forbidden knowledge.

## Failed experiment and root cause

Intermediate exact head `54f79f3606d27e257c30bfeba02fa9ccae06cd64`
had green exact-head CI, but its clean-room chat did not complete after the
natural `Беру 2025 год.` answer. A separate sanitized call to the same pinned
`/api/chat/completions` endpoint returned HTTP 200, so transport availability
was not the defect. The failure was the nested answer-interpretation completion
inside the already active chat request. That run produced no accepted receipt,
was excluded, and its proof window was restored before the correction.

The minimal correction removed the nested answer-model contract and call. The
model still renders the public dialogue; deterministic literal recognition
only proposes a visible answer and cannot publish it.

## Exact-head live matrix

All accepted runs below used code head
`bed97a943ab1fafff49b501f4a1a2d45e14e4543`, generated bundle SHA-256
`c3c92ce5c2b427ac8f6fef3a6b4954f7bdb9f8ed9a7220dec8f7b9595d8f1763`
and the real browser UI.

| Route | Events | Result | Receipt SHA-256 |
| --- | ---: | --- | --- |
| supported closed trade | 22 | natural answer -> separate confirmation -> private XML; close-tab, correction, resume/retry and second-user ACL proved | `94ab3c626592ee27f77b47ac52e8a0a97d9461b10c1c055762af4a2614df3fe8` |
| unsupported 2022: analysis | 2 | analysis, no XML/download | `d0740f2862390850171b986c5caa0d4eec92252bf3597a9f36cf8404cdbc8e9a` |
| unsupported 2022: surrogate | 2 | draft visible in primary Pipe branch, no XML/download | `ec1a56a6d9918c2ea9344567b581192cf4a663f225a6301571cad231681cfbb3` |
| unsupported 2022: stop | 4 | resumable stop plus fresh `2022 -> 2025 -> 2022` mode question | `c8c6479c5d6bf4ded2dfbce04a1dfdf6306fa3f52469c71e29a4788d7c659c66` |
| open long | 1 | retained outside tax base, no XML/download | `ba15ab398708d75104f5a70b3f60be450a0a9762f83bf3030f492724ca29db07` |
| sale only | 1 | prior-position history requested; no invented purchase/short or XML | `ac7fe2e8a0f9f2fdb2b611e8f9273f52ce22bb6c963b47f1e6bbff1f3ff9fe7b` |
| representative T-Bank PDF | 1 | source gap explained with a next action; no semantic fallback or XML | `f182cbfce71bbfed5b0b34f86543afd36e16537a0d505da377591920a9a4a834` |

The representative PDF bytes match corpus SHA-256
`25c3b0606ce86852f6ac8fdf6feccbefedb609bcffc5c1581dc95b9b81c5da67`.
The aggregate index is
`BROKER_REPORTS_ISSUE_310_INTERACTION_TRACE.safe.json`; every listed journal is
available in full next to it.

Open short remains an exact, intentionally unclosed production boundary:
`gate4_ordinary_trade_security_position_source_contract_missing`. The active
qualified projection does not produce `position_effect=OPEN_SHORT`, so there
is no genuine owner-produced browser fixture that may claim a proven short.
The production composition and public-surface regression prove the fail-closed
machine blocker and plain-language explanation. Creating a source mapping or
injecting the historical Gate 4 test contour merely to manufacture a browser
receipt would violate the Issue boundary; this route is therefore reported as
an absent production owner, not as a passed live short.

## Verification

- focused dialogue/Pipe/architecture/release set: `136 passed`, five existing
  SWIG warnings;
- required active ordinary-trade production job locally: `321 passed`, the
  same five warnings;
- release/bundle/architecture guards: `61 passed`, the same five warnings;
- workload lease stress: `25/25` passed;
- Ruff, JavaScript syntax, workflow parsing, `git diff --check` and generated
  bundle byte parity: passed;
- exact-head GitHub CI for `bed97a9...`: run `32960883439`, job
  `98152733528`, `success` in 8m10s.

After the browser matrix, all eight temporary users and proof-only settings
were removed/restored. Control prepared receipt is `a91b81eb...`; restored
receipt is `1a1c11d5...` with `state_restored=true`.

The final report commit necessarily changes the Git head without changing the
product bundle or browser driver. Exact-head CI and the browser matrix are
repeated after that commit; their immutable final SHA and receipt hashes are
published in PR #311 and Issue #310.

## Private XML publication follow-up

The attempted final-head repetition on `9406dc6a638fdd8d960074f672c671dca8ec90fc`
found one further product defect and produced no accepted receipt. After a
valid declaration had been downloaded, re-uploading the byte-identical source
created another native Files record for the same user, case and XML bytes.
Readback confirmed that this was not a browser link-selection error: the two
records had equal case and XML hashes but different valid execution receipt
hashes.

The cause was a wrong identity boundary. `_publish_ndfl_xml_file` included the
current execution receipt hash in the deterministic native file ID. A receipt
proves one execution's provenance; it is not the semantic identity of the
downloadable XML. The minimal correction keeps the owner in the maintained
Pipe and defines native logical file identity as:

```text
authenticated user + case scope SHA-256 + XML SHA-256
```

The first valid receipt remains immutable provenance metadata. Reuse checks
the exact owner, stable publication-identity hash, case, XML hash, physical
bytes and the retained receipt's type. A change of XML bytes, authenticated
user or case still creates a distinct File; a different valid receipt alone
does not. No source, Human Fact, tax, XML, storage or receipt authority was
added.

Adversarial tests prove sequential and concurrent calls with distinct valid
receipt hashes converge on one native File, a losing physical attempt cannot
delete the winner, and corrupted retained receipt metadata fails closed.
Local results are `322 passed` for the required active production guard and
`46 passed` for the architecture/bundle/privacy/control set.

Exact code head `1d57c18fd3acf4f907b2607a69e94fd2c4ec0a66` passed required
CI run `32967848711`, job `98174343284`. The post-CI real OpenWebUI clean-room
run completed all 22 events and produced browser receipt
`7b568ae0d6f7ad6a2ec0c29453ec265de162bb28ac0e5667f817593db11ffa05`.
It proved reload/resume, byte-identical source re-upload with the same logical
download link, two concurrent rendered retries, and second-user model/file/case
denial. Native Files readback showed exactly one record for the final
case+XML hash. The different pre-correction XML remained a separate expected
record because the declaration-date correction changed XML bytes.

The follow-up safe receipt is
`issue310-live/1d57c18-private-file-idempotency.safe.json`, receipt SHA-256
`ebb520b267944156f65549591afb7fae44a1c3985e7cb2d6d7af492f8d5753d3`.
The proof window was restored: control receipt
`2c9f6eccee878398f6ca7f665ac3cd29be4daca07898696ed7a7ed039270dae3`
has `state_restored=true`, all eight temporary users were removed, and the
bootstrap layer was restored.

## Natural-language answer interpretation follow-up

The next independent review started from exact head
`579681bf6d4cf39949f8806b583e588d3b7cc664`. It correctly found that the
previous safety correction had also removed the product's ability to
understand ordinary free-form answers. The final accepted live run exercised
code head `a6318b8006911f1551616602492e32bbd49dcbc3` and generated bundle
SHA-256 `9cfe6bef2a8a4303a88a5cc6dc8db5ee8121aa8d0edadea9e5ffd150ab948c64`.

The corrected boundary keeps one owner per meaning:

- one bounded presentation-model call receives only the safe current public
  context and the current user reply;
- its strict result is `CLARIFY | CANDIDATE`, visible wording, one normalized
  public answer and one verbatim evidence quote;
- the Pipe rejects hidden owner codes, unknown public options, direct
  negation, non-verbatim evidence and owner-invalid candidates;
- a valid candidate is still not a Human Fact and is shown through native
  OpenWebUI confirmation;
- only after explicit confirmation does the existing
  `Gate5HumanGapClosureRuntime` validate and publish against the server-held
  current request publication;
- refusal, ambiguity, model failure or missing confirmation creates no fact
  and leaves the same question family current;
- the interpretation call also owns the visible message for that turn, so the
  Pipe cannot make a second presentation call after confirmation.

No pending-answer registry, second Human Fact owner, source/tax authority,
workflow engine or alternate persistence path was added. The architecture
snapshot is `broker_reports_architecture_policy_v14`.

### Failure-to-fix cycle

The first live attempts were not accepted as evidence. They exposed four
presentation-path defects in sequence: the model was allowed to emit
runtime-owned contract wording, the native roleless confirmation surface was
not located, its negative action is labelled `Отменить`, and a completed
assistant turn could be persisted without reaching the active browser event
stream. A later attempt isolated an SSH-tunnel interruption; it did not produce
an accepted receipt and caused no product change.

The minimal corrections were:

- runtime-owned schema version, exact normalized public value and
  confirmation/clarification wording;
- exact title-and-buttons binding for the native confirmation surface;
- host-owned replay of an already completed assistant leaf, allowed only for
  the exact authenticated user, chat, parent user text and NDFL model;
- one browser reload after a lost terminal event, with no message resend and
  exact last-user/terminal-assistant adjacency required.

The replay seam does not rerun the model or any domain owner. Negative tests
reject incomplete, foreign-model, foreign-workspace and misbound-parent leaves.

### Accepted real OpenWebUI proof

The final clean-room browser run used the real pinned OpenWebUI presentation
model `models/gemini-3.5-flash`, native confirmation UI and only browser-visible
product actions. It completed 24 journal events and produced the privacy-safe
receipt
`665922447a89975ffaca23c9e7539a100a5121a2129e3e1c00365f59f9c4f869`.
The full journal is
`issue310-live/a6318b8-natural-language-confirmation.safe.json`.

| Current question | Free answer | Model result | User action | Fact |
| --- | --- | --- | --- | --- |
| tax period | `не 2025` | `CLARIFY` | no confirmation offered | not created |
| tax period | `Беру 2025 год.` | `CANDIDATE: 2025` | confirmed | created by existing owner |
| capacity | `я обычный человек, не ИП` | `CANDIDATE` | confirmed | created by existing owner |
| filing | `не подтверждаю` | `CLARIFY` | no confirmation offered | not created |
| filing | `может первая, а может корректирующая` | `CLARIFY` | no confirmation offered | not created |
| filing | `подаю первый раз` | `CANDIDATE: INITIAL` | rejected | not created |
| filing | `подаю первый раз` | `CANDIDATE: INITIAL` | confirmed | created by existing owner |
| signer | `подписывать буду сам` | `CANDIDATE` | confirmed | created by existing owner |

The separate delegated-choice answer was also rejected without a model-owned
fact. Every recorded interpretation turn has
`domain_provider_calls_total=0`; direct already-owner-readable inputs do not
need an interpretation completion. The final XML was created only after the
confirmed facts and was downloaded through the native private Files route.

The external HTTPS proxy audit is committed as
`issue310-live/a6318b8-presentation-proxy-audit.safe.json`. Across the complete
browser control, including correction and concurrent retry checks, all 50
presentation requests returned HTTP 200, used only the pinned model, carried
`presentation_only=true`, and belonged only to dialogue rendering (26) or
answer interpretation (24). Aggregate proxy counts are not presented as a
per-turn proof: request hashes identify message bytes, not a browser turn. The
one-call interpretation boundary is instead enforced in the Pipe and its
focused adversarial tests.

Control run `adec79d9beb1cfb3dd50a180983fa5ae` was prepared with receipt
`a8661419840b382be85e94797542b7fc7a21af14e4a0c58286375e712d4496ad`
and restored with receipt
`6090296ea34d6c8c65beab26d2af904877cb0725f9d7e75f65932c9271faa248`.
The restored receipt has `state_restored=true`; both safe receipts are committed
next to the journal.

### Verification

- active ordinary-trade production guard: `333 passed`, five existing SWIG
  warnings;
- focused dialogue/Pipe/browser-driver guard: `90 passed`, the same warnings;
- browser-driver static contract: `8 passed`;
- generated bundle byte parity, Ruff, JavaScript syntax and `git diff --check`:
  passed;
- exact code-head CI for `a6318b8...`: run `33011617367`, job
  `98319052968`, `success` in 10m28s.

The evidence/report commit changes only tracked proof material after the live
run. Its new exact PR head and exact-head CI are published in PR #311 and Issue
#310 after CI completes. PR #311 and Issue #310 remain open; no merge is
performed.
