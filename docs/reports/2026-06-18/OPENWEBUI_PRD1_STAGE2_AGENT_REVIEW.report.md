# OpenWebUI PRD-1 Stage 2 Agent Review

Дата: 2026-06-18
Статус: инженерный review / замечания агента
Область: PRD-1, customer summary, Stage 2 engineering domain

## 1. Summary

Текущий контур Stage 2 стал существенно здоровее после синхронизации PRD-1, customer summary и
`docs/stage2/*`. Главный плюс: документ больше не продает "AI-платформу вообще", а удерживает Stage
2 как набор проверяемых рабочих сценариев, ADR и runtime proofs.

Моя основная позиция: PRD-1 можно использовать как source of truth для подготовки реализации, но еще
нельзя использовать как прямой список задач для немедленного кодинга. Перед implementation нужны
ADR, runtime proof и customer test data. Иначе самые рискованные места - STT proxy, manager
visibility, no-delete, OCR, web-search и provider catalog - быстро превратятся в неявные обещания.

## 2. Что считаю сильными решениями

### 2.1. PRD-1 наконец стал source of truth

Замечание:

Статус `customer-approved Stage 2 PRD / source of truth` правильный. Он убирает двусмысленность
между initial draft, customer summary, stage2 research и engineering backlog.

Обоснование:

- `docs/prd/OPENWEBUI_CORPORATE_CHAT_PRD_1.md` теперь явно ссылается на customer summary,
  engineering domain и research actualization.
- `README.md` ведет на PRD-1, summary, `docs/stage2/README.md`, roadmap, context index, domain map и
  research report.
- Это снижает риск, что будущий агент начнет работу по устаревшему enriched/refined draft.

Практический вывод:

Любая implementation-задача Stage 2 должна начинаться с PRD-1 и `docs/stage2/CONTEXT_INDEX.md`, а не
с переписки или старых черновиков.

### 2.2. Native-first позиция сохранена без самообмана

Замечание:

Правильно, что PRD говорит "native OpenWebUI first", но не обещает, что все требования закрываются
штатно.

Обоснование:

- Groups/RBAC, prompts, workspace models, knowledge, web-search и analytics действительно выглядят
  как natural OpenWebUI surface.
- Но STT video workflow, server-side STT proxy, manager visibility, no-delete и OCR/layout-aware
  pilot требуют проверок или ADR.
- Такая граница не закапывает здравое зерно OpenWebUI, но не выдает research findings за production
  proof.

Практический вывод:

На первом implementation этапе нужно отделять configuration-first slices от custom/integration
slices.

## 3. Главные замечания по рискам

### 3.1. STT/ffmpeg/proxy - главный технический риск Stage 2

Замечание:

Транскрибация теперь корректно включена в Practical Stage 2, но ее нельзя начинать как "просто
прикрутить ffmpeg и Lemonfox".

Обоснование:

- PRD фиксирует три границы: browser, server-side STT proxy, STT provider.
- Browser отвечает за file detection, local preprocessing, audio extraction/conversion,
  progress/cancel UX.
- Proxy отвечает за auth, permissions, API key handling, provider request, transcript normalization,
  errors, optional persistence/audit.
- Provider отвечает только за transcription/timestamps/speaker labels.
- Existing ffmpeg workflow признан technical asset, но artifact не лежит в репозитории, значит его
  API/output contract еще не проверен.

Риск:

Если начать с UI без STT proxy ADR, ключи, лимиты, хранение, ошибки и права доступа будут размазаны
между browser, OpenWebUI и provider. Это создаст хрупкую интеграцию и риск утечки STT API key.

Что нужно сделать:

1. ADR `STT proxy boundary`.
2. Проверить actual ffmpeg workflow artifact.
3. Зафиксировать accepted input/output contract: формат audio blob, max size, duration, MIME,
   retry/cancel behavior.
4. Сделать smoke на desktop и mobile до обещания сроков по large video.

### 3.2. Data masking правильно вынесен в future, но data policy нужна до provider setup

Замечание:

