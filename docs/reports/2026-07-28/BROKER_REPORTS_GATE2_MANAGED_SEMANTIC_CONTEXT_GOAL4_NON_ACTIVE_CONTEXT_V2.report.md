# Broker Reports Gate 2 — Managed Semantic Decision Context GOAL 4

Date: 2026-07-28

Status:
`PASSED_AS_NON_ACTIVE_CONTEXT_V2_PACKET_SIDECAR_WITH_PRIVATE_MAPPING_RECEIPT`

Base revision: `5520ce58c6f96d4e3f02dbf1c7d06af158153f36`

Branch:
`codex/broker-reports-gate2-managed-context-goal4-non-active-v2`

## 1. Результат

GOAL 4 реализован внутри существующей packet authority без смены рабочего
Gate 2 route.

Один вызов `Gate2FinancialSemanticV6PacketFactory.create` теперь строит:

1. прежний active V6 payload;
2. детерминированный неактивный Context V2 candidate;
3. private Context-to-authority mapping receipt.

Второй packet builder, второй Semantic Pack, второй каталог причин, отдельный
Context V2 loader и отдельная Choice authority не созданы.

На десяти frozen synthetic cases подтверждено:

```text
ACTIVE_PAYLOAD_BYTE_IDENTICAL: YES
CONTEXT_V2_ACTIVE: FALSE
CONTEXT_V2_CASES_BUILT: 10
LOCAL_KEY_BIJECTION: PASSED
SEMANTIC_LITERAL_OCCURRENCE_PARITY: PASSED
OPTION_MAPPING_RECONSTRUCTABLE_AT_PACKET_RECEIPT_BOUNDARY: PASSED
LOCAL_CHOICE_V2_NORMALIZATION: NOT_IMPLEMENTED_NOT_RUN
REASON_CODE_VIEW_RETAINED_AT_PACKET_BOUNDARY: PASSED
ACTIVE_UNCLASSIFIED_SOURCE_RETENTION_REGRESSION: PASSED
CONTEXT_V2_UNCLASSIFIED_SOURCE_RESTORATION: NOT_IMPLEMENTED_NOT_RUN
CONTEXT_V2_RESTORE_REPLAY: NOT_IMPLEMENTED_NOT_RUN
HIERARCHY_BRANCHES: 6/6 PASSED
TAMPER_REJECTION: PASSED
PROVIDER_CALLS: 0
```

Важное ограничение: это доказательство packet-sidecar, а не complete request.
V2 Choice/parser, Context Linter V2.1, provider request, persistence/replay и
benchmark не реализованы и не заявлены.

## 2. Аналитический вывод

В неактивном V2 candidate рефайн устранил основную структурную проблему
прежнего model view: это новое представление больше не обязано повторять
backend identities, bindings и длинные option IDs. Вместо этого будущая модель
получит читаемую иерархию, локальные ключи только там, где они нужны для выбора
или cross-reference, полные type cards и контрастные определения причин
`unclassified`. Active model route не изменён.

Backend при этом не теряет точность. Private receipt сохраняет:

- exact Evidence Bundle identities;
- exact source refs и lineage;
- exact Registry/Pack/catalog pins;
- exact `typed_option_id`;
- полную partition всех compiled bindings;
- JSON pointer и authority pointer каждого видимого leaf;
- content hash каждого видимого leaf;
- presentation/permutation identities.

Есть честный size trade-off. На шести cases с typed options V2 уменьшил
суммарный minified model view на 9 851 байт, или 16,95%. На четырёх
zero-choice cases он вырос на 14 502 байта, или 91,45%, потому что теперь даже
при пустом `choices` показывает оба доступных type card и обе причины
`unclassified`. По всем десяти cases итоговый размер вырос на 4 651 байт,
или 6,29%.

