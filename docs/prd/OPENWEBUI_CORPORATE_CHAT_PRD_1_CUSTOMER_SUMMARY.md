# OpenWebUI Corporate Chat Stage 2 Customer Summary

Статус: customer-facing summary
Источник: [OPENWEBUI_CORPORATE_CHAT_PRD_1_REFINED.md](OPENWEBUI_CORPORATE_CHAT_PRD_1_REFINED.md)
Changelog: [OPENWEBUI_CORPORATE_CHAT_PRD_1_REFINED_CHANGELOG.md](OPENWEBUI_CORPORATE_CHAT_PRD_1_REFINED_CHANGELOG.md)
Назначение: согласование Stage 2, объема работ и предварительной оценки трудозатрат

## 1. Что такое Stage 2

Stage 2 - это превращение текущего OpenWebUI-чата в управляемую рабочую среду.

Цель не в том, чтобы просто подключить больше моделей. Цель - дать сотрудникам готовые рабочие сценарии: с правилами, prompts, шаблонами, доступами, инструкциями, понятными ограничениями и базовой видимостью расходов.

## 2. Что входит

В Practical Stage 2 входят:

- рабочие пространства под типовые задачи;
- группы пользователей и доступы;
- общие prompts/templates/knowledge;
- модельный каталог и правила выбора моделей;
- транскрибация аудио/видео через адаптацию существующего ffmpeg workflow;
- server-side STT proxy, чтобы API-ключи не попадали в браузер;
- брокерские отчеты / 3-НДФЛ как рабочий сценарий с ручной проверкой;
- web-search для всех пользователей, но с правилами, лимитами и cost visibility;
- базовая работа с PDF/DOCX/XLSX;
- OCR/layout-aware PDF pilot на реальных документах;
- проверка доступа руководителей к рабочим чатам;
- проверка запрета удаления чатов для обычных пользователей;
- policy допустимых данных и warnings;
- basic analytics / cost visibility;
- user/admin docs и acceptance checks.

## 3. Приоритеты заказчика

Приоритеты Stage 2:

1. Транскрибация.
2. Брокерские отчеты.
3. Web-search.

Группы пользователей:

- админы;
- РО;
- менеджеры ОС / ОП / КО / БО;
- специалисты / бухгалтеры ОВ / ИТС / АУП / БО / ТО.

AI-методологи и владельцы шаблонов:

- администраторы системы;
- руководители отделов, групп или рабочих пространств.

## 4. Как будут выглядеть рабочие пространства

Рабочее пространство - это не просто папка.

Это готовая рабочая зона под задачу:

- кто имеет доступ;
- какая модель используется;
- какие prompts доступны;
- какие инструкции/knowledge подключены;
- какие шаблоны документов есть;
- какие правила безопасности действуют;
- какие примеры хороших запросов есть;
- какие рабочие чаты создают сотрудники.

Правильный паттерн:

- правила, prompts, templates и knowledge общие;
- рабочие чаты индивидуальные внутри общего сценария;
- руководитель может видеть рабочие чаты своей группы, если это предусмотрено политикой доступа.

OpenWebUI не позиционируется как полноценный файловый сервер или документооборот. Общие документы для сценариев допустимы: инструкции, шаблоны, методички, примеры, approved prompts.

## 5. Как будет работать транскрибация

У исполнителя уже есть проверенный ffmpeg workflow для обработки мультимедиа. Он стабильно работает на desktop и mobile. Поэтому транскрибация не считается велосипедом с нуля: готовый workflow адаптируется в корпоративный OpenWebUI-портал.

Схема:

1. Пользователь загружает аудио или видео в GUI.
2. Браузер локально определяет multimedia file.
3. Через ffmpeg/wasm workflow браузер извлекает аудиодорожку и приводит ее к нужному формату.
4. Подготовленный audio blob отправляется в server-side STT proxy внутри OpenWebUI-контура.
5. Proxy проверяет пользователя, права, лимиты и размер файла.
6. Proxy добавляет STT API key и отправляет файл в Lemonfox или другой выбранный STT provider.
7. Результат возвращается в UI.
8. Пользователь применяет шаблон: протокол, задачи, решения, резюме, follow-up.