Решение не включать full data masking/tokenization в Practical Stage 2 правильное. Но это не
освобождает от data policy перед подключением провайдеров.

Обоснование:

- PRD честно говорит, что поверхностная подмена данных на теги создает ложное чувство безопасности.
- Реальная masking-система требует NER/local LLM, mapping storage, reversibility, leak tests, audit
  and trust boundary.
- Stage 2 все равно работает с финансовыми, налоговыми, персональными документами и транскриптами.

Риск:

Если provider setup начнется раньше data policy, команда начнет решать sensitive-data вопросы на
уровне "можно/нельзя" в каждом сценарии вручную. Это плохо масштабируется и создает неодинаковые
правила для OpenAI/Claude/DeepSeek/Yandex/GigaChat.

Что нужно сделать:

1. ADR или decision note `Data policy by provider class`.
2. Таблица allowed/prohibited data для foreign providers, Russian providers, local/self-hosted
   paths.
3. Отдельные warnings для broker reports, tax docs, meeting transcripts and web-search.

### 3.3. Manager visibility - продуктово важно, но юридически и организационно чувствительно

Замечание:

Доступ руководителей к рабочим чатам включен правильно, но формулировка должна оставаться очень
узкой: только рабочие чаты в рамках согласованных групп/рабочих пространств.

Обоснование:

- Stage2 domain map уже фиксирует риск: "руководитель видит слишком много".
- OpenWebUI groups/sharing не равны автоматическому supervisory access ко всем чатам подчиненных.
- Сотрудник должен понимать, какие чаты считаются рабочими и видимыми руководителю.

Риск:

Если сделать это через админские поверхности или грубую кастомизацию без policy, получится скрытый
просмотр личных/черновых чатов. Это не техническая фича, а privacy/security decision.

Что нужно сделать:

1. ADR `Manager visibility and no-delete policy`.
2. Customer-approved matrix: кто кого видит, какие сценарии считаются рабочими, что остается личным.
3. Test user matrix: admin, manager, employee in group, employee outside group.
4. Отдельно проверить audit/export вместо live visibility, если native model слабая.

### 3.4. No-delete не заменяет retention/audit

Замечание:

Technical check запрета удаления чатов нужен, но нельзя считать его полноценной политикой хранения.

Обоснование:

- PRD формулирует no-delete как проверку штатных возможностей OpenWebUI.
- Research допускает fallback: policy, backup/retention, audit/export, minimal patch.
- Даже если UI-delete отключается, остаются API behavior, admin actions, backup lifecycle and DB
  retention.

Риск:

Заказчик может воспринять "запрет удаления" как гарантию неизменяемого аудита. Это не одно и то же.

Что нужно сделать:

1. Проверить UI and API delete behavior для non-admin.
2. Описать retention: сколько хранятся chats, files, transcripts, exports.
3. Зафиксировать, является ли backup/audit достаточным fallback.

### 3.5. OCR/layout-aware PDF pilot стоит оставить pilot, не production

Замечание:

Включение OCR/layout-aware PDF pilot в Practical Stage 2 оправдано, потому что брокерские отчеты и
документы часто не являются чистым текстом. Но это должен быть именно pilot.

Обоснование:

- PRD прямо разделяет basic document handling, OCR/layout-aware pilot and production document
  workflow.
- Stage2 docs требуют реальные customer samples.
- OCR/table extraction quality невозможно принять без тестовых PDF: текстовый PDF, scan, PDF с
  таблицами, печатями/подписями, отчет/выписка/договор.

Риск:

Если на старте не ограничить pilot acceptance, OCR быстро превратится в production document
pipeline: очередь, layout parsing, validation UI, audit logs, human approval.

Что нужно сделать:

1. ADR `OCR pilot scope`.
2. Test data package до реализации.
3. Acceptance не "OCR работает", а "для каждого типа документа есть result или documented
   limitation".

### 3.6. Web-search для всех пользователей требует policy, иначе будет cost/privacy drift

Замечание:

Идея дать web-search всем пользователям разумна, но только с rules, result count, concurrency, cost
visibility and "when not to use" instruction.

