# GOAL584: серверный путь через LiteLLM

10.11.2026. **Ревью и config-preparation slice готовы; весь GOAL ещё не завершён.**
База3095c506, рабочая ветка agent/goal584-single-gateway. Текущая запись и остатки —
[employee-budgets-goal584.md](../../infra-ops/employee-budgets-goal584.md).
GUI, production cutover, платные API и реальные финансовые изменения исключены.

## Что установлено

| Область | Проверенный результат |
|---|---|
| Денежная authority | Просмотренная бюджетная обвязка не создаёт второго денежного состояния. Users/keys/расход/резервирование/лимиты принадлежат LiteLLM. Admin policy предлагает подтверждаемые cap values, reader отображает native spend. |
| Старый connection preparation | Сохраняет Responses0 напрямую и переводит только CC1/2/4; использует master bearer для старого транспортного bootstrap. Это не готовый профиль денежных бюджетов. |
| Native entrypoint | OpenWebUI0.12.2 request Filters выполняются в process_chat_payload; низкоуровневый generate_chat_completion сам этот этап не запускает. Наличие native helper не доказывает наследование signing. |
| Штатные subagents | Идут через CHAT_COMPLETION_HANDLER и наследуют filter IDs/context. Служебные title/tags/follow-up используют существующий service Pipe и отдельного плательщика. |
| OCR | Внешний loader переносит файл и user, но не chat/answer root. OCR намеренно использует raw native Responses для сохранения status/refusal. Замена на полный chat handler изменила бы результат и не восстановила отсутствующую связь. |
| Broker | Есть maintained direct provider adapters и отдельная economy policy. Их нельзя автоматически объявлять штатным общим путём. Фактические Broker Functions/модели сейчас выключены; перед активацией потребуется согласовать owner/dispatch. |
| Личный баланс | Native DTO содержат cap/spend/duration/reset/blocked. Готового employee-self monthly-balance entrypoint не найдено. Cost answer/chat не заменяет месячный остаток; unknown witness не доказывает отсутствие неизвестных расходов или доступность денег для нового запроса. |

## Read-only runtime snapshot

Проверка10.11.2026, 19:08МСК: private owner assertion и SQLite query-only.
Ни model inference, ни изменение конфигурации не выполнялись.

- OpenAI API включён; direct connections и Ollama выключены.
- Пять enabled keyed connections: Responses0 — direct provider; CC1/2/4 — LiteLLM;
  CC3 — другой, пока не классифицированный endpoint без configured model IDs.
  Пустой список настроенных IDs сам по себе не доказывает, что подключение не используется.
- Luna OCR active, extraction engine external, loader настроен.
- Семь установленных Broker Functions и Broker Workspace Models inactive.
  Установленный dictionary Tool не имеет native active flag; его фактический вызов
  этим срезом не установлен.
- Бюджетные Functions в текущем runtime не установлены; перенос ещё не выполнен.

Два первых bounded reads остановились на предпосылках диагностического helper;
это не неисправности production. Третья проверка исключила ненужное чтение Function
content и завершилась. Всего3SSH, каждый менее10s; provider calls0/config writes0.
Сохранились safe receipts, включая ошибки. Секреты, private URL и Function content
в этот отчёт не перенесены; runtime source hashes не квалифицированы.

## Минимальное изменение подготовки

В существующий [prepare_google_gateway.py](../../../deploy/openwebui-upgrade-0122/prepare_google_gateway.py)
добавлен явный managed mode с защищёнными approved native config/env inputs.
Он готовит pending configuration, не применяет её и не запускает контейнеры.
Вместо mixed Workspace/Pipe `/api/models` используется native `/openai/models`.

Все enabled native UI connections, включая Responses, направляются в прежний
LiteLLM service. Сохраняются API type, prefix, IDs и metadata templates. WebUI
получает shared inference bearer; master/operator/provider credentials отдельно.
Неоднозначные active entries, несовместимые aliases/цены, credential overrides и
fallback приводят к отказу подготовки. Неактивные slots очищаются полностью,
исходные настройки остаются в protected source snapshot для согласованного отката.
Native config копируется точно: новых тарифных расчётов, provider payload builder
или финансового хранилища нет. Extra approved embedding/audio entries не превращаются
в UI chat models. Legacy CC bootstrap сохранён отдельно от managed mode; ошибки
managed mode не переключают исполнение на legacy.

