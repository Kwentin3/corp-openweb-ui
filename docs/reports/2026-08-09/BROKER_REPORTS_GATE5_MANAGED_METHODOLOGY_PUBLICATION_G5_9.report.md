# Broker Reports Gate 5 — Managed Tax Methodology Publication (G5.9)

Date: 2026-08-09

Goal status: `G5.9_CLOSED`

Research outcome: `NOT_JUSTIFIED_YET`

Architecture verdict: `REPOSITORY_AUTHORITY_STILL_CHEAPER`

Product status: `INACTIVE`

## Verdict

Нет. В текущем repository/OpenWebUI stack не найден готовый дешёвый owner,
который одновременно даёт:

```text
editable candidate
-> publish exact (methodology_id, methodology_version)
-> immutable historical bytes
-> trusted exact-version read after reopen
```

Наиболее близкий existing primitive — OpenWebUI Prompt history. Он полезен как
редактируемый каталог с access control и version history, но в pinned
OpenWebUI `v0.9.6` не является append-only immutable publication store.
Создание non-production candidate всё равно изменяет current Prompt row, а
history entry можно удалить отдельно; удаление Prompt удаляет всю его history.

Чтобы закрыть эти gaps, понадобился бы новый Tax-specific publisher/resolver,
semantic-version registry, duplicate/CAS guard, authenticated API integration и
операционные запреты/backup guarantees. Это уже дороже текущего G5.8 seam.

Поэтому G5.8 остаётся текущей cheapest correct architecture:

```text
repo JSON + exact pinned hash + application deployment
```

G5.9 не добавляет runtime code, persistence или новый authority owner.

## Research boundary

Проверены:

- G5.8 package resource, trusted authority factory и G5.7 composition;
- pinned OpenWebUI `v0.9.6` Prompt, Prompt History, Skill и Tool models/routes;
- existing Broker Reports atomic stage release scripts и managed asset
  manifests;
- existing `DocumentPassportPromptResolverFactory`;
- STT `PromptCatalogFactory` и его read-only SQLite adapter;
- ArtifactStore/ArtifactResolver scope и proven G5.3 use;
- repository-managed immutable/versioned patterns.

Не выполнялись live publication, OpenWebUI mutation, deployment или product
activation: research доказал отсутствие требуемой immutable boundary до того,
как managed experiment мог стать корректным.

## Repository findings

### A. G5.8 baseline

G5.8 имеет одного trusted owner:

```text
Gate5TrustedMethodologyAuthorityFactory.create
```

Он разрешает closed caller reference только через repository-owned map:

```text
(methodology_id, methodology_version)
-> package resource
-> exact raw SHA-256
-> validated methodology
-> unchanged G5.7
```

Одна published identity связана с одним exact hash. Caller не передаёт bytes,
path или hash. Missing identity и resource tampering fail closed. Для новой
версии нужны repository edit, build и deployment, но не нужны DB, network
client, credentials, ACL, CRUD или lifecycle service.

### B. Cheapest managed candidate: OpenWebUI Prompt history

OpenWebUI Prompt — самый близкий existing managed surface:

- Prompt имеет owner/access grants, active flag и `version_id`;
- initial create создаёт history snapshot и указывает на него `version_id`;
- content update создаёт новый history entry;
- `is_production` решает, передвигать ли production pointer;
- API умеет читать history entry и переключать current version.

Но его фактическая semantics не удовлетворяет G5.9:

1. `is_production=false` не создаёт изолированный draft. Update сначала
   записывает новые `name/content/data/meta/tags` в current Prompt row, commit,
   и только затем создаёт history. Не меняется лишь production `version_id`.

2. Published history не immutable. Write-authorized user/admin может удалить
   отдельный history entry. При удалении Prompt удаляется вся history.

3. `version_id` — opaque history UUID, а не уникальный
   `(methodology_id, methodology_version)`. Existing model не запрещает двум
   snapshots заявить одну semantic methodology version.

4. Version switch восстанавливает snapshot обратно в mutable current row. Это
   rollback/edit behavior, а не exact-version trusted resolution contract.

5. Existing Broker Reports Prompt resolvers читают только active current row:
   `DocumentPassportPromptResolverFactory` и STT `PromptCatalogFactory` не
   разрешают immutable history version по methodology identity.

