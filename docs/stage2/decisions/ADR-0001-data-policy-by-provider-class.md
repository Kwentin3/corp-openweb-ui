# ADR-0001 Data Policy by Provider Class

Status: Proposed

## 1. Context

PRD-1 includes foreign providers, Russian providers, web-search, STT,
broker reports, documents and meeting transcripts. These workflows may process
personal, financial, accounting, tax and internal working data.

Full data masking/tokenization is not part of Practical Stage 2. It remains a
future security slice because reliable masking requires entity detection,
mapping storage, reverse substitution, leak tests and audit controls.

## 2. Problem

Provider setup must not start before data policy by provider class is approved.

Without a policy, each scenario will decide sensitive-data rules ad hoc. That
creates inconsistent rules for OpenAI, Claude, DeepSeek, Yandex, GigaChat, STT,
search and OCR providers.

## 3. Decision needed

Approve a Stage 2 data policy that defines:

- provider classes;
- data classes;
- allowed/prohibited matrix;
- scenario warnings;
- runtime and implementation impact.

This ADR is a draft. It does not approve final policy without customer approval.

## 4. Options

Option 1. Allow providers case by case.

- Lowest planning effort.
- High drift risk.
- Not recommended.

Option 2. Approve policy by provider class.

- Separates foreign providers, Russian providers, local/self-hosted paths and
  future masked/tokenized path.
- Gives one rule set for model catalog, STT, web-search and OCR.
- Recommended for Stage 2.

Option 3. Block all sensitive workflows until full masking exists.

- Strongest privacy posture.
- Blocks Practical Stage 2 value.
- Keep only if customer requires it.

Provider classes to decide:

- foreign providers;
- Russian providers;
- local/self-hosted paths;
- future masked/tokenized path.

Data classes to decide:

- public/low-risk;
- internal working data;
- personal data;
- financial/accounting/tax data;
- broker reports;
- meeting transcripts;
- secrets/API keys/passwords.

Draft matrix:

| Data class | Foreign | Russian | Local/self-hosted | Future masked |
| ---------- | ------- | ------- | ----------------- | ------------- |
| Public/low-risk | Allowed after approval | Allowed after approval | Allowed | Possible |
| Internal working data | Approval required | Approval required | Preferred | Possible later |
| Personal data | Prohibited by default | Legal approval required | Preferred | Future only |
| Financial/accounting/tax data | Prohibited by default | Legal approval required | Preferred | Future only |
| Broker reports | Prohibited by default | Legal approval required | Preferred | Future only |
| Meeting transcripts | Prohibited by default | Approval required | Preferred | Future only |
| Secrets/API keys/passwords | Prohibited | Prohibited | Prohibited in prompts | Prohibited |

## 5. Recommended option

Approve Option 2 as the interim Stage 2 policy path before provider setup.

Scenario warnings should cover:

- broker reports / 3-НДФЛ;
- documents/OCR;
- transcription;
- web-search;
- general chat and secrets.

## 6. Consequences

- Provider setup waits for approved policy.
- Provider model catalog must include allowed data classes.
- Workspace instructions and prompts must include warnings.
- Web-search, STT and OCR candidates depend on policy approval.
- Full masking/tokenization remains deferred.

## 7. Runtime proof needed

- Verify workspace warnings can be shown where users work.
- Verify model/provider access can be constrained by group/scenario.
- Verify no API keys or secrets are documented or exposed in repo.

## 8. Customer input needed

- Which data classes are allowed for foreign providers?
- Which data classes are allowed for Russian providers?
- Which scenarios must use only local/self-hosted paths?
- Can anonymized broker reports be used with external providers?
- Can OCR/VL OCR pilot samples be sent to foreign providers?
- Who approves final warning text?
- What is the retention policy for uploaded files and transcripts?

## 9. Acceptance signals

- Customer/security approves the interim policy.
- Provider catalog references data classes.
- Sensitive scenarios include warnings.
- Practical Stage 2 still excludes full automatic masking/tokenization.

## 10. Links

- [SECURITY_DATA_POLICY](../blueprints/SECURITY_DATA_POLICY.blueprint.md)
- [DATA_MASKING_FUTURE_RESEARCH](../research/DATA_MASKING_FUTURE_RESEARCH.md)
- [PROVIDERS_MODEL_CATALOG](../blueprints/PROVIDERS_MODEL_CATALOG.blueprint.md)
