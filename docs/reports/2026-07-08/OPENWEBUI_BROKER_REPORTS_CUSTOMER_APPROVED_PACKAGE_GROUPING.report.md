# OpenWebUI Broker Reports: Customer-Approved Package Grouping Report

Date: 2026-07-08

Status:

- CUSTOMER_APPROVED_PACKAGE_GROUPING_READY
- CUSTOMER_SOURCE_REGISTRY_UPDATED
- CUSTOMER_CASE_GROUPS_CREATED
- CUSTOMER_DUPLICATE_MAP_READY
- CUSTOMER_REVIEW_QUEUE_READY
- CUSTOMER_APPROVED_RETENTION_APPLIED
- CUSTOMER_ARTIFACTSTORE_PERSISTENCE_READY
- CUSTOMER_KNOWLEDGE_GUARD_PASSED
- READY_FOR_SELECTED_CASE_GROUP_GATE2_PROOF

## 1. Граница среза

Выполнена controlled Gate 1 группировка operator-approved customer test package.
Источник взят только из ignored private local registry предыдущего approved intake run.

Raw filenames, relative paths, full local paths, rows, sheet names и private text в отчёте не публикуются.
Customer documents не копировались в репозиторий и не коммитились.

## 2. Файлы и форматы

- Обработано файлов: `63`
- Форматы: `{'csv': 2, 'html_text': 4, 'pdf': 31, 'xlsx': 2, 'zip': 24}`
- Классы документов: `{'calculation_template': 2, 'dividends_report': 7, 'fees_report': 2, 'operations_table': 8, 'source_broker_report': 7, 'tax_base_calculation': 5, 'unknown_or_needs_review': 32}`

## 3. Case/package groups

- `case_group_001`: брокер/провайдер=`BCS`, документов=11, source=4, output/methodology=4, review=3, confidence=low
- `case_group_002`: брокер/провайдер=`Interactive Brokers / IBKR`, документов=16, source=14, output/methodology=2, review=0, confidence=high
- `case_group_003`: брокер/провайдер=`Otkritie`, документов=3, source=2, output/methodology=0, review=1, confidence=low
- `case_group_004`: брокер/провайдер=`Sber`, документов=4, source=0, output/methodology=1, review=3, confidence=low
- `case_group_005`: брокер/провайдер=`VTB`, документов=4, source=3, output/methodology=0, review=1, confidence=low
- `case_group_006`: брокер/провайдер=`unknown`, документов=25, source=1, output/methodology=0, review=24, confidence=low

## 4. Source vs output/methodology

- Source evidence candidates: `24`
- Output/methodology/calculation artifacts: `7`
- Документов в review queue: `61`
- ZIP/archive review entries: `24`

Source evidence здесь означает только Gate 1 role candidate. Source-fact extraction не запускался.

## 5. Дубликаты, архивы и blockers

- Duplicate groups: `2`
- Duplicate documents: `2`
- Архивов, требующих review: `24`
- Gate 1 normalizer blockers: `92`

ZIP/archive contents не повышались до source evidence. OCR/VLM не выполнялся.

## 6. Рекомендованный первый пакет для Gate 2 proof

Рекомендованный case group: `case_group_002`

Причина: самая связная группа с большим количеством source-evidence candidates и без зависимости от ZIP/archive review.

Перед Gate 2 execution нужно спросить заказчика/специалиста:

- подтвердить выбранный case group;
- подтвердить tax year/account boundary, если он не следует из safe metadata;
- уточнить, являются ли output/calculation files примерами, методологией или прежними результатами;
- явно подтвердить разрешение на source-fact extraction для этого пакета;
- подтвердить методологию по fees, FX/rates, withholding и tax-base treatment.

## 7. Safe/private artifacts

- Safe source registry: `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.vNEXT.safe.json`
- Case/package grouping registry: `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_CASE_GROUPS.v0.safe.json`
- Private ArtifactStore boundary: ignored private evidence root (path withheld)
- Gate 2 handoff ref available: `True`
- Gate 2 handoff использует opaque ArtifactStore refs, not chat JSON.

Private ArtifactStore boundary находится в ignored local storage и не коммитится.

## 8. Retention и Knowledge guard

- retention_policy.mode: `customer_approved_test`
- retention_policy.explicit: `True`
- retention_policy.ttl_seconds: `1209600`
- private slices persisted as `private_case` records;
- purge policy доступна через ArtifactStore case/run purge;
- customer_docs_loaded_to_knowledge=false.

OpenWebUI Knowledge count before: `0`
OpenWebUI Knowledge count after: `0`
Knowledge unchanged: `True`

## 9. Commands

```text
python services/broker-reports-gate1-proof/scripts/customer_approved_package_grouping.py --retention-explicit --check-openwebui-knowledge --env-file .env
python -m unittest discover -s services/broker-reports-gate1-proof/tests -v
python -m compileall -q services/broker-reports-gate1-proof
git diff --check
```

## 10. Запрещённые работы не выполнялись

- source_fact_extraction_performed=false;
- tax_correctness_claimed=false;
- declaration_generated=false;
- xlsx_generated=false;
- ocr_performed=false;
- customer documents/private slices не загружались в Knowledge;
- raw filenames/private paths/rows/text/sheet names не публиковались.