Это не дефект GOAL 4: полный type set в zero-choice cases нужен модели, чтобы
различать «ни один тип не подходит» и «несколько типов остаются
правдоподобными». Но результат запрещает заявлять, что V2 уже доказан как
более короткий контекст. Size budget должен быть измерен и закреплён будущим
Context Linter V2.1 до любого provider transport.

## 3. Context Bootstrap и затронутая authority

Работа начата от последнего accepted `origin/main` после merge GOAL 3.
Прочитаны корневые и service-level `AGENTS.md`, architecture authority map,
Context V2 contract и связанные Pack, reason catalog, Packet, Choice,
Candidate Compiler, Typed Option, Evidence Bundle и exact-evidence contracts.

Затронуты три существующие implementation surfaces:

1. maintained build и единый generated model-assets loader;
2. существующий V5-named semantic projection owner;
3. sole `Gate2FinancialSemanticV6PacketFactory.create`.

Это не три новые authority. Asset family остаётся единственным владельцем
управляемых semantic bytes; projection owner остаётся единственным
Pack/reason projector; PacketFactory остаётся единственным владельцем active
packet и неактивных packet-sidecar projections. Значения Pack/catalog не
переписаны в этих implementation surfaces.

Связанные существующие владельцы используются, но не заменяются:

| Concern | Существующий владелец | Что сделал GOAL 4 |
| --- | --- | --- |
| managed asset loading | один generated model-assets loader | добавил закрытый `context_v2_candidate` profile, сохранив default active profile |
| type semantics | Financial Semantic Pack через существующий projection owner | добавил version-pinned V2 projection с полными cards |
| reason semantics | Managed Decision Reason Catalog | добавил закрытую reason projection через тот же loader |
| source truth | Evidence Bundle | построил читаемую иерархию; exact refs оставил private |
| typed option truth | Candidate Compilation и Typed Options | выдал disposable `choice_N`, сохранил exact option mapping private |
| response choice | существующая V6 Choice authority | не менял; V2 local profile не реализован |
| request lint | существующая Context Linter authority | не менял; V2 extension не реализован |
| provider semantics | provider adapters | не менял; semantic repair отсутствует |

## 4. Архитектура реализации

Исполняемый путь GOAL 4:

```text
managed asset family 1.1.0
  -> existing generated model-assets loader(profile=context_v2_candidate)
  -> existing semantic projection owner
  -> existing Gate2FinancialSemanticV6PacketFactory.create
       -> unchanged packet.payload
       -> non-active context_v2_candidate
       -> private context_v2_mapping_receipt
```

Active default loader по-прежнему возвращает прежнюю active family/projection.
Context V2 snapshot:

- embedded в том же generated runtime module;
- проверяется по exact payload hash;
- не читает repository files во время runtime;
- не импортирует build scripts;
- имеет `runtime_activation=false`;
- не доступен как отдельный public packet builder.

Generated OpenWebUI bundle пересобран из maintained source. В него не добавлена
вторая реализация: обновилась только embedded копия единого model-assets
module.

## 5. Закрытая граница model view

Context V2 candidate имеет детерминированный порядок:

1. `task`;
2. `source`;
3. `type_cards`;
4. `choices`;
5. `shared_relationships`, только если блок непустой;
6. `unclassified_reasons`.

Модель видит:

- короткую неизменяемую задачу выбора;
- `document` с `table -> row`, direct `row`, `text segment` или bounded
  `evidence group`;
- каждый non-reference source literal ровно один раз на authoritative source
  occurrence;
- читаемые meaning, label и value type без null metadata;
- все source-family-compatible type cards (в frozen suite — две);
- локальные `value_N`, `type_N`, `choice_N` и structural keys только при
  необходимости;
- factored readable relationships;
- обе полные reason cards с exact codes.

Модель не видит:

- global refs;
- hashes;
- bundle/package/storage IDs;
- `typed_option_id`;
- `source_value_ref`;
- provider metadata;
- retention/replay metadata;
- source-reference literals;
- private mapping rows.