Важно:

- API-ключи не передаются в браузер;
- STT provider вызывается только через server-side proxy;
- Lemonfox - приоритетный STT provider candidate;
- это изолированный transcription module / integration slice, а не глубокий fork всего OpenWebUI;
- главный риск теперь не ffmpeg, а интеграция с OpenWebUI: UI, proxy endpoint, права, хранение результата, шаблоны и обновляемость.

## 6. Что с PDF/DOCX/XLSX и OCR

PDF, Word и Excel нельзя считать простым текстом.

- DOCX содержит структуру, стили, таблицы, комментарии, track changes и вложения.
- PDF часто является визуальной страницей, а не логическим документом.
- XLSX содержит листы, формулы, типы данных, скрытые строки, merged cells, сводные таблицы и внешние ссылки.

В Practical Stage 2 входит базовая работа с PDF/DOCX/XLSX и OCR/layout-aware PDF pilot на реальных документах заказчика.

PDF нужно классифицировать:

- текстовый PDF;
- скан;
- PDF с таблицами;
- PDF с печатями/подписями;
- отчет/выписка/договор.

Цель OCR pilot - понять, что можно закрыть в Stage 2, а что требует production document pipeline. Production-grade OCR/layout pipeline не обещается в базовом Stage 2.

Для тестов нужны реальные примеры: простой брокерский отчет, отчет с таблицами, PDF, XLSX при наличии, скан/сложный PDF при наличии и пример хорошего результата из текущей схемы в Claude API / Claude models.

## 7. Что с web-search

Web-search нужен всем пользователям, но не как бесконтрольная кнопка.

В Stage 2 нужно:

- выбрать provider;
- описать правила использования;
- задать result count/concurrency settings;
- показать стоимость request;
- дать инструкцию, когда web-search использовать нельзя;
- ограничить дорогие или рискованные сценарии через policy и группы;
- сделать cost visibility для администратора.

## 8. Что с доступом руководителей к чатам

В Practical Stage 2 включается проверка и настройка доступа руководителей к рабочим чатам сотрудников в рамках назначенных групп и рабочих пространств.

Ограничение: это не означает автоматический просмотр всех личных или черновых чатов.

Нужно описать policy:

- какие рабочие чаты видны;
- кому они видны;
- в каких сценариях;
- видит ли сотрудник это правило;
- логируется ли просмотр;
- что делать, если OpenWebUI не поддерживает нужную модель нативно.

Если нативных возможностей недостаточно, варианты: штатная настройка, policy, audit/backup/export, минимальная кастомизация или deferred custom implementation.

## 9. Что с удалением чатов

Заказчик хочет запретить удалять свои чаты всем кроме админов.

В Stage 2 нужно проверить, поддерживает ли OpenWebUI это штатно. Если штатно возможно - настроить или описать настройку. Если штатно невозможно - зафиксировать ограничение и предложить вариант: policy, backup/audit, export, минимальная кастомизация или отдельный patch.

Реализацию нельзя обещать без проверки deployed version и permission model.

## 10. Что с AD/SSO

AD/SSO не принципиален именно в этом этапе.

В Practical Stage 2 оставить discovery/optional:

- проверить возможные схемы OIDC/OAuth/LDAP/trusted header/SCIM;
- описать mapping групп;
- выбрать pilot path, если заказчик решит включать SSO;
- не тянуть full AD lifecycle / SCIM в базовый Stage 2.

## 11. Что с basic analytics / hard billing

Для Practical Stage 2 ориентируемся на basic analytics / cost visibility.

Это значит:

- видеть usage по пользователям/моделям, если OpenWebUI это дает;
- иметь price catalog;
- понимать стоимость LLM tokens, web-search requests, STT hours и storage/files;
- ограничивать дорогие модели группами;
- фиксировать решение, достаточно ли native analytics.

