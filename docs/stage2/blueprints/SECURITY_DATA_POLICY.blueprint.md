# Security Data Policy Blueprint

## 1. Purpose

Сформировать Stage 2 policy for allowed data, provider boundaries and future masking.

## 2. PRD-1 requirements covered

- Зарубежные модели ограничиваются для персональных/финансовых/бухгалтерских данных.
- Отечественные модели могут использоваться шире, но не без правил.
- Нужна policy допустимых данных.
- Data masking/tokenization is not current implementation.
- Full tag substitution is future security/data-protection slice.

## 3. Current known context

PRD-0 warning banner exists but does not replace corporate data policy. PRD-1 says superficial masking creates false sense of security.

Provider setup must not start before data policy by provider class is approved.

## 4. Target user workflow

User sees scenario-specific data rules before sending documents, transcripts or search queries. Admin can explain which providers are allowed for which data class.

## 4.1. Provider and data classes

Policy draft must distinguish provider classes:

- foreign providers;
- Russian providers;
- local/self-hosted paths;
- future masked/tokenized path.

Policy draft must classify data:

- public/low-risk;
- internal working data;
- personal data;
- financial/accounting/tax data;
- broker reports;
- meeting transcripts;
- secrets/API keys/passwords.

Final allow/prohibit rules require customer approval. Until approved, provider setup remains blocked.

## 5. Native OpenWebUI first path

- Warning banners.
- Workspace instructions.
- Prompt templates with data rules.
- Group/model access restrictions.

## 6. Integration / custom implementation path

- Future data masking/tokenization subsystem.
- Local NER/local LLM/entity extraction.
- Secure mapping store and reverse substitution.
- Leak tests and audit logs.

## 7. Data and security notes

Do not treat find/replace as data protection. API keys stay server-side. Sensitive documents/transcripts need retention and visibility policy.

## 8. Dependencies

- Provider catalog.
- Workspaces/RBAC.
- Broker/docs/transcription domains.
- Manager visibility policy.

## 9. Risks and constraints

- False security from shallow anonymization.
- Accidental foreign provider use.
- Logs retaining sensitive content.
- Users bypassing policy in general chat.

## 10. Open questions

- Which data classes are allowed for each provider group?
- Is manual anonymization acceptable for Practical Stage 2?
- Who approves policy text?

## 11. Research links

- [DATA_MASKING_FUTURE_RESEARCH](../research/DATA_MASKING_FUTURE_RESEARCH.md)
- [PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH](../research/PROVIDERS_YANDEX_GIGACHAT_DEEPSEEK_CLAUDE_RESEARCH.md)

## 12. Acceptance signals

- Policy distinguishes foreign and Russian providers.
- Data masking is clearly future/deferred.
- Workspace instructions include allowed/prohibited data examples.
- Provider setup is blocked until customer-approved data policy by provider class exists.
- Broker, document, transcript and web-search scenarios have scenario-specific warnings.

## 13. Implementation readiness

Policy can be drafted now as ADR-0001. Provider setup waits for customer approval.