`source_reference` не превращается в повторённый literal. Только если binding
нужен semantic decision, model view получает читаемую relationship на
конкретную локальную structure или однозначную location phrase; exact
reference остаётся в private receipt.

## 6. Private mapping receipt

Packet-owned receipt имеет identity
`broker_reports_gate2_llm_semantic_context_v2_mapping_receipt_v1`.

Он содержит шесть доказательных групп:

1. `identities` — Context contract, active packet, Registry, Pack,
   projections, catalog и candidate hashes;
2. `scope` — Evidence Bundle, Compilation и exact type-set parity;
3. `visible_field_sources` — полный отсортированный набор JSON pointers,
   authority pointers и content hashes;
4. `local_mappings` — bijective maps value/structure/type/choice keys и
   necessary evidence-reference targets;
5. `binding_partition` — все visible relationships и все backend-only
   bindings;
6. `presentation_order` — exact arrays и permutation identity.

Receipt не является model input и не попадает в repository-safe packet report.
Repository-safe renderer публикует только counts, hashes и explicit
`contains_source_literals=false` / `contains_source_value_refs=false`.

## 7. Exact active compatibility evidence

Active payload строится до V2 sidecar тем же кодом и в прежнем порядке.
Следующие baselines закреплены тестом для всех frozen cases.

`packet_hash` — прежний canonical packet identity. `minified UTF-8 SHA-256`
проверяет exact order-preserving bytes, которые образуют model user content.

| Frozen case | Exact `packet_hash` | Minified bytes | Minified UTF-8 SHA-256 |
| --- | --- | ---: | --- |
| `syn_successor_v2_unique_cash` | `3bcb297a62bf17d74f032b4058dc4c4f3097f33de9f89626b194d4a1600b6851` | 9 638 | `8e36f80f2bcde76c54ac925d68c1d0689fb1cb7c532b742fcab0395ac9504c2e` |
| `syn_successor_v2_unique_printed_total` | `bf63a8bef84415ad2502f3403824eff71bcc386d6c5ea6bb839cdde9870a60c3` | 9 905 | `8bbf5d44e81938470331c398877513a40f387c43294c63ab85500e9014b3101a` |
| `syn_successor_v2_multiple_compatible` | `82a22e646b96e3588172f3f52f281b4e17aace30842699870abe7933341d5865` | 4 246 | `2185d47b0199586986ee846ba7090af14cc55e35b8418d3fda8c77eb396be571` |
| `syn_successor_v2_no_registry_type` | `871385de7814271f6eea35ea930be04c70f92ebc0f4c11d9d19d71f8848e25f5` | 9 770 | `45afe499cfecedc3ee9d3504e2275b953a1241e26a5a954d0df5d879db029314` |
| `syn_successor_v2_missing_discriminator` | `27ff112adfaec49dc6fe30e1ce0de0be127628ca79838c2b4f1171a7ad1fc775` | 9 145 | `246c0eade02cfea33b6573c7d630c93a3b16cdae1c5966716804a57d528311be` |
| `syn_successor_v2_detail_vs_subtotal` | `ec252ed7652fd7348b3f618a381da0efdc2c494d36384e94dea79a014cab92c6` | 3 822 | `b2b11905259090a31dc0abbeffaa1e32e25a423705329fbe90a634e635bd3566` |
| `syn_successor_v2_adjacent_equal` | `9eae5bc8bd399fdb7404f1a3caa22d3d8d56a590d933f0d3c4bab3bdfa689621` | 3 724 | `d0a6de192a59fb5a24bb59b74f60e28db1a9cf4c39faa10fb25b365e4d2b41bf` |
| `syn_successor_v2_adjacent_fx` | `160bdefb600523800bbc26c08435af9149103025b0a144021b5dbaf902a607f9` | 4 066 | `ec98eaabc2d80619b4d588c103994d0b1255299adcd34d03d63b17f1b5206164` |
| `syn_successor_v2_optional_missing` | `31a3fdfe2b56cc81fbdd672b16a5ed94c43116dcb8726199d5287e2eeaa15fb2` | 9 779 | `1ef10407214aa4064570d8b9b591e5de3aaa3a5732d94d530147285c781a23e1` |
| `syn_successor_v2_forbidden_neighbour` | `8504e930fdaadecc5353a895ab03ec15a8f3aab6fe1fd0bb33accb778bc95dea` | 9 875 | `2e291d7fa01fec0be365eaa5be6783e58ae230f1e2d6a8d53ec677120e64ca74` |

