# Broker Reports: аудит и принудительная изоляция контрактов Gate

Дата: 2026-07-18

Репозиторий: `Kwentin3/corp-openweb-ui`

Исходная ревизия: `8801aa2ec67e3b43c89fd71f4354855ff62669d3`

Runtime-ревизия: `b61b509`

Область: maintained Broker Reports runtime, контракты, ArtifactStore/resolver,
Function bundles, тесты и stage-доставка. Новая продуктовая функциональность не
добавлялась.

## 1. Итог простыми словами

До аудита архитектура была правильной по смыслу, но код не везде соблюдал её
физически. Gate 2 напрямую знал о нескольких внутренних форматных модулях Gate
1, читал конкретное SQLite-хранилище и обновлял уже созданные run-артефакты.
Кроме того, Gate 2-сборщик табличных пакетов жил в Gate 1-модуле.

Это были реальные нарушения границ, а не только неудачные имена файлов. Они
устранены минимальным совместимым рефакторингом:

- Gate 2 получает Gate 1 данные через один публичный контракт и resolver;
- Gate 2-табличные пакеты перенесены к владельцу, старый импорт оставлен ленивым
  совместимым фасадом;
- артефакт с существующим id нельзя заменить другим содержимым;
- Gate 2 сохраняет один терминальный run, а не перезаписывает его по ходу
  выполнения;
- Gate 3 context manifest остаётся выходом Gate 2 и единственным разрешённым
  входным корнем будущего Gate 3;
- архитектурные тесты теперь не дают вернуть прямые импорты, SQLite bypass,
  reverse dependency или overwrite-путь.

Проверенный maintained-код следует четырёхступенчатой архитектуре. Это не
означает, что Gate 3 и Gate 4 реализованы: их бизнес-runtime по-прежнему
отсутствует, как и должен в рамках этой задачи.

## 2. Карта зависимостей: до и после

### До

```text
Gate 1 format internals ---------------------------> Gate 2 runtimes
  full_source / pdf_text_layer / pdf_layout_units     direct Python imports
  source_provenance / table_projection

Gate 2 runtimes ---------------------> SqliteArtifactStoreAdapter
                                       list_by_run / get_record_unchecked

Gate 2 created run -- overwrite --> terminal run -- overwrite --> manifest ref

Gate 1 table_projection.py ----------> builds/validates Gate 2 packages
```

На базовой ревизии найдено 14 прямых импортов по проверяемому шаблону. Один из
них, `gate2_handoff.py -> artifact_store`, является исторически названным Gate
1-производителем handoff и рассмотрен отдельно ниже. Остальные материальные
cross-gate связи устранены.

### После

```text
Gate 1 internals
  -> gate1_public_contracts.py
  -> versioned Gate 1 artifacts + ArtifactResolver
  -> Gate 2 readiness/packages/runtimes/validators
  -> terminal versioned Gate 2 artifacts
  -> broker_reports_gate3_context_manifest_v0
  -> future Gate 3

Gate runtimes -> ArtifactStorePort/ArtifactResolver -> SQLite adapter

Gate 2 execution -> append new Gate 2 artifacts; Gate 1 source memory unchanged
```

В maintained Gate 2 business-модулях больше нет импортов
`full_source`, `pdf_text_layer`, `pdf_layout_units`, `source_provenance`,
`table_projection` или конкретного store. Прямые unchecked/list-чтения остались
только внутри platform store/resolver и в отдельном Gate 1 research-shadow
контуре; архитектурный тест запрещает их Gate 2.

## 3. Владение модулями и семействами артефактов

| Поверхность | Единственный владелец | Публичный выход / потребитель | Состояние |
| --- | --- | --- | --- |
| format intake, full-source, normalized text/table, PDF Table Intake | Gate 1 | versioned source artifacts, DCP, issue ledger -> Gate 2 | implemented; scope-specific closure unchanged |
| document passport, DCP, issue ledger, `gate2_handoff_v0` producer | Gate 1 | resolver-accessible refs -> Gate 2 | implemented |
| `gate1_public_contracts.py` | Gate 1 boundary | Gate 1 schema constants, structural validators and source-value reproduction -> Gate 2 | new enforced public surface |
| input readiness and Gate 2 package construction | Gate 2 | validated bounded packages -> Gate 2 model/runtime | implemented |
| candidate sets, relations and binding validation | Gate 2 | validated semantic selection -> source-fact materializer | implemented |
| source/domain run, raw evidence, facts, validation, stitching, coverage | Gate 2 | terminal validated graph -> context manifest | implemented for bounded contours |
| `gate2_table_packages.py` | Gate 2 | versioned table source-fact package | moved to correct owner; old lazy export retained |
| `broker_reports_gate3_context_manifest_v0` | Gate 2 exit boundary | checked immutable index -> future Gate 3 | implemented; no Gate 3 business logic |
| reconciliation, intermediate ledgers, case assembly | Gate 3 | future Gate 3 root -> Gate 4 | not implemented |
| tax, declaration, review and export preparation | Gate 4 | future controlled outputs | not implemented |
| ArtifactStore, resolver, retention/purge | cross-cutting platform | scoped immutable refs -> all gates | domain-neutral mechanics |
| provider registry/adapters/model client | cross-cutting transport with Gate 2 policy contracts | structured proposal + execution metadata -> Gate 2 validators | no acceptance/business authority |
| managed prompts | owning gate contract | versioned prompt/schema hashes -> owning runtime | 12/12 parity-proven |
| Function bundles/build/update/parity scripts | delivery platform | deployable copies of maintained modules | no domain authority |

