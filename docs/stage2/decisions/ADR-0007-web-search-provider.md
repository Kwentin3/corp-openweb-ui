# ADR-0007 Web-search Provider

Status: Proposed

## 1. Context

PRD-1 requires web-search for all users, but with rules, limits, result count,
concurrency and cost visibility.

Brave is the first-pilot candidate if foreign provider use is allowed. Yandex
Search is the Russian-provider candidate. Yandex Search must not be confused
with YandexGPT or GigaChat.

## 2. Problem

Web-search can become a hidden privacy and cost channel if users send sensitive
queries to external search providers without limits or warnings.

## 3. Decision needed

Approve provider choice, usage rules, limits and smoke checks before setup.

## 4. Options

Option 1. Brave Search pilot.

- Strong first candidate.
- Foreign-provider/data-policy approval required.

Option 2. Yandex Search pilot.

- Russian-provider candidate.
- Needs adapter/native capability check and cost approval.

Option 3. Defer web-search.

- Avoids privacy/cost risk.
- Misses a PRD-1 priority.

## 5. Recommended option

Choose Brave or Yandex Search after ADR-0001 data policy and customer
cost/privacy approval.

The decision must define:

- web-search for all users but with rules;
- result count;
- concurrency;
- cost visibility;
- prohibited query examples;
- Yandex Search vs YandexGPT/GigaChat distinction.

## 6. Consequences

- Web-search setup waits for provider approval.
- Sensitive data examples must be prohibited in user instructions.
- Usage/cost visibility must be checked in runtime.
- Provider-specific limits and query examples become acceptance inputs.

## 7. Runtime proof needed

- Russian smoke queries.
- English smoke queries.
- Result count/concurrency settings.
- Cost visibility path.
- Group/feature access proof if applicable.

## 8. Customer input needed

- Provider preference: Brave, Yandex Search or defer.
- Allowed/prohibited query examples.
- Result count/concurrency expectations.
- Cost limit expectations.
- Provider account/key path.

## 9. Acceptance signals

- Provider selected.
- Rules and limits documented.
- Smoke queries pass.
- Prohibited-query examples are included in instructions.
- Cost visibility is documented or gap is recorded.

## 10. Links

- [WEB_SEARCH](../blueprints/WEB_SEARCH.blueprint.md)
- [WEB_SEARCH_PROVIDERS_RESEARCH](../research/WEB_SEARCH_PROVIDERS_RESEARCH.md)
- [USAGE_ANALYTICS_BILLING_RESEARCH](../research/USAGE_ANALYTICS_BILLING_RESEARCH.md)
- [ADR-0001 Data Policy](ADR-0001-data-policy-by-provider-class.md)
