# G3.4D strict alias contract

Status: `LOCAL_PROVEN_LIVE_BLOCKED`

Date: 2026-08-07

## Canonical response schema

The existing `Gate3LabelingResponseV1` schema remains the sole model-output
contract. Its `target_alias` property is:

```json
{
  "type": "string",
  "pattern": "^t[0-9]{3,}$",
  "description": "Exact bare alias value shown in the document: for [t123], return t123. The value itself must contain only t followed by digits; do not include brackets, Markdown, prefixes, or explanations."
}
```

No current chunk aliases are placed in an enum. The deterministic validator
still checks that a syntactically valid alias is an exact member of the current
projection/chunk mapping.

Gemini structured output supports `description` as a model-guiding schema
property but does not list string `pattern` in its supported subset. Therefore
the existing provider adapter projects the exact contract-owned description to
Gemini, while the canonical schema and validator retain the exact regex. This
is a provider projection inside the existing adapter, not a second grammar.

## Exact instruction fragment

The versioned instruction is
`broker-reports-bounded-semantic-labeling@1.0.1`. Its alias fragment is:

```text
В target_alias верни ровно bare alias: для [t123] значение поля равно t123.
Внутри значения разрешены только t и цифры; не добавляй скобки, Markdown,
префиксы или пояснения.
```

Human audit answer: the schema description and instruction cannot reasonably
be read as permission to return `[t123]`, `` `t123` ``, `target=t123`,
`alias: t123` or `<t123>`.

Provider capability reference, checked 2026-08-07:
[Google Gemini structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en).