Обоснование:

- Web-search работает с внешними провайдерами и может отправлять sensitive prompts.
- Brave `brave_llm_context` подходит как first pilot, но это foreign provider.
- Yandex Search API - отдельный search provider decision, его нельзя смешивать с YandexGPT/GigaChat.

Риск:

Без лимитов и policy web-search станет скрытым каналом утечки данных и неконтролируемых расходов.

Что нужно сделать:

1. ADR `Web-search provider`.
2. Customer approval: Brave vs Yandex Search vs deferred.
3. Smoke queries and prohibited-query examples.
4. Начальные result count/concurrency limits.

### 3.7. Provider catalog должен быть ADR до настройки провайдеров

Замечание:

Нельзя начинать подключать Claude/DeepSeek/Yandex/GigaChat как список ключей. Сначала нужен provider
model catalog.

Обоснование:

- `GPT-mini` пока остается бизнес-лейблом, а не exact model ID.
- Claude API / Claude models и Claude Code разведены правильно, но это нужно закрепить в catalog.
- DeepSeek aliases and pricing/model IDs могут дрейфовать.
- YandexGPT и GigaChat требуют выбора одного российского provider или разных ролей.

Риск:

Без catalog пользователи получат хаотичный список моделей, а администратор - неуправляемый
cost/security surface.

Что нужно сделать:

1. ADR `Provider model catalog`.
2. Для каждой модели: exact ID, provider, status, сценарии, data class, cost unit, owner, fallback.
3. Перед production setup перепроверить model IDs and pricing.

### 3.8. Basic analytics - правильный default, но без runtime proof это только гипотеза

Замечание:

Native analytics first - правильное решение. Hard billing/gateway не нужно тащить в Practical Stage
2 без явного требования enforceable budgets.

Обоснование:

- OpenWebUI analytics потенциально закрывает базовую visibility.
- Hard budgets, virtual keys, rate limits and guaranteed blocking - это gateway-class
  responsibilities.
- LiteLLM добавит ops/security/backup/rollback surface.

Риск:

Если deployed OpenWebUI analytics окажется слабее текущей документации, заказчик может не получить
ожидаемый cost visibility.

Что нужно сделать:

1. Runtime proof: two users, groups, models, several requests.
2. Проверить, видны ли token usage/model/user/group breakdown.
3. Если нет - documented decision: native-only enough, manual price catalog, or gateway ADR.

### 3.9. Оценка часов стала реалистичнее, но ее нужно держать как planning range

Замечание:

Диапазон Practical Stage 2 `144 / 212 / 304` часов выглядит более честно, чем ранняя оценка, потому
что scope вырос: STT proxy, OCR pilot, manager visibility, no-delete, provider catalog, data policy.

Обоснование:

- Ранний low baseline был уместен для lighter native-first configuration.
- Текущий Practical Stage 2 включает integration and proof-heavy work.
- Часть работ зависит от customer samples, provider keys and runtime access.

Риск:

Если воспринимать expected как fixed bid, scope начнет конфликтовать с blockers: customer test data,
actual ffmpeg artifact, deployed OpenWebUI proof, provider policy.

Что нужно сделать:

1. Перед коммерческой оценкой закрыть ADR и runtime proof для самых дорогих рисков.
2. Разделить fixed scope and variable options.
3. В договорной логике считать OCR/manager/no-delete/STT video как acceptance-bound slices, а не как
   open-ended feature bucket.

## 4. Замечания по порядку реализации

### 4.1. Нельзя начинать с кода

Обоснование:

Roadmap прямо говорит, что implementation начинается только после roadmap/blueprints/research/ADRs
review and approval. Это не бюрократия: без ADR технические границы не определены.

Рекомендуемый порядок:

1. ADR `STT proxy boundary`.
2. ADR `Provider model catalog`.
3. ADR `Web-search provider`.
4. Data policy decision.
5. Runtime proof: OpenWebUI capabilities, analytics, no-delete, manager visibility.
6. Test data package.
7. После этого implementation slices.

