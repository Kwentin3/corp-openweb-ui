# Broker Reports Global Gate 1 — Multi-Format Document Memory Closure v1

Дата: 2026-07-18

Репозиторий: `Kwentin3/corp-openweb-ui`

Runtime-ревизия: `a8d8b1f`

Private-corpus ignore protection: `2b60c8b`

Итог: `CLOSED_FOR_SUPPORTED_PILOT_PROFILE_V1`

## 1. Вывод простыми словами

Реальный клиентский корпус найден. Предыдущий вывод «исходных файлов нет» был
неверным: устарели сохранённые рабочие пути, а не сами документы.

Все 63 исходных файла сверены по SHA-256 с безопасным реестром и скопированы в
стабильное приватное хранилище вне Git. Из них 56 являются обязательными
верхнеуровневыми источниками. Внутри 24 ZIP действительно лежат нужные PDF и
XML, поэтому ZIP нельзя было оставить «условным» или просить пользователя
распаковывать вручную. Добавлена ограниченная безопасная ZIP-поддержка.

Полный фактический прогон обработал 104 source records: 56 исходных входов и
48 promoted PDF/XML members. Это 80 логических документов, потому что ZIP —
контейнер происхождения, а не отдельный финансовый документ.

Итоговые состояния: 26 `complete`, 78 `review_required`, ни одного `partial`,
`blocked`, `unsupported` или `unreadable`. Во всех 104 случаях accounting и
zero-silent-loss прошли. Агентская техническая ревизия также прошла 104/104.

`review_required` здесь означает не потерю данных, а честное ограничение:
память документа полна, но конкретную таблицу, XML-структуру, визуальный слой
или дубль нельзя автоматически объявлять каноническим финансовым фактом.

## 2. Что показала фактическая ревизия корпуса

| Факт | Результат |
| --- | ---: |
| Физические файлы / общий размер | 63 / 18,872,606 bytes |
| SHA-мультимножества original / private copy / safe registry | совпадают |
| Duplicate groups / extra copies | 2 / 2 |
| Обязательные top-level sources | 56 |
| ZIP containers | 24 |
| ZIP members | 72 |
| Promoted PDF/XML members | 48 |
| Accounted P7S sidecars | 24 |
| Source records в Gate 1 | 104 |
| Logical documents | 80 |

Два XLSX — 20-листовые формульные расчётные книги. Ещё пять PDF — производные
налоговые расчёты. Они исключены не из-за отсутствия реализации и не ради
зелёного статуса: проверка фактического содержимого показала, что это
downstream outputs, а не первичные source-evidence документы.

## 3. Уточнённый профиль v1

| Формат | Что поддержано | Что получает Gate 2 |
| --- | --- | --- |
| CSV | строгий CSV с versioned limits | ordered rows/source values и validated table projection |
| static HTML | DOM-ordered text/tables и bounded data images | text/table scopes; visual units с обязательным visual consumer |
| PDF | page text/layout и bounded rendered visual fallback | page/text/table scopes, provenance и явные ограничения |
| XML | ordered neutral events без DTD/entities | neutral structure; canonical financial table unavailable |
| ZIP | bounded extraction PDF/XML, P7S sidecar accounting | lineage-only container и обычная memory каждого promoted member |

ZIP factory запрещает traversal, absolute paths, symlinks/special files,
encryption, nested archives, member-name collisions и превышение budget/ratio.
Ни один member не может исчезнуть без disposition.

## 4. Реальные дефекты, найденные и исправленные proof gate

Первый полный запуск сохранил данные, но честно оставил девять `partial`:
PDF требовали явного text/visual fallback, а четыре HTML содержали встроенные
изображения. Добавлены bounded PDF visual-page memory и HTML visual-media
memory.

Следующий operator review поймал ещё один настоящий дефект: значения четырёх
HTML были сохранены, но внешний текст и таблицы группировались и теряли общий
DOM-порядок. Production extractor исправлен: text/table blocks теперь идут в
исходной последовательности, таблицы сохраняют собственный ordinal, а media
сверяется по checksum. После регресса на четырёх реальных HTML весь corpus proof
повторён с нуля и прошёл.

## 5. Actual-corpus execution и operator acceptance

Safe proof:
`BROKER_REPORTS_GATE1_ACTUAL_CUSTOMER_CORPUS_ACCEPTANCE.v1.safe.json`.

| Проверка | Результат |
| --- | --- |
| Normalization run | `normrun_e1855c54126bce9c` |
| Package validation | passed |
| Terminal source records | 104/104 |
| `complete` / `review_required` | 26 / 78 |
| Accounting | passed for all accepted records |
| Zero silent loss | passed for all accepted records |
| Archive profile | 24/24 containers, 72/72 members accounted |
| Agent operator review | passed, 104/104 |
| Human customer acceptance | not performed |
| Knowledge/RAG/vector | not used |

