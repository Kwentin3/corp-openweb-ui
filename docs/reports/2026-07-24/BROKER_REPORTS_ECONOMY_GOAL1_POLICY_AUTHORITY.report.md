# Broker Reports — Economy Goal 1: policy authority

Дата: 2026-07-24

Терминальный статус: `COMPLETED`.

## Результат

Создана pure, deterministic и code-owned policy `broker_reports_economy_model_policy_v1`.

Policy является единственным новым authority для:

- exact economy model IDs;
- alias → exact ID resolution;
- provider/model family;
- cost class и token pricing identity;
- supported modality и structured-output mode;
- workload classes;
- cheapest-first preference order;
- input/output token caps;
- reasoning и paid-tools policy;
- maximum default/fallback/full-scope calls;
- lifecycle и qualification receipt identity;
- runtime allowlist generation и narrowing.

Policy пока не подключена к production runtime: это отдельный Goal 4. До принятой Goal 3 qualification все candidates fail-closed и qualified runtime allowlist пуст.

## Candidate catalog

| Preference | Provider | Exact model ID | Family | Stage evidence | Qualification state |
| ---: | --- | --- | --- | --- | --- |
| 0 | OpenAI | `gpt-5-nano-2025-08-07` | Nano | unavailable | `unavailable` |
| 1 | OpenAI | `gpt-5.4-nano-2026-03-17` | Nano | unavailable | `unavailable` |
| 2 | Gemini | `models/gemini-3.1-flash-lite` | Flash-Lite | available | `qualification_required` |
| 3 | Gemini | `models/gemini-3.5-flash-lite` | Flash-Lite | available | `qualification_required` |
| 4 | Anthropic | `claude-haiku-4-5-20251001` | Haiku | maintained connection enabled | `qualification_required` |

Aliases разрешаются в pinned exact IDs и отражаются отдельным `alias_used` в resolution. Alias не попадает в runtime receipt как resolved identity.

## Fail-closed invariants

- unknown model ID отклоняется;
- Sol, Luna, Mini, regular Flash, Pro, Sonnet и Opus отсутствуют в declarations;
- non-economy family не проходит policy validation;
- unqualified candidate не попадает в runtime allowlist;
- active model без `qualified` status и SHA-256 qualification receipt невозможен;
- runtime/config override может только сузить qualified allowlist;
- попытка расширить allowlist завершается `economy_runtime_allowlist_expansion_forbidden`;
- paid tools запрещены;
- reasoning разрешён только `disabled` или `minimal`;
- default provider calls per operation равны одному;
- fallback calls ограничены одним;
- response body policy — только `strict_contract_json_only`.

## Workload contracts

Policy определяет отдельные budgets для:

- `gate2_source`;
- `gate2_domain`;
- `gate2_financial_evidence`;
- `gate2_financial_checksum`.

Числовое enforcement и safe cost receipts реализуются в Goal 2. Goal 1 фиксирует immutable policy inputs и запрещает runtime расширять их.

## Verification

- policy hash: `d9207ca5e2e2e4b78f62d3c834f663cd945c4925cf4b16312d2292fc27c8006f`;
- model declarations: `5`;
- qualified model IDs до Goal 3: `0`;
- focused tests: `50 passed`;
- new-file Ruff: `passed`;
- compile check: `passed`;
- `FACTORY_REQUIRED` / `FORBIDDEN` anchors: присутствуют и test-covered;
- provider calls: `0`;
- Gate 1 change: `0`;
- Registry/decision/materializer/context change: `0`;
- Knowledge/RAG/vector change: `0`.

Standalone `pytest.exe` дважды остановился на collection из-за отсутствующего service root в import path. Тесты исполнялись однозначно через `python -m pytest` из `services/broker-reports-gate1-proof`; assertion failures отсутствовали.

## Acceptance

- `ECONOMY_POLICY`: `VERSIONED_AND_CODE_OWNED`;
- `EXPENSIVE_MODEL_POLICY_SELECTION`: `IMPOSSIBLE`;
- `WORKLOAD_OVERRIDE_ESCALATION`: `IMPOSSIBLE`;
- `EXACT_RESOLVED_MODEL`: `RECORDED_BY_CONTRACT`;
- runtime integration: `DEFERRED_TO_GOAL_4`;
- live release: `NOT_PERFORMED`.
