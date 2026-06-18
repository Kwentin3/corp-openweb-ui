# Data Masking Future Research

## 1. Question

Should Stage 2 implement data masking/tokenization now, or keep it as a future security slice?

## 2. Research status

Status: researched from OpenWebUI, LiteLLM and Microsoft Presidio docs on 2026-06-18.

Result type: future-slice boundary. No masking code was implemented.

## 3. Findings

- OpenWebUI filter functions can be used for PII scrubbing, input/output logging, cost tracking,
  rate limiting and policy enforcement patterns.
- Microsoft Presidio provides detection and anonymization/de-anonymization modules for PII.
  Operators include masking, redaction and encryption-style transformations.
- LiteLLM documents a Presidio-based PII/PHI masking guardrail with modes such as pre-call,
  post-call/logging and actions such as mask/block.
- These tools are useful building blocks, but they do not remove the need for a data policy,
  locale-specific recognizers, mapping storage, reversibility decisions and leak tests.

## 4. Why not Practical Stage 2 implementation

Data masking looks simple only if it is treated as string replacement. A usable corporate design
must answer:

- which entities are detected for Russian financial/legal documents;
- whether masked values must be reversible for final user output;
- where mapping tables are stored and encrypted;
- how false positives/false negatives are reviewed;
- whether masking happens before provider call, after provider call, in logs, or all of these;
- how prompt injection and file attachments are handled;
- how to prove that secrets/PII do not leak to foreign providers.

That scope is larger than the current practical Stage 2 and should not be smuggled into provider
setup.

## 5. Recommended Stage 2 policy

- Document allowed/prohibited data by provider class: foreign providers, Russian providers,
  local/self-hosted paths.
- For broker/tax examples, use anonymized test documents where possible.
- Do not promise automatic anonymization in customer-facing wording.
- Keep masking/tokenization as future security ADR after practical workflows are accepted.
- Do not start provider setup until data policy by provider class is approved.
- Apply the policy to broker reports, documents, meeting transcripts, web-search queries and model
  catalog access.

Provider setup implication:

- foreign providers, Russian providers, local/self-hosted paths and future masked/tokenized path
  must be separated in policy;
- public/low-risk, internal working data, personal data, financial/accounting/tax data, broker
  reports, meeting transcripts and secrets/API keys/passwords must be separated in policy;
- final allow/prohibit matrix requires customer approval.

## 6. Future architecture options

| Option | Use case | Notes |
| ------ | -------- | ----- |
| OpenWebUI filter function | Lightweight prompt/file text guard | Must be tested against OpenWebUI update surface. |
| LiteLLM Presidio guardrail | Gateway-based masking and provider routing | Requires gateway architecture and policy ownership. |
| Dedicated masking service | Strongest separation and mapping control | Highest complexity; suitable only if sensitive workflows scale. |

## 7. Sources

- https://docs.openwebui.com/features/extensibility/plugin/functions/filter/
- https://microsoft.github.io/presidio/
- https://microsoft.github.io/presidio/anonymizer/
- https://github.com/microsoft/presidio
- https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2

## 8. Status

Research complete. Keep as future slice, not Practical Stage 2 implementation.
