# Broker Reports CSV pre-Gate-3 context v1

Status: implemented and stage-proven

CSV profile: `broker_reports_csv_supported_profile_v1`

Gate 3 root: `broker_reports_gate3_context_manifest_v0`

## Назначение

Это первый поддержанный сквозной формат Broker Reports до границы Gate 3:

```text
private process=false CSV intake
  -> complete deterministic CSV normalization
  -> normalized source payload / source unit / table projection
  -> deterministic bounded segmentation
  -> Gate 2 candidate binding and strict validation
  -> deterministic stitch and coverage
  -> broker_reports_gate3_context_manifest_v0
```

Контракт не реализует ledger, междокументную сверку, расчёт налога,
декларацию или XLS/XLSX. Gate 3 обязан принимать manifest как единственный
корневой вход и разрешать private facts только через ArtifactResolver.

## 1. Поддерживаемый CSV profile v1

| Свойство | Правило |
| --- | --- |
| Максимальный размер входа | `5,000,000` bytes |
| Кодировки | UTF-8 BOM, UTF-8, CP1251 |
| Разделители | comma, semicolon, tab, pipe |
| Определение разделителя | `csv.Sniffer` в разрешённом наборе; затем детерминированный scoring; равный результат блокируется как ambiguous |
| Quoting | double quote, doubled quote, без backslash escape, strict parser |
| Header | первая logical record; минимум 2 непустых уникальных trimmed cell |
| Data | минимум одна непустая data row |
| Пустые строки | сохраняются и учитываются |
| Неравные records | сохраняются буквально; padding и truncation запрещены |
| Максимум logical rows | `10,000`, включая header и пустые rows |
| Максимум cells | `100,000` |
| Максимум columns в record | `256` |
| Максимум символов в cell | `32,000` |
| Максимальный materialized JSON | `20,000,000` bytes |
| NUL | запрещён |
| Нормализационный scope | весь CSV logical document |

Один и тот же `CsvSupportedProfileFactory.create()` используется техническим
профилером и full-source builder. Отдельная permissive parsing ветка запрещена.

Malformed, unsupported, ambiguous и over-budget CSV получают точный reason
code и не создают extraction-grade source unit. Latin-1 fallback, silent repair
и first-N truncation запрещены.

## 2. Полнота нормализации и bounded Gate 2 scope

Принятый CSV полностью материализуется как один
`private_normalized_source_payload_v0`, один complete
`private_normalized_source_unit_v0` и один
`broker_reports_normalized_table_projection_v0`.

Parent unit обязан иметь:

- `source_slice_truncated=false`;
- `parent_remainder_status=not_applicable_parent_complete`;
- полный ordered inventory source refs;
- одинаковые source/payload checksum refs у derived units;
- exact partition всех parent refs по deterministic segments.

Gate 2 v1 работает с явно объявленным bounded segment, а не заявляет весь CSV
прочитанным VLM. Segmentation plan перечисляет выбранные и deferred segments.
Deferred segments находятся вне declared Gate 3 scope и видны в manifest.

Для ready scope нужны одновременно:

- хотя бы один validator-accepted typed source fact;
- ровно одна model attempt на package;
- zero repair, fallback и provider failure;
- strict JSON Schema и точные provider/model/adapter/prompt/schema identities;
- zero rejected packages, uncovered refs, conflicts и unknown refs;
- exact equality selected refs и terminal ownership refs;
- complete stitch;
- valid issue context, включая явный пустой набор.

Candidate binding разрешён как нативный Gate 2 path. VLM выбирает только
детерминированные candidate ids и semantic roles. Candidate set, relation set,
binding validation, raw output, canonical facts, validation и stitch должны
быть сохранены и включены в проверяемый manifest graph.

## 3. Авторитетный Gate 3 root

`broker_reports_gate3_context_manifest_v0` — safe-internal checked index, не
копия customer data. Production factory:
`Gate3ContextManifestFactory.create()`.

Manifest содержит:

- declared bounded CSV scope и profile id;
- included document, normalized payload/unit/table и selected segment refs;
- explicit deferred documents, units и segments;
- DCP, technical profile и issue-ledger refs;
- terminal Gate 2 run и summary refs;
- route, domain package, candidate binding, raw output, validation, source
  facts, domain wrapper и stitch refs;
- safe counts, provider/schema identities и zero-loss hashes;
- access fingerprint, retention horizon и downstream restrictions;
- детерминированный `gate3_input_status=ready|blocked` и reason codes.

Manifest не содержит rows, cells, raw output, source values, filenames,
private paths или customer identifiers. Все private descendants остаются
`private_case` в `project_artifact_payload`.

`gate3_input_status` пересчитывается кодом из фактического persisted graph.
Унаследованный `gate3_handoff_ready` не является authority.

Gate 3 запрещено использовать как root:

- chat message;
- raw CSV;
- table projection;
- extraction run;
- DCP без terminal Gate 2;
- readiness boolean.

## 4. Access, retention и privacy

Manifest хранится как `safe_internal` в `project_artifact_store`. Разрешение
manifest и всех descendants требует того же user, normalization run,
case/chat и workspace model context, а также
`allow_private=true` и `require_source_available=true`.

Wrong user/case/workspace, expiry, purge и source deletion fail closed.
Manifest и descendants обязаны иметь один retention mode и один `expires_at`.

Customer CSV не загружается в OpenWebUI Knowledge, RAG или vectors. Chat и
operator report могут показывать только counts, statuses, reason codes и opaque
refs.

## 5. Stage acceptance 2026-07-17

Fresh customer-approved representative CSV прошёл:

- `process=false` private intake;
- complete whole-CSV normalization и table projection;
- deterministic one-ref high-confidence bounded segment;
- Gemini `models/gemini-3.5-flash` candidate-binding extraction;
- 1 typed `document_summary_evidence` fact;
- 0 rejected, uncovered, conflict, unknown, repair, fallback и provider
  failure;
- manifest `ready`;
- same-context manifest/private-fact resolution;
- wrong user/case/workspace denial;
- active coherent customer retention;
- `artifact_expired` и `artifact_purged` на изолированном equivalent graph;
- zero Knowledge/RAG/vector use.

В этом proof 343 невыбранных segments явно deferred вне declared scope. Это не
whole-document Gate 2 claim.

Live capability observation: full domain schemas и некоторые declared models
могут быть отвергнуты provider connection. Такие runs сохраняются как blocked.
Product proof использует отдельно выбранный approved Gemini 3.5 transport; это
не hidden failover внутри run.

## 6. Ограничения

- Поддержка не распространяется на произвольные или unlimited CSV.
- HTML, TXT, XLS/XLSX, PDF, DOCX, ZIP, images и legacy XLS не закрыты этим
  контрактом.
- Ready bounded scope не означает, что все deferred CSV segments прошли Gate 2.
- Source fact не является ledger item, tax conclusion или declaration field.
- Расширение scope требует нового terminal run и нового manifest; существующий
  ready manifest не мутируется.

Следующие форматы должны подключаться к тому же manifest family через свой
versioned technical profile и complete normalized units. Отдельный Gate 3 root
для каждого формата запрещён.

## 7. Нормативный статус

```text
CSV_SUPPORTED_PROFILE: VERSIONED_AND_DOCUMENTED
CSV_NORMALIZATION: COMPLETE_FOR_DECLARED_SCOPE
CSV_GATE_2_SOURCE_FACTS: TERMINAL_AND_VALIDATED
GATE_3_CONTEXT_MANIFEST: READY
PRE_GATE_3_CONTEXT_LAYER: READY_WITH_EXPLICIT_CSV_LIMITATIONS
```