6. Existing atomic stage release работает с current Function/Prompt SQLite
   rows и exact rollback snapshots. Он не публикует Prompt History и сам
   является software deployment contour.

7. Прямое чтение/запись OpenWebUI SQLite из Gate 5 повторило бы OpenWebUI DB
   schema, bypassed его API/access boundary и добавило runtime coupling. Это не
   дешёвое переиспользование existing owner.

Таким образом, stock Prompt history может хранить candidate snapshots, но не
может быть принят как trusted immutable Tax Methodology authority без новой
надстройки.

### Остальные existing primitives

| Primitive | Полезное свойство | Почему не закрывает G5.9 |
| --- | --- | --- |
| OpenWebUI Skill | managed content, active flag, access grants | update in place; version/history/published immutable read отсутствуют |
| OpenWebUI Tool | managed content, access grants | update in place; это Python Tool owner, version/history отсутствуют |
| STT Prompt Catalog | isolated factory, read-only access checks, prompt hash | STT-specific; читает mutable current Prompt row, не history version и не пишет |
| Document Passport Prompt resolver | existing OpenWebUI Prompt read owner | читает active current row по id/command; не methodology publication/history |
| atomic stage release | exact current-row update/readback/rollback | release-oriented direct SQLite contour; history не создаёт, deployment не устраняет |
| managed asset manifests | semantic versions и exact repository hashes | остаются repository/build/deployment-bound |
| ArtifactStore | immutable artifact id, access/lifecycle machinery | authority — authenticated user/case artifact; нет system-published methodology namespace, uniqueness или append-only publisher |
| Canonical/versioned case objects | strong immutable case evidence | принадлежат document/case lifecycle и не являются generic system content registry |

Переиспользование этих owners путём смены их domain semantics создало бы
неявного второго владельца или ослабило их current scope.

## Concrete gap

Минимальный корректный managed contour потребовал бы добавить все следующие
обязанности, которых сейчас нет у одного existing owner:

1. validate structured methodology candidate до publication;
2. атомарно зарезервировать уникальный `(methodology_id, methodology_version)`;
3. сохранить exact bytes/hash append-only;
4. запретить overwrite и delete published version либо детектировать их как
   fail-closed authority breach;
5. разрешать exact semantic version, не mutable current row и не caller bytes;
6. выполнять authenticated publish/read через supported OpenWebUI boundary;
7. поддерживать backup/restore и operational readback этого нового trusted
   state;
8. связывать resolved bytes/hash с unchanged G5.7/G5.8 result.

Stock Prompt API даёт candidate/history storage, authenticated access и read
по opaque history id как editable catalog mechanics, но не их trusted
immutable semantic-version form. Добавление недостающих частей уже означает
новый publication owner и security/operations boundary.

## Options comparison

| Variant | Moving parts | Operational result | Decision |
| --- | --- | --- | --- |
| A. G5.8 repo resource | JSON, closed id/version map, exact hash pin, existing build/deploy | exact, closed-world, reproducible; новая version требует software release | current direction |
| B. OpenWebUI Prompt history + Tax adapter | existing Prompt DB/history/ACL plus new publisher, API credential path, exact-version resolver, semantic uniqueness, hash binding, delete/tamper guard, backup/readback | deployment мог бы исчезнуть, но stock immutability недостаточна | `NOT_JUSTIFIED_YET` |
| C. Methodology persistence/platform | new table/model, migration, CRUD, ACL/RBAC, lifecycle, UI/service, operations | может дать полный lifecycle | вне текущей боли и бюджета |

Variant B нельзя честно назвать «один existing Prompt». Нужные дополнительные
части и есть отдельная managed publication subsystem, пусть и небольшая.

## Cost / Architecture verdict

### Current baseline

G5.8 имеет три conceptual moving parts:

```text
one JSON resource
+ one closed id/version -> resource/hash binding
+ existing application package/deployment
```

Цена: для v2 нужны repository edit/review, application build и deployment;
developer/release involvement остаётся.

### Cheapest managed candidate

Самый дешёвый найденный вариант использует OpenWebUI Prompt DB/history/ACL, но
реально дополнительно требует:

