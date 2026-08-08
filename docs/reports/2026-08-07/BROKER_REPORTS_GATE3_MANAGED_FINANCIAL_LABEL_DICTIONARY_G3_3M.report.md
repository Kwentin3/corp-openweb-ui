# Broker Reports GOAL G3.3M — Managed Financial Label Dictionary v1

Date: 2026-08-07

## GOAL_STATUS

```text
GOAL_G3_3M = COMPLETED
IMPLEMENTATION = INACTIVE
RUNTIME_ACTIVATION = false
PRODUCT_CUTOVER = false
PUBLISHED_VERSIONS = 1
PUBLISHED_V1_LABELS = 9
NEXT_ALLOWED_GOAL = G3.4_AFTER_REVIEW
```

G3.3M закрыт в заявленной границе. Создан один immutable, hash-pinned owner
значений финансовых labels и минимальный review lifecycle. LLM labeling,
annotation persistence, product route и G3.4 не начинались.

## WHAT_WAS_ACHIEVED

- Опубликована версия `broker-reports-financial-labels@1.0.0` ровно с девятью
  согласованными labels.
- Для каждого label зафиксированы meaning, positive boundary, negative
  boundary, examples и confusable cases.
- Реализован единый factory-routed surface: explicit load, full deterministic
  Markdown render, draft, validate, diff, review receipt и publish preparation.
- Published resource проверяется двумя pin: SHA-256 точных file bytes и
  semantic-integrity SHA-256.
- Новые prepared bytes не становятся loadable автоматически. Для активации
  версии требуется отдельное human-reviewed добавление package resource и
  обоих pins; существующая версия не перезаписывается.
- Старые результаты сохраняют точную привязку `dictionary_id` +
  `semantic_version` по существующему `FinancialAnnotationsV1` contract.

## WHAT_WAS_REUSED

- Девять решений `KEEP`, уточнённые определения и conflict boundaries из
  [G3.3V corpus validation](./BROKER_REPORTS_GATE3_NDFL_DICTIONARY_CORPUS_VALIDATION_G3_3V.report.md).
- Research provenance и downstream need map из
  [G3.3R](./BROKER_REPORTS_GATE3_NDFL_MINIMAL_DICTIONARY_G3_3R.report.md).
- Существующие Gate 3 DTO identities и binding rule из
  [Minimal Labeling v1](../../stage2/contracts/BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md).
- Репозиторный factory/authority и closed-world package-resource patterns.

Ранее выполненная работа не потеряна: G3.3R объясняет необходимость labels, а
G3.3V остаётся evidence происхождения финальных границ. Нормативные значения
при этом не скопированы в несколько runtime surfaces.

## WHAT_WAS_ADDED

- Нормативный immutable resource:
  [`gate3_financial_label_dictionary.v1.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.v1.json).
- Единственный lifecycle/loader/renderer owner:
  [`gate3_financial_label_dictionary.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary.py).