Физическое имя пакета `broker_reports_gate1` остаётся историческим контейнером
совместимости. Владение определяется модулем, контрактом, фабрикой и типом
создаваемого артефакта, а не верхним именем Python package.

## 4. Реестр нарушений

| ID | Серьёзность | Нарушение | Решение |
| --- | --- | --- | --- |
| V1 | высокая | Gate 2 напрямую импортировал форматные внутренности Gate 1. | Введён `gate1_public_contracts.py`; Gate 2 импортирует только этот surface и собственные контракты. |
| V2 | высокая | Gate 2 зависел от `SqliteArtifactStoreAdapter` и делал `list_by_run` / `get_record_unchecked`. | Введён domain-neutral `ArtifactStorePort`; чтение перенесено в scoped `ArtifactResolver.catalog_run/resolve_record`. |
| V3 | высокая | `INSERT OR REPLACE` и повторная запись одного run id позволяли семантическую замену артефакта. | Только `INSERT`; одинаковый replay идемпотентен, отличающееся содержимое даёт `artifact_immutable`; Gate 2 пишет один terminal run. |
| V4 | средняя | Gate 2 package builder/validator находился в Gate 1 `table_projection.py`. | Реализация перенесена в `gate2_table_packages.py`; прежний путь — только ленивый compatibility export. |
| V5 | средняя | Версии domain run/summary, package schema и normalized-value fields дублировались. | Константы имеют одного владельца в Gate 2 contract-модулях; потребители импортируют их. |
| V6 | низкая | Bundle builder не знал о новых boundary-модулях. | Модули добавлены в явный dependency order; три bundle пересобраны и протестированы. |

Неразрешённых материальных нарушений в audited maintained scope не осталось.

## 5. Выполненный рефакторинг

1. Выделен публичный Gate 1 contract surface без изменения versioned artifact
   names и payload meaning.
2. Выделен `ArtifactStorePort`; Gate runtimes и manifest зависят от порта и
   resolver, а не от SQLite-класса.
3. Добавлены metadata-only resolver operations с обязательной проверкой
   user/run/case-or-chat/workspace scope.
4. Убраны Gate 2 format-private imports; воспроизведение source values и
   структурные проверки доступны только через Gate 1 public boundary.
5. Gate 2 table packages перемещены к владельцу с compatibility-safe lazy
   re-export.
6. ArtifactStore переведён с replace-семантики на immutable insert/idempotent
   replay; external payload создаётся exclusive-write.
7. Source/domain Gate 2 runtimes перестали сохранять `created` и заменять тот
   же run. Они добавляют один terminal run и новые дочерние артефакты.
8. Manifest ref планируется детерминированно до terminal run, затем manifest
   сохраняется один раз и сверяется с планируемым ref.
9. Добавлен AST-based architecture test и обновлён closed-world bundle order.

Это behavior-preserving contract enforcement. Миграции схемы, новых artifact
families, форматов, Gate 3 ledger или налоговой логики нет.

## 6. Проверенные опасения, не потребовавшие рефакторинга