Итого active minified bytes: `73 970`.

Меняется только возвращаемый packet dataclass: к нему добавлены две
неактивные sidecar fields. `packet.payload`, `packet_hash`, Prompt, current
response format и request consumer не изменены.

## 8. Context V2 frozen evidence

Все значения ниже являются repository-safe metadata синтетического набора.
Source literals и exact refs здесь не публикуются.

| Frozen case | Context view hash | UTF-8 bytes | Semantic literals | Choices | Relationships | Mapping receipt integrity |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `syn_successor_v2_unique_cash` | `9c780b85968b651e627b0f040473d346035d52b253de7ae119cc87dd0c9bd57a` | 8 070 | 4 | 2 | 6 | `3afae0f6eefbc86b0d001712efc406cac7ec2f7bc59e693116cc2581077daae3` |
| `syn_successor_v2_unique_printed_total` | `7350efbf8aa78a57ad76ba5a7c68db4983637432020e4c96ab10e708ba9baa9a` | 8 068 | 4 | 2 | 6 | `b0c4140cf0ed825385be9a5d9819bb8089f3975b1c77bca344819e5a538f317a` |
| `syn_successor_v2_multiple_compatible` | `bf6a005731ef2bdad8d27ee5095e2686ec74eb24da5247cf60f5d8920f570e65` | 7 620 | 6 | 0 | 0 | `b7b3ab10c0f3c27c511ae02f3f81408eb614a1910a2d33e4bd7a983abb9c83b3` |
| `syn_successor_v2_no_registry_type` | `abc5f46a1c1a9a1ead6ef9b462bb6b8c2b12980e80ad5093c514ff664481fb5a` | 8 065 | 4 | 2 | 6 | `478ccf69fe3f42ac47dff2a36ecc6fa14c78fbf16969471a37e4ed76ef325587` |
| `syn_successor_v2_missing_discriminator` | `13fbf8cae4f00d675e0bed4c3ee7ccc2adab59d43586d9699561d3608e2280af` | 7 921 | 3 | 2 | 5 | `4ef5685f1e5c31b14adb73c502d3042c4616856c5844e6adab902938f3b657e2` |
| `syn_successor_v2_detail_vs_subtotal` | `51f35dcf4fa75c531df5e0dadae1d325cd949de474e9b4a1d1a78032fda5cf3f` | 7 560 | 5 | 0 | 0 | `86f36bf502a117c478e9ec7fe6bc510165fed142a7ddafbe9c1f227da9f60e93` |
| `syn_successor_v2_adjacent_equal` | `0e4370b96a6d0ea2d4833f6811592a0fd9cf97e8fc332f5658ab98f5ff6e7fcf` | 7 556 | 5 | 0 | 0 | `4877094a81683d122080aee1b042656b01312712261dc09ae9ea9575ee28e333` |
| `syn_successor_v2_adjacent_fx` | `dfd16c24fa90ce7789783c52f6fa1d5c23c06a1dc7de073949b897fbd6a69fbb` | 7 624 | 6 | 0 | 0 | `ae1054112feca91b1861a8b6121895897d0f1448bd6a3511fda073a5e4cb371f` |
| `syn_successor_v2_optional_missing` | `6a24834df539580bfd5eb30e39eae3360e9743ef16a091cef1539ae4d8e85bee` | 8 068 | 4 | 2 | 6 | `ac905df80a2c293a4d820b35dd569c0bbd07cb5402c9bbdd573c2620b3d0024f` |
| `syn_successor_v2_forbidden_neighbour` | `f4dbf86e9e6db424af5bdfd05f6b45554762c5879e8c505a8f6e941de42fea09` | 8 069 | 4 | 2 | 6 | `d79e9545cbf63720b72b691bf294bbc70504091f89979d2d100fc1380cba109b` |