```text
Tax Methodology publisher/validator
+ authenticated OpenWebUI API client/credential boundary
+ semantic id/version uniqueness registry or equivalent CAS
+ exact history-version resolver and hash binding
+ published-delete/tamper enforcement
+ backup/restore and readback procedure
+ API/schema drift tests and support
```

Новая отдельная DB/table/UI не обязательны, но отсутствие этих компонентов не
делает contour дешёвым: authority, security и operations responsibilities всё
равно новые.

### Benefit

После реализации такого contour могли бы исчезнуть:

- repository resource edit для каждой compatible methodology version;
- application build;
- application deployment.

Developer involvement исчезнет только после создания и сопровождения
publisher/operator tooling; stock Prompt UI сама по себе не гарантирует
structured validation или immutable semantic publication.

### New costs

Взамен появляются:

- stateful OpenWebUI runtime dependency в trusted calculation pre-boundary;
- API credentials и новый security boundary;
- network/API/schema failure modes;
- uniqueness, concurrency и tamper/delete semantics;
- backup/restore и disaster-recovery dependency;
- новый owner, tests, monitoring/readback и long-term support;
- риск смешения LLM Prompt lifecycle с tax methodology authority.

Для одного experimental methodology family эта стоимость выше доказанной
пользы отказа от deployment.

### Verdict

```text
REPOSITORY_AUTHORITY_STILL_CHEAPER
```

## Why no representative v2 was published

Managed success criteria требовали, чтобы published contents нельзя было
тихо overwrite/delete и чтобы `(id, version)` однозначно разрешался после
reopen. Stock OpenWebUI Prompt mechanics не обеспечивают эти инварианты.

Создать v2 в Prompt table и показать happy-path read означало бы доказать
только storage, а не trusted immutable publication. Такой тест дал бы ложный
положительный результат. Поэтому managed write не выполнялся, а новая
publication boundary не реализована.

G5.8 focused replay повторно подтверждает, что current baseline остаётся
рабочим и fail-closed.

## Verification

```text
G5.7 + G5.8 deterministic/trusted contour: 8 passed
STT current-row PromptCatalog owner:           6 passed
existing atomic stage release owner:          20 passed
runtime/product/OpenWebUI state mutations:     0
new DB/table/service/ACL/UI:                    0
```

Source inspection additionally confirmed:

- Prompt candidate update mutates current row before history creation;
- production pointer movement is separate from current content mutation;
- individual history entries and complete Prompt history are deletable;
- Skill and Tool models are mutable current records without equivalent
  immutable publication history;
- current repository Prompt readers do not resolve a semantic methodology
  version from Prompt History.

## Evidence

- [G5.8 contract](../../stage2/contracts/BROKER_REPORTS_GATE5_TRUSTED_METHODOLOGY_AUTHORITY.v0.md)
- [G5.8 trusted authority/runtime](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_trusted_methodology.py)
- [Document Passport Prompt resolver](../../../services/broker-reports-gate1-proof/broker_reports_gate1/document_passport.py)
- [STT Prompt catalog](../../../services/stage2-stt/stage2_stt/prompt_catalog.py)
- [atomic stage release remote owner](../../../services/broker-reports-gate1-proof/scripts/broker_reports_atomic_stage_remote.py)
- [OpenWebUI Prompt model, pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompts.py)
- [OpenWebUI Prompt History model, pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/prompt_history.py)
- [OpenWebUI Prompt routes, pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/routers/prompts.py)
- [OpenWebUI Skill model, pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/skills.py)
- [OpenWebUI Tool model, pinned v0.9.6](https://github.com/open-webui/open-webui/blob/v0.9.6/backend/open_webui/models/tools.py)

## Final answer and stop condition

На текущей инфраструктуре публикацию compatible Tax Methodology можно было бы
отделить от deployment только ценой нового publication authority вокруг
OpenWebUI. Existing primitives не сохраняют одновременно immutability,
semantic identity authority и exact-version reproducibility почти бесплатно.

Итог: `G5.9_CLOSED`, `NOT_JUSTIFIED_YET`,
`REPOSITORY_AUTHORITY_STILL_CHEAPER`. G5.8 repository-versioned authority
подтверждён как current direction. Следующий Gate 5 slice не начат.
