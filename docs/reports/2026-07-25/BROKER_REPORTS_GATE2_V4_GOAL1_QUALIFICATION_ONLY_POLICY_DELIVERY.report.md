# Broker Reports — Gate 2 v4, Goal 1: qualification-only policy delivery

Дата: 2026-07-25
Статус: `COMPLETED`

## Результат

Policy `1.4.0` доставлена в stage через отдельный qualification-only Action.
Ни один production workload не начал использовать новые модели.

Acceptance Goal 1:

- `QUALIFICATION_POLICY_LIVE: EXACT`;
- `PRODUCTION_MODEL_ADMISSION: EMPTY`;
- `GATE1_VISUAL_BEHAVIOR_DELTA: ZERO`;
- `REPOSITORY_LIVE_PARITY_FOR_QUALIFICATION_SCOPE: EXACT`;
- `ROLLBACK: PROVEN`.

Это не production activation и не model qualification. Provider generation в
этом Goal не выполнялась.

## Git и delivery boundary

- accepted base `main`: `a42624b62628009a3a10e8b043404215553b19e3`;
- implementation и stage source revision:
  `e52375878f58b268fe910158e94db905bc7f5843`;
- branch:
  `codex/broker-reports-gate2-v4-goal1-qualification-policy-live`;
- PR: [#113](https://github.com/Kwentin3/corp-openweb-ui/pull/113);
- Goal 0 dependency: PR #112, merge
  `a42624b62628009a3a10e8b043404215553b19e3`.

PR создан отдельно от Goal 0. Следующий dependent Goal допускается только
после merge PR #113.

## Изменённые контракты

Добавлены:

- `broker_reports_gate2_economy_qualification_policy_v1`;
- `broker_reports_gate2_economy_qualification_authorization_v1`;
- `broker_reports_gate2_economy_qualification_action_delivery_v1`;
- factory boundary
  `Gate2EconomyQualificationPolicyFactory.create`;
- non-global Action
  `broker_reports_gate2_economy_qualification_action`;
- live harness preflight, который до provider call требует:
  - exact live Action hash;
  - exact qualification policy hash;
  - exact model ID;
  - exact provider profile;
  - exact workload;
  - provider route revision;
  - input/output contract revisions;
  - prompt revision;
  - adapter projection revision;
  - canonical validator revision.

Qualification authorization жёстко фиксирует:

- paid tools: `false`;
- fallback calls: `0`;
- repair attempts: `0`;
- alias acceptance: forbidden;
- production admission: forbidden.

## Контракты, явно оставленные без изменений

Не менялись:

- Financial Evidence Registry
  `broker_reports_gate2_financial_evidence_registry_v1`;
- four-disposition contract;
- deterministic financial materializer;
- `broker_reports_gate2_financial_context_v1`;
- independent financial checksum contract;
- canonical parsers и validators;
- model policy `1.4.0`,
  hash
  `e71bbb7c95774058bc2324343a2de2adef2f3307d8b30f8e92d8cbf514bd09c9`;
- workload policy `1.4.0`,
  hash
  `f1eb7daa08f10c125d21addb5ec03a5dfac42207cc39a4b3aa86224820fc3a7d`;
- workload qualification registry и его статусы;
- production admissions для всех четырёх workload;
- provider profiles и provider connections;
- managed Prompts;
- Gate 1 visual model IDs, valves и behavior;
- Gate 1, source и domain bundled Pipe content;
- legacy dual-read/new-schema single-write behavior;
- Knowledge/RAG/vectorization boundaries;
- Gate 3.

Старое composite-stage metadata gap из Goal 0 не исправлялось и не
используется как доказательство whole-stage parity. В этом Goal доказана
только exact qualification scope parity.

## Минимальная dependency closure

```text
model policy 1.4.0
        +
workload policy 1.4.0
        ↓
Gate2EconomyQualificationPolicyFactory
        ↓
closed-world qualification Action snapshot
        ↓
live readback + exact hash check
        ↓
factory-backed qualification authorization
        ↓
existing budget / adapter / canonical validator path
```

Новый Action:

- не импортирует workspace package;
- не импортирует OpenWebUI runtime modules;
- не вызывает HTTP/provider SDK;
- не является global;
- не меняет Pipe execution;
- публикует только safe policy snapshot.

Поэтому ни один из трёх maintained Pipe bundles не требовал регенерации или
release.

## Live identity

| Поле | Значение |
|---|---|
| Action ID | `broker_reports_gate2_economy_qualification_action` |
| Action type | `action` |
| Active / global | `true / false` |
| Repository/live content SHA-256 | `6310dcdeb5419a830779aa2395dd3b0e9e087619648c616da7bbe8b6e1c2ffb0` |
| Live meta SHA-256 | `65b755c6a7c23f9e78261c68d4c5e79b4e58468be994ccdf5b2630cbfa5d9f4d` |
| Qualification policy SHA-256 | `d6b33ce5bdfd5e75b6c6afb66efa47a79150144c522f8e2ea433a7a045c23395` |
| Action valves SHA-256 | `44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a` |
| Maintained Function+valve snapshot SHA-256 | `a19a142c0f046c520db12aa4e4fd4ba628704fc708ce9c128bc9fda93b4bc480` |
| Published models total | `41` |

До и после delivery совпали:

- maintained Function content/meta/valve projections;
- published model inventory;
- Gate 1 visual boundary.

## Exact model matrix live

Опубликованы все четыре exact ID:

- `models/gemini-3.1-flash-lite`;
- `models/gemini-3.5-flash-lite`;
- `gpt-5.4-nano-2026-03-17`;
- `claude-haiku-4-5-20251001`.

Model-specific reasoning controls:

| Exact model | Provider profile | Reasoning |
|---|---|---|
| Gemini 3.1 Flash-Lite | `google_gemini` | `minimal` |
| Gemini 3.5 Flash-Lite | `google_gemini` | `minimal` |
| GPT-5.4 Nano | `openai_gpt` | `disabled` |
| Claude Haiku 4.5 | `anthropic_claude` | `disabled` |

Для всех моделей paid tools запрещены.

## Qualification authorization proof

Без provider generation построены exact authorization identities:

| Exact model | Workload | Authorization SHA-256 |
|---|---|---|
| Gemini 3.1 Flash-Lite | `gate2_source` | `681de6b84a606c95642095dedbc32f4af68dd8b2e62f3fa2bb089ea60477f669` |
| Gemini 3.1 Flash-Lite | `gate2_domain` | `2beb99b92a218d58d9e517885b255a2ee56de2d58c381d6fcbe84cfc01845926` |
| Gemini 3.5 Flash-Lite | `gate2_source` | `38bf9f0a5e875076c395990a42d345c714faab89069f355bcad7f0b42db0810e` |
| Gemini 3.5 Flash-Lite | `gate2_domain` | `29784fe18037998f400dea46b477651788613cf380bc53b8f6aa9e449f5daee7` |
| Gemini 3.1 Flash-Lite | `gate2_financial_evidence` diagnostic | `5c723cf8b49cd6ea216f166361c1bc927e4cb921f009612ae194fb39b10cdc46` |
| Gemini 3.5 Flash-Lite | `gate2_financial_evidence` | `ff256b7362da6dabe7b51b020bbba5cc572a46236e42ecb01d7bd157b66a5402` |
| GPT-5.4 Nano | `gate2_financial_evidence` | `efde8a286bc93d62b1983793d3c4d4bc5948c649b2390b3075dd3365bff3e012` |
| Claude Haiku 4.5 | `gate2_financial_checksum` | `45d955c6ef0d4270cbb82b587bcadb6f7adf2faf55e1453fb5d25ccd507ce610` |

Эти authorization receipts не являются qualification receipts и ничего не
добавляют в production allowlist.

## Rollback

Начальное состояние Action: отсутствует.

Выполнена последовательность:

1. create candidate;
2. activate non-global candidate;
3. delete candidate и подтвердить возврат к отсутствию;
4. recreate candidate;
5. повторно подтвердить active/non-global exact state.

Результат:

- previous state restored: `true`;
- candidate state restored: `true`;
- previous absent-state identity:
  `222667f43f9523fc629245ed567d43490d97c8c68ac48af5bae6433827d01900`;
- stage mutations: `5`.

## Tests

Focused:

- `62 passed in 1.61s`.

Full service suite:

- `1377 passed`;
- `20 skipped`;
- `5` существующих SWIG deprecation warnings;
- runtime: `100.63s`.

Также прошли:

- Ruff check;
- Ruff format check;
- repository/live Action hash readback;
- four live exact-model preflight runs;
- four source/domain policy authorization builds.

## Calls, tokens, cost

- provider calls: `0`;
- customer calls: `0`;
- generated outputs: `0`;
- input tokens: `0`;
- output tokens: `0`;
- actual cost: `USD 0`;
- expensive model calls: `0`;
- fallback calls: `0`;
- repair attempts: `0`.

## Privacy

- customer corpus не использовался;
- customer values не читались;
- raw provider output отсутствует;
- secrets и bearer tokens в report/receipt не включаются;
- в Git входят только code, tests и safe evidence;
- Knowledge/RAG/vector writes: `0`;
- Gate 3 execution: `0`.

## Terminal reporting

- status: `COMPLETED`;
- exact implementation/stage revision:
  `e52375878f58b268fe910158e94db905bc7f5843`;
- branch:
  `codex/broker-reports-gate2-v4-goal1-qualification-policy-live`;
- PR: `#113`;
- contracts changed: qualification-only policy, authorization, Action delivery
  и live preflight boundary;
- contracts unchanged: frozen Gate 2 authorities, production routes, all three
  maintained Pipes, Prompts, provider connections и Gate 1 visual;
- provider/customer calls: `0 / 0`;
- exact model IDs: четыре разрешённых ID;
- tokens/cost: `0 / USD 0`;
- fallback/repair: `0 / 0`;
- focused/full tests: `62 passed / 1377 passed, 20 skipped`;
- privacy: `PASSED`;
- stage mutations: `5`;
- next permitted Goal after merge PR #113:
  v4 Goal 2, Gemini source qualification.
