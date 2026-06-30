# OPENWEBUI SiliconFlow PaddleOCR-VL API Probe Report

Date: 2026-06-25

Status: blocked. No customer documents were used. No OpenWebUI production
configuration or production provider decision was changed.

## Verdict

Runtime availability is not proven.

Observed split:

- `https://api.siliconflow.cn/v1` matches the official CN docs and model
  evidence for `PaddlePaddle/PaddleOCR-VL-1.5`, but the local key was rejected:
  `401`, body: `"Api key is invalid"`.
- `https://api.siliconflow.com/v1` accepts the local key for `/models`, but
  neither checked PaddleOCR-VL id is exposed in that account model list.
- On `.com`, both `PaddlePaddle/PaddleOCR-VL-1.5` and
  `PaddlePaddle/PaddleOCR-VL` return `400`, code `20012`, message:
  `Model does not exist. Please check it carefully.`

Recommendation: mark blocked until a SiliconFlow CN API key that authorizes
`https://api.siliconflow.cn/v1` is available. Retry
`PaddlePaddle/PaddleOCR-VL-1.5` first. Do not select
`PaddlePaddle/PaddleOCR-VL` as the target id; the release notes say that id was
scheduled for offline removal and runtime did not expose it.

## Source Docs Checked

- SiliconFlow Vision docs:
  `https://docs.siliconflow.cn/en/userguide/capabilities/vision`
  - VLM requests use `/chat/completions`.
  - `messages.content` can include `image_url`.
  - `image_url.url` can be a normal URL or a base64 data URL.
- SiliconFlow CN multimodal docs:
  `https://docs.siliconflow.cn/cn/userguide/capabilities/multimodal-vision`
  - Multimodal models are called through `/chat/completions`.
  - The CN page includes PaddleOCR client usage sections.
- SiliconFlow chat completions API reference:
  `https://docs.siliconflow.cn/en/api-reference/chat-completions/chat-completions`
  - Auth format is `Authorization: Bearer <token>`.
  - Response shape can include `usage`.
- SiliconFlow model list API reference:
  `https://docs.siliconflow.cn/en/api-reference/models/get-model-list`
  - Endpoint: `GET /models`.
- SiliconFlow public model/commercial pages were checked only to confirm model
  availability signals. Commercial terms are not recorded in this GitHub
  report.
- SiliconFlow CN model square:
  `https://cloud.siliconflow.cn/open/models`
  - Lists `PaddlePaddle/PaddleOCR-VL-1.5` with vision/OCR positioning.
- SiliconFlow CN release notes:
  `https://docs.siliconflow.cn/cn/release-notes/overview`
  - Lists `PaddlePaddle/PaddleOCR-VL` among models scheduled for offline removal
    on 2026-04-29.
- PaddleOCR official usage guide:
  `https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PaddleOCR-VL.md`
  - Shows SiliconFlow usage with `vl_rec_server_url=https://api.siliconflow.cn/v1`
    and `vl_rec_api_model_name=PaddlePaddle/PaddleOCR-VL-1.5`.

## Local Secret Handling

- Added a local `.env` section for the probe:
  - `SILICONFLOW_API_KEY`
  - `SILICONFLOW_API_BASE_URL`
  - `SILICONFLOW_PADDLEOCR_VL_PRIMARY_MODEL`
  - `SILICONFLOW_PADDLEOCR_VL_FALLBACK_MODEL`
- The key value is not printed in this report.
- The key value is not included in the probe script.
- `.env` is gitignored in this repo.

## Synthetic Test Image

Artifact:

`docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/synthetic_test_document.png`

Properties:

- no customer data;
- no real personal data;
- Russian text;
- small table;
- visible marker: `SYNTHETIC TEST DATA`;
- SHA-256: `d4976f04ba0020b81e1025b6f5c1d6abb81c0e85f0cb8684a43e246ea71344b0`;
- size: `37,918` bytes.

Prompt used:

```text
Распознай документ. Верни Markdown и затем JSON с полями: text, tables, warnings. Не добавляй факты, которых нет на изображении.
```

## Model IDs Tested

Requested ids:

1. `PaddlePaddle/PaddleOCR-VL-1.5`
2. `PaddlePaddle/PaddleOCR-VL`

Runtime result:

