# Native tool history and Responses image transport

OpenWebUI 0.11.4 merges sequential tool rounds without assistant prose into an
earlier assistant message. Tool images are then moved after subsequent results.
This also changes an already submitted prompt prefix. Upstream fixed the same
converter in [PR #31593](https://github.com/open-webui/open-webui/pull/31593), commit
`e88e1f8119fa88110beca57ffa7f0578d97ce699`. This bundle applies that exact one-line
change, guarded by the full original and resulting `misc.py` hashes.

The same stateless loop unconditionally applies the Chat Completions image
fallback to Responses connections. It turns a tool image into a new user message
asking the model to analyze images. An authorized private request capture showed
the model answering that injected request instead of completing the original
document task. `apply_transport.py` preserves the existing multimodal tool-output
representation for Responses, using the native connection's `api_type`; other
providers keep their existing fallback. History replay and code-interpreter
continuations use the same selection. Both source files have exact version/hash
guards, idempotent application and drift rejection.

Boundary map:

- Connection/API type -> native `get_openai_connection` -> connection config -> middleware.
- Stored tool output -> native `convert_output_to_messages` -> tool content -> native provider converter.
- Images -> native `convert_url_images_to_base64` -> authorized inline image -> Responses function result.

The transport change is a representation adapter. It adds no prompt, task state,
tool loop, provider connection or document policy. Stateful provider storage is
not required. GPT-6 Luna uses the existing Responses connection and is removed
from the Filter's Chat Completions `no_reasoning_model_ids` valve through native
administration; provider credentials remain server-local.

CI builds against the pinned official 0.11.4 image. Production preserves the
accepted media/history image `sha256:1be70208df179647a572d6e61dfccf363cad57425d16607a9a610044a4a5592f`
as its base. Tag that exact local image and pass the tag explicitly:

```sh
docker tag sha256:1be70208df179647a572d6e61dfccf363cad57425d16607a9a610044a4a5592f corp-openwebui/context-base:history-6f7c84d4
docker build --build-arg OPENWEBUI_BASE_IMAGE=corp-openwebui/context-base:history-6f7c84d4 -f runtime.Dockerfile -t corp-openwebui/tool-context:responses-0114 .
```

Run these commands from this directory. Only the code/build files belong
in the build context; no environment files, credentials or chat data are needed.
The production candidate is pinned in the existing release Compose recipe.
The diagnostic provider-capture overlay is not part of that production pin.

The image checks nine native converter/installer cases, including sequential and
parallel calls, commentary between calls and results, image ordering, stable
prefixes, incomplete calls, unchanged guide content, repeat application and source
drift rejection. Four behavioral checks fail on the preserved base and all nine
pass on the candidate. A read-only replay of the failed private turn also keeps
its 17 completed results and places its initial render before all later edits.
These checks establish serialization correctness; browser acceptance separately
determines whether the document-generation loop is resolved.

Five additional checks import the installed middleware and provider converter:
Responses keeps the original user request and multimodal function result,
Chat Completions keeps its existing fallback, non-OpenAI models bypass the OpenAI
connection owner, a later edit stays after its render, and source drift fails.
Fixtures are synthetic; private captured requests and customer documents are
retained outside Git.

Deployment must change only the WebUI image in the active server-owned Compose
recipe, preserving server-local environment, resource tuning and data volumes.
Keep that recipe and image for rollback. Remove this bundle when the selected
runtime includes both fixes and the same history/transport checks pass natively.
