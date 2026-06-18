# ADR-0001 Data Policy by Provider Class

Status: Proposed
Date: 2026-06-18
Domain: Security / data policy / providers

## 1. Context

PRD-1 includes foreign providers, Russian providers, web-search, STT, broker reports, documents and meeting transcripts. These workflows may process personal, financial, accounting, tax and internal working data.

Full data masking/tokenization is not part of Practical Stage 2. It remains a future security slice because reliable masking requires entity detection, mapping storage, reverse substitution, leak tests and audit controls.

## 2. Problem

Provider setup must not start before data policy by provider class is approved.

Without a policy, each scenario will decide sensitive-data rules ad hoc. That creates inconsistent rules for OpenAI/Claude/DeepSeek/Yandex/GigaChat/STT/search/OCR providers and increases leakage risk.

## 3. Decision Needed

Approve a Stage 2 data policy that defines:

- provider classes;
- data classes;
- allowed/prohibited matrix;
- scenario warnings;
- runtime and implementation impact.

This ADR is a draft. It does not approve final policy without customer approval.

## 4. Provider Classes

- Foreign providers.
- Russian providers.
- Local/self-hosted paths.
- Future masked/tokenized path.

## 5. Data Classes

- Public/low-risk.
- Internal working data.
- Personal data.
- Financial/accounting/tax data.
- Broker reports.
- Meeting transcripts.
- Secrets/API keys/passwords.

## 6. Allowed / Prohibited Matrix Draft

| Data class | Foreign providers | Russian providers | Local/self-hosted paths | Future masked/tokenized path |
| ---------- | ----------------- | ----------------- | ----------------------- | ---------------------------- |
| Public/low-risk | Allowed after provider approval | Allowed after provider approval | Allowed | Allowed after masking design |
| Internal working data | Customer approval required | Customer approval required | Preferred | Possible later |
| Personal data | Prohibited by default | Customer/legal approval required | Preferred | Future only |
| Financial/accounting/tax data | Prohibited by default | Customer/legal approval required | Preferred | Future only |
| Broker reports | Prohibited by default unless anonymized and approved | Customer/legal approval required | Preferred | Future only |
| Meeting transcripts | Prohibited by default for sensitive meetings | Customer approval required | Preferred | Future only |
| Secrets/API keys/passwords | Prohibited | Prohibited | Prohibited in prompts/files | Prohibited |

## 7. Warnings Required in Working Scenarios

- Broker reports / 3-НДФЛ: result is draft analysis and requires human review.
- Documents/OCR: extracted content may be incomplete; scans/tables need pilot classification.
- Transcription: transcripts may contain personal or commercial data; retention and visibility must be known.
- Web-search: do not put sensitive personal/financial/accounting data into search queries.
- General chat: do not send secrets, passwords, API keys or production credentials.

## 8. Non-goals

- No automatic masking in Practical Stage 2.
- No guarantee of anonymization.
- No local LLM masking subsystem yet.
- No provider setup approval by this draft alone.

## 9. Open Questions for Customer

- Which data classes are allowed for foreign providers?
- Which data classes are allowed for Russian providers?
- Which scenarios must use only local/self-hosted paths?
- Can anonymized broker reports be used with external providers?
- Can OCR/VL OCR pilot samples be sent to foreign providers?
- Who approves final warning text?
- What is the retention policy for uploaded files and transcripts?

## 10. Runtime / Implementation Impact

- Provider setup waits for approved policy.
- Provider model catalog must include allowed data classes.
- Workspace instructions and prompts must include warnings.
- Web-search, STT and OCR candidates depend on policy approval.
- Full masking/tokenization remains deferred.

## 11. Status

Proposed. Needs customer/security approval before provider setup.
