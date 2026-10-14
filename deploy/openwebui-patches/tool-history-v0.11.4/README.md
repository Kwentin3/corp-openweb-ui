# Native tool history backport

OpenWebUI 0.11.4 merges sequential tool rounds without assistant prose into an
earlier assistant message. Tool images are then moved after subsequent results.
This also changes an already submitted prompt prefix. Upstream fixed the same
converter in [PR #31593](https://github.com/open-webui/open-webui/pull/31593), commit
`e88e1f8119fa88110beca57ffa7f0578d97ce699`. This bundle applies that exact one-line
change, guarded by the full original and resulting `misc.py` hashes.

CI builds against the pinned official 0.11.4 image. Production preserves the
accepted media image `sha256:c4ba3bda7e228f99a246f1d823dfe2a8830dbd8fad6966d2e1862350fb8be423`
as its base. Tag that exact local image and pass the tag explicitly:

```sh
docker tag sha256:c4ba3bda7e228f99a246f1d823dfe2a8830dbd8fad6966d2e1862350fb8be423 corp-openwebui/media-0114-base:tool-history-c4ba3bda
docker build --build-arg OPENWEBUI_BASE_IMAGE=corp-openwebui/media-0114-base:tool-history-c4ba3bda -f runtime.Dockerfile -t corp-openwebui/openwebui-tool-history:upstream-31593 .
```

Run these commands from this directory. Only the three code/build files belong
in the build context; no environment files, credentials or chat data are needed.
The production candidate is pinned in the existing release Compose recipe.

The image checks nine native converter/installer cases, including sequential and
parallel calls, commentary between calls and results, image ordering, stable
prefixes, incomplete calls, unchanged guide content, repeat application and source
drift rejection. Four behavioral checks fail on the preserved base and all nine
pass on the candidate. A read-only replay of the failed private turn also keeps
its 17 completed results and places its initial render before all later edits.
These checks establish serialization correctness; browser acceptance separately
determines whether the document-generation loop is resolved.

Deployment must change only the WebUI image in the active server-owned Compose
recipe, preserving server-local environment, resource tuning and data volumes.
Keep that recipe and image for rollback. Remove this bundle when the selected
runtime includes the upstream fix and the same history checks pass natively.