Aggregate:

```text
CASES: 10
MODEL_VISIBLE_UTF8_BYTES: 78621
SEMANTIC_LITERAL_OCCURRENCES: 45
TYPE_CARDS_PER_CASE: 2
CHOICES: 12
VISIBLE_FIELD_SOURCE_ROWS: 1408
COMPILED_BINDING_OCCURRENCES: 59
COVERED_BINDING_OCCURRENCES: 59
VISIBLE_RELATIONSHIPS: 35
SEMANTIC_VALUE_RELATIONSHIPS: 23
EVIDENCE_PREDICATE_RELATIONSHIPS: 12
FACTORED_DUPLICATE_OCCURRENCES: 24
BACKEND_ONLY_BINDINGS_IN_FROZEN_SUITE: 0
NECESSARY_REFERENCE_TARGETS: 12
```

`59 -> 35` не означает потерю bindings. Двадцать четыре повторяющихся
occurrences сведены в shared/readable relationships, а receipt перечисляет
каждый covered original binding.

## 9. Zero-choice и unclassified

Четыре frozen cases имеют пустой Compiler `typed_options`:

- `syn_successor_v2_multiple_compatible`;
- `syn_successor_v2_detail_vs_subtotal`;
- `syn_successor_v2_adjacent_equal`;
- `syn_successor_v2_adjacent_fx`.

Active payload оставлен прежним, включая исторически пустой
`available_type_cards`.

Неактивный V2 candidate во всех четырёх случаях:

- сохраняет все semantic literals;
- показывает обе Registry-authorized source-family-compatible type cards;
- оставляет `choices=[]`;
- показывает обе полные reason cards;
- сохраняет exact decision-code view в private receipt.

Такой shape позволяет будущей модели сравнить видимый источник с типами и
осмысленно различить:

- `no_registry_type`;
- `ambiguous_registry_type`.

GOAL 4 не выбирает reason, не меняет frozen expected answers и не утверждает,
что эти expected answers семантически верны. Это задача последующих local
proof/smoke GOALs.

## 10. Packet-boundary mapping и bijection

Для каждого frozen case доказано:

- `value_key -> source_value_ref` является bijection для visible semantic
  targets;
- `structure_key -> exact node_identity` является bijection, когда
  structural key нужен;
- `type_key -> input_type_id` является bijection;
- `choice_key -> typed_option_id` является bijection;
- каждый mapping row указывает на реально существующий model-view JSON
  pointer;
- каждый видимый primitive leaf имеет ровно одну field-source row;
- content hash каждой field-source row совпадает с exact rendered leaf;
- каждый compiled role binding находится ровно в одной части:
  visible relationship или backend-only binding;
- presentation and option permutation identities детерминированы.

Эти проверки доказывают reconstructable exact mapping на packet-receipt
boundary. Они не выполняют V2 Choice parsing/normalization и не доказывают
restore/replay; эти слои остаются `NOT_IMPLEMENTED_NOT_RUN`.

Перестановка исторического `slim_choice_order` не меняет V2 candidate и его
receipt. Это отделяет новый Context V2 от прежнего Slim diagnostic surface.

## 11. Semantic hierarchy

Отдельные focused fixtures проверяют шесть важных веток только через
существующий PacketFactory:

