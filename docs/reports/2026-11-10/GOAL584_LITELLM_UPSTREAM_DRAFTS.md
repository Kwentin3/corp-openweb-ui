# Local upstream drafts — not submitted

Prepared 2026-11-10. Public-safe wording only. No issue, comment, PR or provider
request was sent. Each draft is scoped to the pinned LiteLLM 1.105.1 study;
current main/released images have not been replayed with this reproduction.
Before any separately approved submission, select a target commit, check the
linked existing report and attach a small reproducible fixture plus exact
before/after observations. Do not describe an untested latest release as affected.

## 1. Cached authoritative spend floor can undo a completed calendar reset

Suggested title: `Cached positive DB floor can raise a post-calendar-reset spend counter`

Related, not claimed duplicate: [PR #40940](https://github.com/BerriAI/litellm/pull/40940)
addresses stale key/user/team object caches and reset retries; it is not merged
as of this check. Exact upstream replacement remains unconfirmed.

Observed boundary: `get_current_spend` → `_authoritative_floor_spend` in
`litellm/proxy/proxy_server.py` on the pinned 1.105.1 image.

Minimal deterministic setup, without paid calls:

1. Use a disposable native budget DB/cache and one budgeted user/key.
2. Let durable spend and the cached `spend_db_floor:<counter_key>` become positive,
   for example `8`, while retaining that marker within its TTL.
3. Complete a calendar budget reset so durable spend and the live spend counter
   are zero. Ensure the old positive floor marker is still present. The reset
   must complete before starting the admission read; this is not an in-flight
   read/reset race reproduction.
4. Call the native spend/admission path with its post-reset source state.
5. Inspect durable spend, the live counter and the floor marker.

Expected: an obsolete cached floor does not raise the new-period live counter.
Observed on the pinned source/stand: trusting the cached positive marker can
restore the pre-reset value and reject an otherwise usable budget.

Local bounded mitigation revalidates a cached floor before it raises the live
counter, using the existing per-counter reseed lock. A marker written during
the DB await retains precedence. It does not solve a read begun before a
calendar reset that writes no reset marker. This limitation should stay explicit.

## 2. Preserve provider Usage presence separately from normalized token values

Prefer a focused follow-up to existing [issue #37992](https://github.com/BerriAI/litellm/issues/37992)
over opening a duplicate zero-vs-missing issue. That report is open and describes
explicit zero being replaced by local estimates on disconnect. The additional
boundary here is raw CC SSE JSON before OpenAI SDK 2.33.0 parsing and LiteLLM
stream assembly, not merely the final `Usage` object.

Minimal generic replay through the actual async OpenAI-compatible CC route:

```text
data: {"id":"chatcmpl-demo","object":"chat.completion.chunk","created":1,"model":"demo","choices":[{"index":0,"delta":{"role":"assistant","content":"OK"},"finish_reason":null}]}
data: {"id":"chatcmpl-demo","object":"chat.completion.chunk","created":1,"model":"demo","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}}
data: [DONE]
```

Replay the same stream with the final `usage` omitted, `null`, incomplete or
invalid, then with a consistent nonzero triplet. Retain the raw provider event
and the native same-call logging outcome. Also interrupt after the first event.

Expected: a complete explicit zero remains distinguishable from unavailable or
invalid provider usage. Local estimates may be useful, but cannot establish
that the provider actually supplied complete usage. A successful HTTP request,
zero-valued assembled Usage or completed stream alone does not prove presence.

The pinned local mitigation observes JSON within the original SDK stream parse
path and retains a request-local presence/validity stamp bound to the native
call and response. It does not replace content assembly, tool handling or
LiteLLM pricing. Later main uses a changed request implementation, so the patch
must not be presented as directly applicable there without reproduction.

## 3. Deliver cancellation to the native post-call lifecycle before accounting

Suggested title: `Async CC disconnect before first chunk can bypass post-call observer lifecycle`

Related: merged [PR #33736](https://github.com/BerriAI/litellm/pull/33736) provides
native partial-disconnect billing. Open [PR #49715](https://github.com/BerriAI/litellm/pull/49715)
proposes draining provider output after disconnect; that behavior is outside
this reproduction. The issue here is invocation and evidence continuity for
existing callbacks, with no new billing service.

Minimal generic native-proxy reproduction:

1. Configure a scripted OpenAI-compatible upstream and a small existing
   CustomGuardrail observer recording the native call identity, Usage presence
   and terminal hook outcome. Use disposable native DB/cache and no paid API.
2. Start `/v1/chat/completions` with `stream=true`. Let the proxy receive upstream
   HTTP 200, then hold the first SSE event. Do not require downstream HTTP 200:
   no downstream byte may have been emitted at this point.
3. Cancel the client request and release/stop the scripted upstream.
4. Inspect the actual CC generator cleanup, callback invocation and native spend
   row for that call. Repeat after one content event with no provider Usage.

Expected: cancellation reaches the existing cleanup/failure lifecycle with
same-call logging evidence even if there is no partial success response.
When a partial response exists, the post-call observer runs before the native
success dispatch. Terminal handling must not double-count a call or release
its concurrency slot twice.

Pinned mitigation carries the exception from the actual CC generator into the
shared cleanup, reuses the native deferred guardrail operation before partial
success, and exposes the same native Logging evidence to CustomGuardrail failure
hooks. Serializing logger callbacks retain their normal request shape.

The isolated acceptance observed one native failure row after pre-first-chunk
cancel and a downstream policy reading unavailable usage. That is pinned stand
evidence, not a claim about production, every route or the latest upstream image.
