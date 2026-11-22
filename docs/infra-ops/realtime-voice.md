# Native Realtime voice access

18 November 2026: native Realtime enabled and accepted through the browser,
server and provider path. This dated acceptance does not cover a physical
microphone, audible playback on customer equipment or mobile browser behavior.

## Configuration and access

The accepted runtime is OpenWebUI 0.12.2, image
`sha256:39f3fd9c25c2529767a0f4d5a99991216b3eda0d8891b3fcd49c2fd80ba7540a`.
Native Audio settings own Realtime: OpenAI/API-key authentication,
`gpt-realtime-2.1`, voice `marin`, transcription `gpt-transcribe` and the
built-in call prompt. The existing protected server-side key is reused.
Microphone dictation remains on Lemonfox; ordinary TTS remains on OpenAI `tts-1`.

Administrators have call access by role. Ordinary users need membership in
the dedicated `Realtime` group. Native permissions are additive: keep global
`chat.call=false`, grant calls only in `Realtime`, and avoid call grants in other
groups. Preserve unrelated rights, including global `chat.stt=true` and
`chat.tts=true`. Native Allow Call covers Standard and Realtime together;
the call mode is instance-wide. Individual membership belongs to the protected
native user/group registry, not this repository.

Realtime audio goes directly to OpenAI and is outside the LiteLLM employee
budgets. No new service, image build or OpenWebUI core patch was needed.

## Operator use

Refresh the portal, select the ordinary chat model, leave the composer empty
and click **Voice mode / Режим голоса**. Allow microphone access and finish with
the native End call control. Manage membership under
**Admin → Users → Groups → Realtime**. Audio settings are under
**Admin Panel → Settings → Audio → Voice calls**.

The existing WebUI environment must contain `WSS_PROXY` using the approved
outbound proxy. aiohttp selects proxies by URL scheme: an HTTPS proxy alone
does not cover `wss://`. Preserve this variable during deployments without
publishing its value. The native proxy fix required one intentional WebUI
recreation with the accepted image, existing mounts and runtime limits.
The exact environment file and Compose selectors belong to the protected
deployment inventory; use that owner rather than creating another deployment.

## Acceptance on 18 November

- Native WebSocket authorization returned `bridge.ready` for administrators
  and a temporary ordinary user in `Realtime`. Outside that group the ordinary
  user received `Call permission denied`; removing membership denied a new call.
- The browser Voice mode consumed a known Russian audio fixture through
  `getUserMedia`/AudioContext and the native recorder/worklet. OpenAI transcribed
  an explicit request to pass `27 × 14` to the selected `gpt-6.1-sol` chat model.
  Native `generate_chat_completion` returned 378 and Realtime spoke the answer.
  Transcription, chat generation and voice output were not mocked.
- An arithmetic-only phrase was answered directly by the voice model. Handoff
  depends on that model under the built-in prompt; not every substantive request
  is guaranteed to delegate. Realtime uses the selected chat's enabled features.
- Outside the group, an ordinary user recorded a separate Russian fixture with
  actual MediaRecorder. One native Lemonfox transcription returned the source
  text, preserved existing typed text, inserted the transcript once and did not
  send a chat request. The composer kept Dictate without showing Voice mode.
- STT/TTS objects, unrelated rights and existing account roles/settings matched
  the baseline. Owned synthetic chats, temporary user/membership, transcription
  cache files and bounded browser jobs were removed and their absence checked.

These checks establish the tested browser/server/provider and authorization
paths. Device-specific microphone, playback and mobile checks remain unverified.

## Recovery and retained evidence

Protected configuration and deployment snapshots, the scoped rollback helper,
safe receipts and hash-verified browser evidence remain in the operator evidence
store under the `realtime-voice-20261118` task identifier. Exact locations and
membership identifiers stay in the private operator inventory. Preserve these
assets; do not commit environment snapshots, credentials or user records.

The configuration rollback rehearsal checked the live state without applying
an actual rollback. The helper defaults to rehearsal; application requires an
explicit operator action, a current administrator credential and drift checks.
Restore only the touched Audio/default/group call settings, preserving current
STT/TTS and unrelated state. Do not overwrite newer changes with a whole snapshot.

Removing `WSS_PROXY` needs a WebUI recreation to take effect and is unnecessary
when only disabling Realtime. Any authorized recreation must reuse the recorded
Compose owner, exact image, mounts and resource limits, without rebuilding or
recreating unrelated services. Follow the protected deployment snapshot.

## References

- [Native Voice Mode](https://docs.openwebui.com/features/chat-conversations/chat-features/voice-mode/)
- [Additive permissions](https://docs.openwebui.com/features/authentication-access/rbac/permissions/)
- [aiohttp WebSocket proxy support](https://docs.aiohttp.org/en/stable/client_advanced.html#proxy-support)
- [Existing microphone dictation](microphone-stt.md)