| Ветка | Доказанный результат |
| --- | --- |
| canonical table lineage | `document -> table -> row -> values` |
| row без `table_ref` | `document -> row -> values` |
| Gate 1 text projection | `document -> text segment -> values` |
| ambiguous structural target | bounded `evidence group`, без угадывания row |
| interleaved source order между двумя rows | hierarchy группируется детерминированно; literal occurrence/ref coverage остаётся exact |
| только unbound source references | fail closed: `financial_semantic_context_v2_visible_hierarchy_empty` |

Fallback не создаёт ложную точность. Если exact reference нельзя однозначно
связать с одним row/text segment, renderer создаёт читаемый evidence group и
сохраняет exact association/lineage private.

## 12. Tamper и collision handling

Закрытые guards проверяют:

- candidate hash и exact minified UTF-8 size;
- `active=false`;
- `provider_calls_total=0`;
- receipt identity links;
- receipt integrity hash;
- Pack/Registry/catalog projection pins;
- readable-name collisions;
- duplicate source refs;
- invalid source structure;
- invalid choice/type links;
- incomplete binding partition;
- missing field-source provenance;
- invalid necessary-reference targets.

Публичный Context V2 material validator независимо пересобирает exact candidate
и весь receipt из Registry, Evidence Bundle, Compilation и managed projections,
после чего требует exact dataclass equality. Публичный
`validate_financial_semantic_v6_packet` поверх этого повторно строит весь
packet из Registry, Evidence Bundle, source package и Compilation.

Поэтому отклоняются:

1. изменённый candidate даже после пересчёта candidate hash;
2. изменённый receipt даже после пересчёта его собственного integrity hash;
3. receipt field, перенаправленный на другой существующий authority pointer;
4. necessary reference, перенаправленный на другую существующую structure.

Private exact renderers не являются validation authority; caller должен
передавать validated packet. До будущего provider request дополнительный
complete-request fail-closed барьер обязан добавить Context Linter V2.1.

## 13. Managed asset evidence

Пины неактивного managed family:

```text
FAMILY: broker_reports_gate2_financial_domain_assets@1.1.0
FAMILY_MANIFEST_SHA256: 4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d
RUNTIME_ACTIVATION: false
REGISTRY_SHA256: 0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8
PACK_INTEGRITY_SHA256: ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8
PACK_PROJECTION_SHA256: 08c59bac807e27980c6902d282a0e000f1ceb81d14d761ff0c8c249b4f2f988f
REASON_CATALOG_SHA256: d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15
REASON_PROJECTION_SHA256: 817c1f555b8d97c1547483815b7266efa0777ec272190b87e2bc500e97955071
DECISION_CODE_CONTRACT_SHA256: e9d7ce23c0c73c1d2907755c1495688dc64d7d3a02135c1fdb16316f184866af
CANDIDATE_ASSET_PAYLOAD_SHA256: 99be5272ebab4e69e2533391f381bd27682496148f760e1e4a171f9e7162cdad
GENERATED_RUNTIME_PROJECTION_SHA256: b8e3f5855eed9850d8f46356ff5eb4bf6623694d4a600aec89e09e92ba713e19
```

Build-time validation доказывает, что human wording приходит из managed
assets, а не из packet, runner или adapter Python.

## 14. Проверки

Выполнены:

```text
MODEL_ASSET_BUILD_CHECK: PASSED
GENERATED_BUNDLE_PARITY: PASSED
RUFF_CHANGED_PYTHON: PASSED
FOCUSED_INTEGRATION_SUITE: 85 PASSED
FULL_SERVICE_SUITE: 1907 PASSED, 20 SKIPPED, 5 WARNINGS, 630.66 SECONDS
GIT_DIFF_CHECK: PASSED
FRESH_LOCAL_DIFF_REVIEW: APPROVED_NO_FINDINGS
PROVIDER_CALLS: 0
```

Focused suite включает:

- active bytes и packet identity на 10 frozen cases;
- Context V2 determinism;
- complete type set в zero-choice cases;
- literal occurrence parity;
- отсутствие nulls, backend/global identities и canonical `_vN` IDs в
  model view;