Hard billing/gateway - отдельное решение. Если нужны virtual keys, hard budgets, rate limits, guaranteed blocking и единый router по providers, это отдельный gateway slice, например LiteLLM.

## 12. Что с подменой данных на теги

Идея правильная, но это не простая find/replace операция.

Полноценная автоматическая подмена данных на теги требует отдельного доверенного контура:

- локально принять исходный текст или документ;
- распознать чувствительные данные;
- заменить их на теги;
- сохранить защищенную карту соответствий;
- отправить во внешнюю модель обезличенный контекст;
- получить ответ;
- выполнить обратную подстановку внутри доверенного контура;
- защитить карту маппинга;
- логировать обработку;
- проверить, что данные не утекли мимо тегов.

Для качественного распознавания ФИО, счетов, ИНН, паспортов, адресов, сумм, договоров, компаний и других сущностей может потребоваться локальная LLM или специализированный NER/entity extraction module.

Если сделать подмену поверхностно, она создаст ложное чувство безопасности. Поэтому сейчас фиксируем правила допустимых данных, warnings, ручные рекомендации по обезличиванию и roadmap, а полноценную автоматическую подмену выносим в отдельный защищенный этап.

## 13. Какие провайдеры включаем/исследуем

Для корпоративного чат-портала нужен Claude API / Claude models. Claude Code - отдельный dev/agentic coding tool, не обычный provider для OpenWebUI-чата, и не входит в Practical Stage 2 без отдельного dev-agent сценария.

Провайдеры:

- Claude API / Claude models;
- GPT-mini как основная или fallback модель;
- DeepSeek как обязательная альтернатива;
- YandexGPT и GigaChat исследовать и выбрать одного российского provider;
- Lemonfox как приоритетный STT provider;
- web-search provider выбрать по качеству, цене, лимитам и доступности.

## 14. Что не входит в базовый Stage 2

Не входит автоматически:

- full data masking/tokenization subsystem;
- local LLM/NER for sensitive data;
- full AD lifecycle / SCIM;
- hard billing/gateway;
- production-grade OCR/layout pipeline;
- complex Excel parser;
- production DOCX/XLSX generation;
- deep OpenWebUI fork;
- full document management/storage;
- полноценный RAG по всем документам компании;
- агентная система с действиями в 1С/CRM;
- гарантия идеальной обработки любых PDF/DOCX/XLSX.

## 15. Оценка часов

Оценка дана в часах. Она не включает стоимость LLM/API, web-search, STT, сервера, хранения и подписок. После discovery диапазоны нужно уточнить по фактической версии OpenWebUI, доступам, провайдерам и требованиям заказчика.