Ревизия сравнивала реальные bytes с resolver-доступной private memory: SHA и
размер, начало/середину/конец, страницы, таблицы, строки/ячейки/значения,
PDF provenance, HTML order, XML events, ZIP lineage, unresolved scopes и
отсутствие ложного `complete`.

## 6. Публичная граница Gate 1 -> Gate 2

DCP ссылается на `broker_reports_gate1_document_memory_manifest_v1` по schema,
manifest id и integrity hash. Gate 2 получает память только через
`ArtifactResolver` и typed refs. Проверено:

- manifest validator passed;
- profile enforcement required;
- resolver required;
- format-specific parser в Gate 2 не требуется;
- scope readiness и restrictions присутствуют;
- public audit не изменяет ArtifactStore;
- private payloads не встроены в safe root.

Полная массовая сборка всех опциональных Gate 2 packages не является условием
Gate 1 closure. Ранее она показала длительное небounded-время и вынесена в
отдельный performance debt. Это не дефект сохранности document memory.

## 7. Тесты и live alignment

Локальный сервисный набор: `903 passed`, 5 dependency deprecation warnings.

После runtime-коммита обновлены все три автономных Functions. Read-only parity
proof завершился `status=passed`:

| Function | Repo/live SHA-256 |
| --- | --- |
| `broker_reports_gate1_pipe` | `99ed3acf67b650444c5919f1030155ce89d5bbdbddb447bfb8671856913f39df` |
| `broker_reports_gate2_source_fact_pipe` | `6ca9969c1ddd768cf5677259211cc40cb3fd352eb36c96e5a9bbf7c0c9c98645` |
| `broker_reports_gate2_domain_source_fact_pipe` | `829dcc885828df206f228a2151752339f0647a8be6d3b0ed1a872931f67d9679` |

Managed Prompts: 12/12 совпадают. `fitz=1.26.5`. Factory-boundary audit passed.
Stage-container synthetic mixed-format proof на поставленном Gate 1 bundle
также прошёл. Клиентские документы на stage не загружались: фактический corpus
proof выполнен parity-equivalent backend core в приватной среде.

## 8. Приватность и Git isolation

- Original corpus не изменялся.
- Private copy, extracted members, local registry, ArtifactStore и proof work
  находятся вне репозитория.
- Maintained code не содержит абсолютного пути к клиентскому корпусу.
- Local path config игнорируется Git.
- Safe JSON не содержит private paths, filenames, source values или media.
- Customer documents не загружались в Knowledge/RAG/vector storage.
- Git получает только код, тесты, contracts и safe evidence.

Дополнительно рассчитаны Git-compatible blob ids всех 63 исходников: это 61
уникальный blob с учётом двух duplicate copies. Совпадений с текущим Git index
и со всей достижимой историей репозитория — `0 / 0`.

## 9. Что закрытие не утверждает

Gate 1 закрыт только для поддержанного профиля v1. Это не означает:

- human customer acceptance — оно не выполнялось;
- канонический выбор двух duplicate groups;
- каноничность каждой unresolved PDF/HTML/XML таблицы;
- готовность финансовой/налоговой семантики Gate 2/3;
- устранение performance debt массового Gate 2 package builder;
- универсальную поддержку XLSX/DOCX/TXT/XLS или новых ZIP member formats.

Эти ограничения сохранены явно и не отменяют доказанную полноту Gate 1 memory.

## 10. Acceptance matrix

| Критерий | Состояние |
| --- | --- |
| Authoritative corpus recovered/reconciled | passed |
| Required source-evidence set approved | passed |
| Bounded ZIP source-container profile | implemented and proven |
| Every required source/member terminal | passed |
| Accounting and zero silent loss | passed for actual accepted corpus |
| Scope-level restrictions | passed |
| Public Gate 1 handoff | stable and validated |
| Agent-operated acceptance | passed |
| Human customer acceptance | not performed, not required for technical closure |
| Repository/live parity | passed |
| Private corpus Git isolation | passed |

## 11. Обязательный финальный статус

```text
BROKER_REPORTS_GLOBAL_GATE_1:
CLOSED_FOR_SUPPORTED_PILOT_PROFILE_V1

ACTUAL_CUSTOMER_CORPUS:
RECOVERED_AND_RECONCILED

ACTUAL_CORPUS_GATE_1_EXECUTION:
PASSED

AGENT_OPERATOR_ACCEPTANCE:
PASSED

ZIP_SOURCE_CONTAINER_PROFILE:
IMPLEMENTED_AND_PROVEN

ZERO_SILENT_LOSS:
PROVEN_FOR_ACTUAL_ACCEPTED_CORPUS

PRIVATE_CORPUS_GIT_ISOLATION:
PROVEN

GATE_1_PUBLIC_HANDOFF:
STABLE_AND_VALIDATED

REPOSITORY_LIVE_ALIGNMENT:
PROVEN
```