| Base URL | Model id | `/models` visibility | Chat status | Runtime message |
| --- | --- | --- | --- | --- |
| `https://api.siliconflow.cn/v1` | `PaddlePaddle/PaddleOCR-VL-1.5` | not available because `/models` returned `401` | `401` | `Api key is invalid` |
| `https://api.siliconflow.cn/v1` | `PaddlePaddle/PaddleOCR-VL` | not available because `/models` returned `401` | not meaningfully tested after auth failure | auth gate blocks model proof |
| `https://api.siliconflow.com/v1` | `PaddlePaddle/PaddleOCR-VL-1.5` | false; `/models` returned 70 ids, target absent | `400` | `code=20012`, model does not exist |
| `https://api.siliconflow.com/v1` | `PaddlePaddle/PaddleOCR-VL` | false; `/models` returned 70 ids, target absent | `400` | `code=20012`, model does not exist |

## `/v1/models` Result Summary

Artifacts:

- `docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/models_ids_only.safe.json`
- `docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/cn_models_summary.safe.json`
- `docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/com_models_summary.safe.json`

Summary:

| Base URL | Status | Latency | Model count | `PaddlePaddle/PaddleOCR-VL-1.5` | `PaddlePaddle/PaddleOCR-VL` |
| --- | ---: | ---: | ---: | --- | --- |
| `https://api.siliconflow.cn/v1` | `401` | `2811 ms` | `0` | not visible | not visible |
| `https://api.siliconflow.com/v1` | `200` | `2315 ms` | `70` | not listed | not listed |

The `.com` model list artifact records only model ids and status metadata.

## Chat Completions Result

Endpoint attempted:

- `POST /chat/completions`

Artifacts:

- `docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/cn_probe_result.safe.json`
- `docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/com_probe_result.safe.json`
- `docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/com_fallback_model_probe_result.safe.json`
- `docs/reports/2026-06-25/siliconflow-paddleocr-vl-probe/minimal_text_chat_error_probe.safe.json`

Base64 `data:image/png;base64,...` input:

| Base URL | Model | Status | Latency | Result |
| --- | --- | ---: | ---: | --- |
| `.cn` | `PaddlePaddle/PaddleOCR-VL-1.5` | `401` | `698 ms` for image call; `2044 ms` for minimal text error probe | key invalid |
| `.com` | `PaddlePaddle/PaddleOCR-VL-1.5` | `400` | `1051 ms` for image call; `2621 ms` for minimal text error probe | model does not exist |
| `.com` | `PaddlePaddle/PaddleOCR-VL` | `400` | `1038 ms` for image call; `2153 ms` for minimal text error probe | model does not exist |

URL input:

- Not proven.
- A temporary public upload via `0x0.st` was unavailable.
- More importantly, no working PaddleOCR-VL model id was available, so URL
  acceptance could not be separated from model availability.

## Working Request Example

The request shape below is the exact intended request form. The key is redacted.
It did not produce a successful response with the current key/account split.

```bash
curl --request POST \
  --url https://api.siliconflow.cn/v1/chat/completions \
  --header "Authorization: Bearer <redacted>" \
  --header "Content-Type: application/json" \
  --data '{
    "model": "PaddlePaddle/PaddleOCR-VL-1.5",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "image_url",
            "image_url": {
              "url": "data:image/png;base64,<redacted>",
              "detail": "high"
            }
          },
          {
            "type": "text",
            "text": "Распознай документ. Верни Markdown и затем JSON с полями: text, tables, warnings. Не добавляй факты, которых нет на изображении."
          }
        ]
      }
    ],
    "stream": false,
    "temperature": 0,
    "max_tokens": 1600
  }'
```

## Response Shape Summary

No successful PaddleOCR-VL response was obtained.

Therefore:

- working model id: none proven;
- working endpoint: none proven for PaddleOCR-VL;
- accepts base64: not proven;
- accepts URL: not proven;
- returns Markdown: not proven;
- returns valid JSON by instruction: not proven;
- `usage` present: not observed;
- can normalize to `DocumentExtractionResultV1`: no, because there is no
  successful extraction payload.

## Usage Summary

- Runtime usage: absent, because no successful PaddleOCR-VL chat completion was
  obtained.
- Account metering: not observed. Failed auth/model-not-found probes are not
  evidence of a successful OCR extraction.

## Recommendation

Mark the SiliconFlow PaddleOCR-VL API probe as blocked.

Next retry condition:

1. Obtain or activate a SiliconFlow CN API key that works with
   `https://api.siliconflow.cn/v1/models`.
2. Re-run the same probe against `PaddlePaddle/PaddleOCR-VL-1.5`.
3. Use `PaddlePaddle/PaddleOCR-VL` only as historical/deprecated evidence, not
   as the preferred target id.

Do not make an OpenWebUI production provider decision from this run.