- local-key bijections;
- field-source totality и content hashes;
- exact binding accounting;
- exact material rebuild и self-consistent tamper rejection;
- шесть hierarchy branches;
- single-loader/closed-world architecture checks;
- unchanged default active assets и unchanged historical V5 projection;
- отсутствие V2 sidecars в request/provider/evidence persistence paths.

Ни один тест GOAL 4 не вызывает provider.

## 15. Privacy

Repository-safe report содержит только:

- synthetic case IDs;
- counts;
- schema/asset identities;
- hashes;
- byte sizes;
- test outcomes.

Он не содержит:

- credentials;
- provider response IDs;
- customer literals;
- exact customer refs;
- internal filesystem paths;
- raw provider envelopes;
- hidden reasoning traces.

Private Context V2 candidate и mapping receipt могут содержать exact synthetic
evidence при локальном вызове explicit private renderer, но автоматически в
Git не сохраняются.

Для future actual corpus:

- exact model-facing customer context остаётся вне Git;
- exact mapping/evidence receipt остаётся вне Git;
- repository-safe report связывается с private evidence только hashes;
- private evidence retention/replay остаётся backend-owned.

## 16. Что этот GOAL не доказывает

Не реализовано и не заявлено:

- V2 local Choice profile/parser;
- V2 response schema;
- Context Linter V2.1;
- sealed complete request;
- provider-specific request projection для V2;
- provider compatibility;
- response parsing или reason normalization для V2;
- alias restoration через runtime Choice;
- V2 response/end-to-end materialization;
- evidence persistence/restore/replay;
- exact report projector для provider run;
- model quality;
- expected-answer validity;
- token/cost/latency;
- benchmark compatibility;
- production activation;
- GUI publish/readback/rollback.

Контекст построен, но не отправлен модели.

## 17. Finish contract

| Требование | Результат |
| --- | --- |
| existing packet authority builds active context | `PASSED`, bytes unchanged |
| existing packet authority builds non-active V2 | `PASSED` |
| private mapping/evidence receipt | `PASSED` |
| second builder | `0` |
| V2 aliases deterministic | `PASSED` |
| emitted value/structure/type/choice local-key ↔ private exact identity mappings | `PASSED`; evidence-reference resolution may intentionally be many-to-one |
| every semantic literal exact/once per source occurrence | `PASSED` |
| semantic hierarchy preserved | `PASSED` |
| option reconstruction exact | `PASSED_AT_PACKET_MAPPING_RECEIPT_BOUNDARY`; V2 Choice normalization `NOT_IMPLEMENTED_NOT_RUN` |
| unclassified retention exact | reason-code view retained at packet boundary; active/code-owned source-retention regression `PASSED`; Context V2 source restoration/replay `NOT_IMPLEMENTED_NOT_RUN` |
| tampering fails closed | `PASSED` |
| provider calls | `0` |
| canonical documentation current | `PASSED` |

## 18. Continuation

После fresh review, зелёных checks, APPROVED и merge этого отдельного PR может
начаться только GOAL 5 — Minimal Model Surface Contract.

GOAL 5 должен:

- зафиксировать полный allowlist model-visible полей;
- зафиксировать полный список запрещённых по умолчанию полей;
- объяснить необходимость каждого разрешённого поля;
- дать representative human-readable examples;
- сохранить runtime changes `0`;
- не вызывать provider.

GOAL 5 не реализует linter, projection или activation. Context Linter V2.1 и
budget guard принадлежат только GOAL 9 после minimal projection и non-active
Context V2.1 в GOAL 7 и GOAL 8. До принятия этих successor contracts Context
V2.0 нельзя подключать к request builder.

## 19. Repository-safe receipt

[BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.receipt.safe.json](./BROKER_REPORTS_GATE2_MANAGED_SEMANTIC_CONTEXT_GOAL4_NON_ACTIVE_CONTEXT_V2.receipt.safe.json)