### 4.2. Первый implementation slice должен быть configuration-first

Обоснование:

Workspaces/RBAC/prompts/knowledge/model catalog дают ценность и проверяют OpenWebUI native surface
без тяжелой кастомизации.

Рекомендуемый первый slice:

- группы;
- 3 рабочих сценария;
- shared prompts/templates;
- workspace models;
- policy warnings;
- basic acceptance checklist.

Это даст рабочую базу, пока STT/OCR/provider ADR закрываются отдельно.

### 4.3. STT лучше делать отдельным module/slice

Обоснование:

STT затрагивает browser, media processing, proxy, provider, storage, errors, transcripts and
security. Это самостоятельный bounded context, а не настройка в existing chat.

Рекомендуемый результат slice:

- uploaded audio/video -> prepared audio -> proxy -> provider -> transcript -> templates;
- no API key in browser;
- clear file limits;
- retention policy;
- smoke on desktop and mobile.

## 5. Остаточные несостыковки и дрейф

### 5.1. Exact model IDs and prices remain unstable

Проблема:

PRD сохраняет финансовую таблицу и provider candidates, но pricing/model names are time-sensitive.

Обоснование:

Документы сами говорят, что тарифы нужно перепроверить перед commercial proposal and production
enabling. Это особенно важно для OpenAI/Claude/DeepSeek/Yandex/GigaChat.

Рекомендация:

Перед implementation не просто "перепроверить цены", а выпустить `Provider model catalog ADR` с
датой проверки, exact model IDs and approved account path.

### 5.2. Existing ffmpeg workflow is external to repo

Проблема:

PRD опирается на существующий ffmpeg workflow как technical asset, но artifact не находится в этом
репозитории.

Обоснование:

Research docs прямо фиксируют, что actual workflow artifact не inspected. Значит пока невозможно
доказать output format, browser support, performance and integration API.

Рекомендация:

Перед STT implementation импортировать или описать artifact contract: repo/path, supported inputs,
output format, browser matrix, licensing, versioning, core asset hosting.

### 5.3. Manager visibility and no-delete depend on customer policy, not only OpenWebUI

Проблема:

Технически можно проверить permissions, но нельзя технически решить, какие чаты руководитель имеет
право видеть.

Обоснование:

Это privacy/security boundary. Без customer-approved policy реализация может быть одновременно
"работающей" и неправильной.

Рекомендация:

Сначала policy and test matrix, потом настройка или patch.

## 6. Мой итоговый verdict

PRD-1 как source of truth сейчас пригоден для implementation planning. Его сильная сторона - честное
разделение Practical Stage 2, ADR-required boundaries and future slices.

Но readiness к реализации пока частичный:

- готово к planning: workspaces/RBAC/prompts, provider catalog ADR, web-search ADR, STT proxy ADR,
  data policy;
- готово к runtime proof: OpenWebUI capabilities, analytics, no-delete, manager visibility;
- blocked by customer input: broker reports, OCR/customer docs, group matrix, provider/data policy;
- not ready for implementation as a single batch: STT, OCR, manager visibility, no-delete, hard
  billing, data masking.

Самое важное замечание: Stage 2 нельзя реализовывать как один большой "развитие OpenWebUI" task. Его
нужно вести маленькими slices с proof gates. Иначе проект быстро смешает продуктовые обещания,
OpenWebUI capabilities, custom integration, security policy and provider procurement в один
неуправляемый ком.

## 7. Рекомендуемый next action

1. Создать ADR `STT proxy boundary`.
2. Создать ADR `Provider model catalog`.
3. Создать ADR `Web-search provider`.
4. Создать decision note `Data policy by provider class`.
5. Провести runtime proof deployed/staging OpenWebUI.
6. Запросить customer test data package.
7. После этого сформировать implementation backlog по slices.

## 8. Non-goals для этого отчета

- Не запускалась реализация.
- Не менялся production.
- Не подключались provider.
- Не читались `.env` или secrets.
- Не обновлялись цены через интернет.
- Не менялись compose/env/scripts.