| Блок | Min hours | Expected hours | Max hours | Входит в Base | Входит в Practical | Входит в Extended | Комментарий |
| ---- | --------: | -------------: | --------: | ------------- | ------------------ | ----------------- | ----------- |
| Discovery и проверка OpenWebUI capabilities | 6 | 10 | 14 | Да | Да | Да | Версия, Groups/RBAC, file upload, STT, web-search, Analytics, deployed limitations. |
| Workspaces, groups, roles | 10 | 16 | 24 | Да | Да | Да | Рабочие пространства, группы, доступы, роли пользователей, owner model. |
| Prompts/templates/knowledge | 10 | 16 | 26 | Да | Да | Да | Общие prompts, templates, approved instructions, examples. |
| Provider catalog | 8 | 12 | 20 | Light | Да | Да | Claude API/models, GPT-mini, DeepSeek, YandexGPT/GigaChat selection. |
| Web-search for all users | 8 | 12 | 18 | Light | Да | Да | Provider, limits, result count, concurrency, инструкция, cost visibility. |
| Transcription module | 18 | 30 | 48 | Light audio | Да | Да | Existing ffmpeg workflow, audio/video preprocessing, server-side STT proxy, Lemonfox. |
| Broker reports / 3-НДФЛ pilot | 10 | 16 | 24 | Да | Да | Да | Реальные примеры отчетов, warnings, manual review. |
| Basic PDF/DOCX/XLSX handling | 10 | 16 | 24 | Да | Да | Да | Простые документы и честные limitations. |
| OCR/layout-aware PDF pilot | 8 | 14 | 24 | Нет | Да | Да | Discovery + pilot, не production document pipeline. |
| Manager access to work chats | 6 | 10 | 18 | Нет | Да | Да | Policy, штатные возможности, audit/export/customization options. |
| Chat deletion restriction check | 3 | 6 | 10 | Нет | Да | Да | Проверка штатного запрета удаления, fallback policy/patch option. |
| Data policy and masking roadmap | 6 | 10 | 16 | Да | Да | Да | Warnings, allowed data, future data masking subsystem note. |
| Basic analytics / cost visibility | 6 | 10 | 16 | Да | Да | Да | Native analytics, price catalog, no hard gateway promise. |
| AD/SSO optional discovery | 3 | 6 | 10 | Нет | Light | Да | Не full AD lifecycle / SCIM. |
| User/admin docs and acceptance | 10 | 16 | 24 | Да | Да | Да | Инструкции, smoke/acceptance, handoff. |
| Coordination and buffer | 10 | 16 | 24 | Да | Да | Да | Уточнения, приемка, feedback cycle. |

| Вариант | Min hours | Expected hours | Max hours | Что входит |
| ------- | --------: | -------------: | --------: | ---------- |
| Base Stage 2 Lite | 104 | 148 | 208 | Управляемое ядро, 3 сценария, web-search light, broker/doc pilot, transcription light без полного video/large-file контура, без OCR pilot и manager/chat deletion custom work. |
| Practical Stage 2 | 144 | 212 | 304 | Рекомендуемый вариант: рабочие сценарии, группы, prompts/templates, transcription audio/video на базе existing ffmpeg workflow, Lemonfox/STT proxy, broker reports, web-search всем, базовые документы, OCR/layout-aware PDF pilot, provider evaluation, manager access/check, chat deletion check, basic analytics, docs, acceptance. |
| Extended Stage 2 | 220 | 320 | 480 | Больше сценариев, глубже OCR/document тесты, больше provider smoke, больше polishing, больше access-control work и возможные минимальные кастомизации. |

Optional slices оцениваются отдельно и не включаются в Practical Stage 2 автоматически:

| Optional slice | Min hours | Expected hours | Max hours | Когда нужен |
| -------------- | --------: | -------------: | --------: | ----------- |
| Full data masking/tokenization subsystem | 56 | 88 | 140 | Если нужна автоматическая подмена чувствительных данных на теги с картой маппинга и обратной подстановкой. |
| Local LLM/NER for sensitive data | 40 | 72 | 120 | Если нужно локально распознавать ФИО, ИНН, счета, паспорта, адреса, договоры и другие сущности. |
| Full AD lifecycle / SCIM | 32 | 56 | 96 | Если нужен lifecycle пользователей/групп, а не только discovery/optional SSO. |
| Hard billing/gateway | 32 | 56 | 90 | Если basic analytics недостаточно и нужны hard budgets, virtual keys, rate limits, guaranteed blocking. |
| Production-grade OCR/layout pipeline | 64 | 112 | 180 | Если pilot показывает существенную долю сканов/сложных PDF и нужна промышленная очередь обработки. |
| Complex Excel parser | 40 | 72 | 120 | Если нужны формулы, несколько листов, сводные таблицы, внешние ссылки и точные расчеты. |
| Production DOCX/XLSX generation | 32 | 60 | 100 | Если нужны утвержденные шаблоны, controlled export, версии и проверка результата. |
| Deep OpenWebUI fork | 80 | 140 | 220 | Если isolated integration slices недостаточно и нужен устойчивый fork lifecycle. |
| Full document management/storage | 80 | 140 | 240 | Если OpenWebUI хотят превратить в корпоративное файловое хранилище/документооборот. |
