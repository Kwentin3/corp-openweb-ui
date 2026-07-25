# Broker Reports — Gate 2 ambiguity discipline, Goal 5

Дата: 2026-07-25

Статус: `PROMPT_V2_TYPING_BIAS: PROVEN_FOR_EXACT_RECEIPT_PAIR`

## Controlled comparison

Attempt 1 и Attempt 2 имели одинаковые:

- exact model/provider route;
- fixture;
- deterministic scopes;
- model-input hashes;
- Registry;
- canonical/provider schemas;
- validator/materializer/comparator;
- reasoning/budget/fallback policy.

Различались только:

- prompt contract ID;
- prompt content/hash.

Новых diagnostic calls для статистической репликации не выполнялось.

## Prompt v1

Key behavior:

- выбрать только eligible Registry type;
- `unclassified_financial_input` при невозможности safe typing;
- сохранить каждый package value;
- не создавать system/audit metadata.

Observed:

- typed: 6;
- unclassified: 4;
- no-financial: 0;
- unsupported: 1;
- passed: 7/11.

Оба disputed ambiguity cases были правильно unclassified.

Weaknesses:

- no explicit disposition ordering;
- insufficient distinction cash vs printed metric;
- headers/no-financial boundary weak;
- association/equal-value rules absent.

## Prompt v2

Added:

- explicit four-disposition rules;
- cash requires explicit ordinary-cash label;
- printed metric requires explicit source-printed total/metric label;
- equal literals require contextual association;
- headers/layout → no-financial;
- unclassified only for actual financial values not safely typed.

Observed:

- typed: 9;
- unclassified: 0;
- no-financial: 1;
- unsupported: 1;
- passed: 9/11.

Prompt v2 исправил:

- detail vs subtotal;
- repeated header;
- missing optional dimensions;
- adjacent equal values.

Но два ранее правильных unclassified outcomes стали typed cash.

## Exact bias finding

Phrase:

> Use typed_input only when one eligible definition and every required role
> are explicit.

не является machine constraint. При двух eligible types она может читаться
как «выбери одну подходящую definition», а не «typed разрешён только при
единственном доказанном type».

Дополнительно strict schema предлагает branches в порядке:

1. cash typed;
2. printed typed;
3. unclassified;
4. no-financial;
5. unsupported.

В обоих disputed v2 cases выбран первый cash branch.

Schema order сам по себе не достаточен как causal explanation: prompt v1 с тем
же order выбрал unclassified. Но v2 сделал type-specific matching более
салient, тогда как schema не кодировала semantic preconditions. Это создало
измеримый branch shift:

- unclassified 4 → 0;
- typed 6 → 9.

В `explicit_unclassified` модель даже оставила `source_label=null`, то есть
prompt condition про explicit cash label не была выполнена, но schema/validator
приняли decision.

Для exact paired receipts prompt-v2 typing bias доказан. Без повторных вызовов
не утверждается универсальная статистическая частота для модели.

## Prompt/schema conflict

Prompt требует:

- semantic cash/printed evidence;
- safe typing;
- unclassified при отсутствии safe match.

Schema требует только:

- role/value-type-compatible refs;
- eligible type ID;
- bounded reason code.

Следовательно, prompt запрещает решения, которые schema делает representable.
Canonical validator корректно следует schema, а не prose.

Safety существует только в prompt — это неприемлемо.

## Bounded responsibility allocation

### Prompt owns

- concise decision semantics;
- prohibition inference/invention;
- use only supplied source context/refs;
- choose unclassified when admitted types still semantically unresolved.

### Registry owns

- normative type meaning;
- examples/counterexamples;
- stable type IDs.

### Deterministic typed-admission policy owns

- positive discriminator proof;
- conflict/ambiguity detection;
- admitted type IDs;
- removal of unsafe typed branches.

### Provider schema owns

- exact package-specific representability;
- typed variants only for admitted IDs;
- unclassified/no-financial/unsupported always available when applicable.

### Canonical validator owns

- admission identity/hash recheck;
- eligible type/ref/role enforcement;
- no post-response conversion.

## Prompt v3 decision

Prompt-only tweak запрещён.

После code-owned admission и context v2 нужен новый concise prompt identity,
который:

- не перечисляет fixture-specific cases;
- не является единственной safety boundary;
- объясняет, что наличие typed branch означает pre-admitted candidate, но
  semantic evidence всё равно должно поддерживать type;
- сохраняет unclassified как нормальный terminal outcome.

Prompt v3 и provider call относятся к отдельному implementation/qualification
GOAL.

## Acceptance

- `PROMPT_V2_TYPING_BIAS: PROVEN_FOR_EXACT_RECEIPT_PAIR`
- `PROMPT_RESPONSIBILITY: BOUNDED`
- `PROMPT_SCHEMA_CONFLICT: PROVEN`
- `SAFETY_ONLY_IN_PROMPT: FORBIDDEN`

No production/runtime code changed. Provider/customer calls: 0.
Следующий шаг: Goal 6 benchmark expectation audit.
