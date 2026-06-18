# Data Masking Future Research

## 1. Question

What would a real data masking/tokenization subsystem require after Practical Stage 2?

## 2. Why it matters for PRD-1

Customer suggested data replacement with tags, but PRD-1 explicitly keeps full masking as future security slice.

## 3. Current assumptions

- Not included in Practical Stage 2 implementation.
- Simple find/replace creates false security.
- Real solution needs local processing and trust boundary.

## 4. What to verify

- Entity types: names, accounts, INN, passports, addresses, amounts, contracts, companies.
- Local NER/local LLM options.
- Mapping store design.
- Reverse substitution.
- Leak tests.
- Audit/logging.

## 5. Sources to check

- Security policy.
- Customer data examples.
- Future NER/local inference options.

## 6. Test plan / proof plan

Design future proof with sensitive sample corpus, expected entities, anonymized output, reverse substitution and leak checks.

## 7. Risks

- Missed sensitive data.
- Incorrect reverse mapping.
- Mapping store compromise.
- Users assume all data is safe.

## 8. Decision options

- Manual anonymization only.
- Local NER helper.
- Local LLM/NER subsystem.
- Full tokenization service with mapping store.

## 9. Recommended next step

Keep out of Practical Stage 2; document future architecture only after customer approval.

## 10. Status

Deferred / future slice.