| Опасение | Вывод |
| --- | --- |
| `broker_reports_gate1/__init__.py` экспортирует много типов | Совместимый публичный фасад, не runtime decision path. Деструктивная смена package запрещена и не даёт архитектурной пользы. |
| `gate2_handoff.py` импортирует store | Несмотря на имя, это Gate 1 producer versioned Gate 1 -> Gate 2 handoff. Это не Gate 2 business consumer и не reverse dependency. |
| Общий artifact type registry | Механический allowlist platform store; финансовых решений и readiness authority нет. |
| `stable_digest` | Общая детерминированная утилита без доменной политики. |
| provider adapters | Только transport/schema projection/execution metadata; они не принимают facts и не импортируют business runtimes. |
| PDF hybrid/structural/direct-PDF modules | Gate 1 research/shadow или bounded intake; они не являются Gate 2 semantic authority. Accepted PDF Table Intake не переоткрывался. |
| Python dictionaries внутри одной фабрики/validator call | Это локальное представление versioned schema. Между gates нормативно передаются только persisted refs; shared mutable handoff memory не используется. |
| Compatibility readiness flags | Сохраняются для чтения старых артефактов, но manifest factory их не считает authority и recomputes declared graph. |

## 7. Карта меж-gate контрактов и validators

| Переход | Producer | Versioned boundary | Deterministic validation / failure | Completeness и storage |
| --- | --- | --- | --- | --- |
| Gate 1 -> Gate 2 | Gate 1 normalizer/DCP/handoff factories | `domain_context_packet_v0`, `gate2_handoff_v0` и resolver-linked descendants | `Gate2InputReadinessFactory`, Gate 1 public validators; wrong scope/lifecycle/schema fail closed | Только declared source-ready refs; private payload остаётся `private_case`, safe indexes — `safe_internal` |
| Gate 2 internal terminal graph | Gate 2 package/model/validator/stitch factories | versioned packages, raw evidence, facts, validation, stitch, summary, terminal run | strict schema + deterministic fact/binding/stitch/coverage validators | Accepted/rejected/deferred scope explicit; writes append-only |
| Gate 2 -> Gate 3 | `Gate3ContextManifestFactory` at Gate 2 exit | `broker_reports_gate3_context_manifest_v0` | resolver re-read, graph/hash/scope/lifecycle/privacy/terminal-status recomputation; mismatch fails closed | Checked index of one declared terminal Gate 2 graph; no copied private values |
| Gate 3 -> Gate 4 | no maintained producer | proposal only | not applicable | Business runtime intentionally not implemented |

Будущий Gate 3 может начинаться без импортов Gate 1/Gate 2 internals: его
единственная допустимая исходная точка — validated context manifest и resolver.
Архитектурный тест уже запрещает иную зависимость для будущих `gate3*` business
modules.

## 8. Инвариант независимой памяти документов

Инвариант доказан для maintained execution path.

- `ArtifactStore.put_record` не позволяет изменить payload/contract/scope
  существующего id; другой смысл требует нового id.
- lifecycle/source-delete/purge меняют только явно разрешённое состояние и не
  заменяют business payload.
- тест выполняет реальный Gate 2 run, снимает полный snapshot всех ранее
  созданных Gate 1 records/payloads и доказывает byte/structure equality после
  выполнения; новые Gate 2 records появляются дополнительно.
- model/prompt retry, rejected fact и новый manifest создают новые артефакты и
  не меняют source units, normalized payloads, DCP или issue ledger.

Следствие: Gate 1 может менять внутренний parser/normalizer без изменения Gate
2, пока сохраняется публичная versioned boundary. Новая версия boundary требует
явного adapter/validator update, а не скрытого импорта parser internals.

## 9. Проверка после рефакторинга

### Local

| Команда/контур | Результат |
| --- | --- |
| `python -m unittest discover -s tests` | `712 tests`, `OK`, 48.629 s |
| Architecture + CSV + PDF Table Intake + store/lifecycle + Gate 2 runtime | `60 tests`, `OK`, 18.779 s |
| Regenerated Gate 1/Gate 2 bundle + candidate/architecture contour | `32 tests`, `OK`; только SWIG deprecation warnings |
| `python -m compileall -q broker_reports_gate1 scripts tests` | `COMPILEALL_OK` |
| Ruff по всем изменённым source/test modules (`E402` исключён как существующее test path setup) | `All checks passed` |
| `git diff --check` | passed |

Финальный полный suite подтверждает контракты, accepted CSV profile, PDF Table
Intake, wrong user/case/chat, expiry, purge, source deletion, no-Knowledge
guards, terminal Gate 2 graph и manifest lifecycle.

В процессе рефакторинга тесты действительно ловили ошибки: пять scope/order
ошибок resolver, пропущенный compatibility import и неправильный bundle module
order. Все причины исправлены; финальные прогоны выше выполнены после
исправлений. Это не были проигнорированные flaky failures.

### Stage

1. Штатные update scripts успешно установили три Function bundle и выполнили
   read-back Prompt contracts.
2. Общий synthetic Gate 2 smoke: `status=passed`, terminal `completed`, 9 fact
   types, 45 временных records, затем 45 purged; file/document/Knowledge/vector
   delta = 0.