- Package-local review CLI:
  [`gate3_financial_label_dictionary_cli.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate3_financial_label_dictionary_cli.py).
- Нормативный lifecycle contract:
  [Financial Label Dictionary v1](../../stage2/contracts/BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.md).
- Exact generated LLM view:
  [model.generated.md](../../stage2/research/BROKER_REPORTS_GATE3_FINANCIAL_LABEL_DICTIONARY.v1.model.generated.md).
- Behavioral, closed-world, immutability and anti-drift tests plus CI inclusion.

## WHAT_WAS_NOT_NEEDED

- Новые schema, registry, manifest, database или publisher service.
- RAG, Knowledge ingestion, partial/lazy dictionary retrieval или embeddings.
- Prompt, Skill, Tool, provider adapter, retry/repair или model call.
- ArtifactStore type, annotation writer, workflow, GUI или product route.
- Повторное использование широкого historical Gate 2 Financial Semantic Pack
  как Gate 3 meaning owner.
- Новые labels, включая все deferred candidates.

## ACCEPTANCE_EVIDENCE

| Acceptance point | Evidence | Result |
| --- | --- | --- |
| один нормативный owner | JSON resource загружается только через `Gate3FinancialLabelDictionaryFactory.create`; architecture guards запрещают duplicate/path bypass | `PASS` |
| ровно девять labels | exact ordered-ID assertion; dropped/deferred IDs disjoint | `9/9 PASS` |
| immutable published v1 | file SHA-256 и semantic-integrity pin проверяются при каждом load; tampered package copy fails closed | `PASS` |
| explicit version load | доступна только pinned `1.0.0`; `1.1.0` без reviewed pin возвращает `gate3_dictionary_version_not_published` | `PASS` |
| deterministic full Markdown | два render имеют одинаковый SHA-256 и byte parity с generated view | `PASS` |
| draft/diff/validate | полный draft `1.1.0` валиден; exact unified diff воспроизводим | `PASS` |
| human approval boundary | `PENDING` отклоняется; receipt обязан совпасть с exact `draft_sha256`; текущий v1 содержит supplied-goal approval | `PASS` |
| non-overwrite publish preparation | CLI использует exclusive create; повторная запись завершается terminal error | `PASS` |
| closed-world package | isolated copy package загружает resource без workspace-only import/path hack | `PASS` |
| no activation | отсутствуют provider, annotation persistence и product consumer; prepared version не попадает в published pin set | `PASS` |

Focused lifecycle suite:

```text
python -B -m pytest -q tests/test_broker_reports_gate3_financial_label_dictionary.py
9 passed in 6.41s
```

Relevant contract and architecture suite:

```text
python -B -m pytest -q \
  tests/test_broker_reports_gate3_financial_label_dictionary.py \
  tests/test_broker_reports_gate3_minimal_labeling_contract.py \
  tests/test_broker_reports_gate3_projection.py \
  tests/test_broker_reports_gate_architecture.py \
  tests/test_broker_reports_kt1_architecture_stabilization.py
71 passed, 1 warning in 45.67s
```

Warning attribution: существующий `DeprecationWarning` для escape sequence в
`scripts/local_pdf_dual_vlm_canonical_table_report.py`; G3.3M его не меняет.

Privacy/repository guard:

```text
python -B -m pytest -q \
  tests/test_repository_privacy_guard.py \
  tests/test_broker_reports_doc34_repository_contract.py \
  tests/test_broker_reports_gate3_financial_label_dictionary.py
19 passed in 9.12s
```

Full service suite не объявлен зелёным: неизменённый `python -B -m pytest -q`
дважды не дал terminal test result и был остановлен оболочкой с `exit 124` —
сначала после `124s`, затем после `604s`. Assertion output отсутствовал. Это
runner timeout, а не доказанный assertion failure или PASS.

Final combined bounded gate после всех doc/status edits:

```text
81 passed, 1 warning in 48.65s
```

## RAW_EVIDENCE

Published v1:

```json
{
  "dictionary_id": "broker-reports-financial-labels",
  "semantic_version": "1.0.0",
  "status": "PUBLISHED",
  "labels_total": 9,
  "file_sha256": "83d97cb2f0abe9c1cbe848012f7f681ef231247e620edfc6cb4e9d5085e490a6",
  "integrity_sha256": "c48e53219dd007fe842779760f6ad1e1c3e868192719d2450c8e00afd1221154"
}
```

Deterministic render:

```text
render_a_sha256 = 7c9074207c170425125eabe04891cecf4cbd03815f7cefac1bf42c0a9c2f6be3
render_b_sha256 = 7c9074207c170425125eabe04891cecf4cbd03815f7cefac1bf42c0a9c2f6be3
generated_view_sha256_without_bom = 7c9074207c170425125eabe04891cecf4cbd03815f7cefac1bf42c0a9c2f6be3
generated_view_file_sha256_with_utf8_bom = 3bd0c34f1ead3d2d90630f82e1a563958386054166a0c93ce8184644d5c3d106
```

Draft example (proposal only, never activated):

```json
{
  "proposal_id": "g3.3m-evidence-interest-example",
  "base_version": "1.0.0",
  "proposed_version": "1.1.0",
  "change": "append INTEREST_INCOME example: Cash interest credited",
  "valid": true,
  "labels_total": 9,
  "draft_sha256": "f231d8d9b79dd3cd711b40fbde700a5e894ec5c2177247adfa3c5a53b65fb5d1",
  "conflicts": []
}
```

Exact deterministic diff:

```diff
--- published-1.0.0
+++ draft-1.1.0
@@ -88,7 +88,8 @@
     ],
     "examples": [
       "Проценты по займам \"овернайт\"",
-      "Interest Credit"
+      "Interest Credit",
+      "Cash interest credited"
     ],
     "confusable_with": [
       "Дебетовый процент",
```

Human-approved current publication:

```json
{
  "approval_id": "g3.3m-explicit-goal-approval-2026-08-07",
  "decision": "APPROVED",
  "approved_by_role": "goal_setters",
  "approved_at": "2026-08-07",
  "basis": "G3.3M contract fixes the nine G3.3V-validated labels"
}
```

Fail-closed evidence:

```text
pending_publish=gate3_dictionary_human_approval_required
unreviewed_version_load=gate3_dictionary_version_not_published
caller_mutation_isolated=true
tampered_resource=gate3_dictionary_published_file_hash_mismatch
```

The illustrative draft/diff above is not a financial decision and was not
committed as a published successor. Its purpose is to prove the lifecycle
without silently creating version `1.1.0`.

## KNOWN_LIMITATIONS

- The dictionary is not a tax engine and makes no NDFL conclusion.
- `INTEREST_INCOME` and `SECURITIES_LENDING_INCOME` retain the `MEDIUM`
  evidence limitation documented by G3.3V.
- Five visual-only corpus sources remained unclassified in G3.3V; G3.3M does
  not manufacture evidence for them.
- Mechanical conflict checks cannot replace human financial review.
- No annotation output exists yet, so exact old-result version binding is
  contractually prepared but has no G3.4/G3.5 runtime instance to demonstrate.
- Full service suite has no terminal verdict in this run because of the two
  separately attributed runner timeouts. Focused, architecture and privacy
  suites do have terminal PASS results.

## OBSERVATIONS

- The nine-label set is smaller and sharper than the original ten-label draft:
  `BROKER_SERVICE_CHARGE` remains dropped because clean positive evidence was
  absent and custody/transaction meanings would be conflated.
- Complete dictionary injection is small enough that RAG or lazy loading would
  add failure modes without a demonstrated benefit.
- A reviewed resource plus explicit code pin is sufficient for v1. A registry,
  manifest or publishing service would duplicate authority at this scale.

## KISS_CHECK

```text
MEANING_OWNERS = 1
PUBLISHED_RESOURCES = 1
PUBLISHED_LABELS = 9
FACTORIES = 1
DATABASES = 0
REGISTRIES = 0
MANIFESTS = 0
PUBLISHER_SERVICES = 0
RAG_PATHS = 0
PROVIDER_CALLS = 0
ANNOTATION_WRITERS = 0
PRODUCT_ROUTES = 0
```

The only intentional duplicate representation is the exact generated Markdown
review view. Byte-parity testing keeps it derived and non-authoritative.

## NEXT_ALLOWED_GOAL

```text
G3.4 — only after explicit review and authorization
```

Work stops here. G3.4, provider execution, annotation persistence and product
activation were not started.