Root исправил два обязательных замечания независимого review:
legacy-only Usage callback мог пропустить CC streaming policy; оба stream peers
теперь обязательны, legacy handler и повторы запрещены. Disabled connection мог
сохранить provider Authorization в headers; теперь pending config содержит только
enable=false, исходный snapshot не меняется.

Продолжение source review после6cf74f71 выявило B3: callbacks установлены, но
Responses alias с отсутствующим/true supports_native_streaming проходил подготовку.
Runtime guard для такого профиля записывает not_run; это подтверждено существующим
native component case. Managed Responses теперь требует прежний квалифицированный
OpenAI-compatible buffered-upstream профиль: mode=responses,
supports_native_streaming=false, openai/<wire model> и отсутствие другого custom
provider override. WebUI SSE/Tools и содержимое запросов не меняются. Проверка
ограничена matched UI aliases, extra approved embedding/audio rows не затронуты.

## Проверки и границы доказательства

9 focused unittest PASS, включая33 negative projection subcases, за0.020s.
Проверены all-enabled projection, protocol/prefix preservation, native-vs-Workspace
catalog, exact approved config bytes, separated credentials, hidden inactive keys,
однозначность aliases/цен и отсутствие apply/start. Native GET/Docker/POSIX metadata
явно заменены boundary fixtures; реальные protected inputs не использовались.
TemporaryDirectory автоматически удалены. Независимый source review: PASS только
этого config-preparation slice. Новый CI/DB/provider/GUI прогон не запускался.

Модельный request body этот срез не принимает и не перестраивает. Прежние принятые
доказательства native CC/Responses Usage, ledger/блокировки и delegate context
переиспользуются на неизменённых runtime sources. Они не объявляют новый OCR путь
проверенным. Все факты нового runtime snapshot — configuration inventory,
а не продуктовая приёмка нового маршрута.

## Патчи и обязательный остаток

[Реестр](../../infra-ops/patch-registry.md) ссылается на существующие manifests,
installer/verifier owners, известные upstream issue/PR и условия снятия патчей.
Для существующих OpenWebUI0.12.2 overlays отдельно отмечено source-build known /
current runtime UNVERIFIED. Новых core patches этого GOAL нет.
Подготовлены [безопасные upstream drafts](GOAL584_LITELLM_UPSTREAM_DRAFTS.md);
публикаций не было.

**Плательщик OCR выбран пользователем: служебный бюджет платформы.** В исходниках
добавлена операция `document_ocr` к существующему подписанному service scope с
реальным File ID и запустившим распознавание actor. Chat/answer root не создаётся.
Common настройки платформы вынесены из service Pipe в уже существующий общий
модуль; OCR и фоновые задачи читают одного владельца конфигурации. OCR сохраняет
raw native Responses, File ACL и полный PDF/instruction/schema. Шлюз выбирает
служебное native назначение по проверенной подписи, включая native Responses с
пустым TASK; неподписанные и неподходящие вызовы не проходят к провайдеру.

При неизвестной Usage существующая проверка блокирует соответствующий native
ключ модели платформы. Личные ключи сотрудника и старые chat-service правила
не меняются; отдельного расчёта денег, журнала или core patch не добавлено.
Локально: 86 OCR/service Pipe тестов без пропусков; 50 provenance/auth PASS и один
optional pinned-native buffered admission skip в лёгком venv; шесть выбранных
проверок guard с настоящим LiteLLM1.105.1 PASS.
Фактический converter/Form из pinned WebUI0.12.2 исполнен: PDF, instruction и schema
сохранены, добавлен только carrier подписи. Внешние File/User/HTTP owners в этих
проверках заменены явными fixtures; это не native DB или продуктовая GUI-приёмка.
Остаток — ограниченная проверка новой финансовой связи на существующем стенде.

Также до реального включения необходимо классифицировать connection3, подготовить
approved native каталог/права/цены/лимиты и квалифицировать выбранный target.
Это не основание менять production в данном GOAL. Глобальная чистка63k строк
проверочного кода и разработка UI остаются отдельными задачами.

Подробные source reviews и safe receipts: local/goal584/single-gateway/.