3. Доменный `income` candidate-binding smoke через approved Gemini profile:
   `status=passed`, terminal `completed`, validator passed, stitch complete,
   30 временных records, затем 30 purged; Knowledge/vector delta = 0.
4. Read-only parity verifier: `status=passed`, Function bundle `3/3`, managed
   Prompt `12/12`, approved provider registry/factory boundaries passed.

Дополнительный первый domain attempt через `gpt-5.6-luna` был отвергнут
провайдером как `gate2_model_schema_response_format_rejected`. Runtime корректно
завершился `completed_with_rejections`, не сохранил невалидные facts, не писал в
Knowledge/vector и очистил 27 records. Следующий Gemini attempt прошёл. Между
ними один запрос не дошёл до Pipe из-за 30-second `/api/v1/auths/` timeout и не
создал артефактов. Эти события атрибутированы как provider/transport evidence,
а не замаскированы изменением валидатора.

Stage SHA:

| Function | Repository = live SHA-256 |
| --- | --- |
| `broker_reports_gate1_pipe` | `b02272b9eaf7c95cd0928d01b8e682a562fe3b09b97f6919c062fbef6a292035` |
| `broker_reports_gate2_source_fact_pipe` | `c8e6d43d49a1ef2bf70d1752a7b15d5212c1e7964a31454509b3ffe5c5a524fe` |
| `broker_reports_gate2_domain_source_fact_pipe` | `977a12db5d8765ea6096a49afeeb28b069ad4a8d4cf317bc9d8e47d369e23466` |

## 10. Ответы на ключевые вопросы аудита

| Вопрос | Ответ |
| --- | --- |
| Один ли business owner у каждой maintained capability? | Да; матрица разделяет Gate 1, Gate 2, Gate 2 exit, будущие Gate 3/4 и platform mechanics. |
| Была ли логика размазана между gates? | Частично и материально: Gate 2 package logic находилась в Gate 1 module, а Gate 2 импортировал parser internals. Исправлено. |
| Может ли gate мутировать артефакты другого gate? | Нет на maintained store path: semantic overwrite rejected; downstream создаёт новые ids. |
| Версионированы и валидируются ли handoff? | Да для двух maintained переходов; scope/readiness recomputed. |
| Есть ли reverse/circular business dependencies? | Нет; lazy compatibility export из Gate 1 module в Gate 2 owner изолирован и не участвует в normal runtime construction. |
| Domain-neutral ли store/resolver? | Да; они знают scope, lifecycle, visibility и retention, но не financial facts/readiness semantics. |
| Ограничены ли providers transport/schema projection? | Да; deterministic Gate 2 validators остаются authority. |
| Можно ли начать Gate 3 без internals предыдущих gates? | Да архитектурно: только manifest + resolver. Сам Gate 3 business runtime ещё не реализован. |

## 11. Оставшийся архитектурный долг

- Историческое имя package и большой `__init__.py` остаются compatibility debt,
  но не дают бизнес-владение и не оправдывают destructive rewrite.
- `ArtifactStorePort` пока имеет одну SQLite implementation; порт отделяет
  runtime, но не обещает готовность другой БД.
- Gate 1 format acceptance остаётся scope-specific; OCR/image-only и universal
  formats не закрыты этой задачей.
- Gate 2 coverage остаётся bounded; этот аудит не доказывает full-corpus
  semantic completeness.
- Gate 3 и Gate 4 business contracts/runtime не реализованы. Architecture guard
  задаёт вход будущего Gate 3, но не является доказательством ещё не
  существующей reconciliation логики.
- Старый OpenAI domain smoke показал provider-specific strict-schema rejection;
  это не boundary defect, но остаётся отдельным operational/provider вопросом.

Ни один пункт не нарушает изоляцию текущего maintained runtime и не требует
расширять scope этого refactor.

## 12. Финальный статус

```text
BROKER_REPORTS_GATE_CODE_ISOLATION:
PROVEN

INTER_GATE_CONTRACT_BOUNDARIES:
ENFORCED

DOMAIN_OWNERSHIP_IMPLEMENTATION:
CONSISTENT

POST_REFACTOR_VERIFICATION:
PASSED

REPOSITORY_LIVE_ALIGNMENT:
PROVEN_OR_NOT_REQUIRED
```

Здесь `REPOSITORY_LIVE_ALIGNMENT` означает `PROVEN`: runtime revision
`b61b509` находится в `origin/main`, все три stage Function bundle совпадают с
репозиторием по SHA-256, все 12 managed Prompt совпадают по содержимому и
metadata.
