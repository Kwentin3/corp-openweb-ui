# GOAL #584: бюджеты сотрудников и стоимость чата

Актуальная запись на 10.11.2026. Аудит завершён, рефакторинг разрешён.
**Весь продукт ещё не принят; production не менялся.**
Источник: [issue #584](https://github.com/Kwentin3/corp-openweb-ui/issues/584).
[Ограниченный аудит](../reports/2026-11-09/GOAL584_KISS_AUDIT.md).

## Результат и границы

LiteLLM — единственный владелец денег, денежных лимитов и SpendLogs.
Общая серверная интеграция связывает каждый вызов с сотрудником, чатом и ответом,
включая помощников. Новый конвейер на общем пути не требует своего финансового
кода. Сотрудник видит стоимость ответа и накопленную стоимость чата; администратор
меняет лимиты через готовую форму в чате с серверной проверкой прав и подтверждением.
Месячные бюджеты, доли по моделям и отдельный служебный плательщик сохраняются.
Неизвестная Usage означает неизвестный расход и блокировку только данной модели
для данного сотрудника. Подтверждённый ноль отличается от неизвестного.

Разрешены изменения исходников и проверки на изолированном стенде. 10.11 пользователь
отдельно разрешил узкую поправку сохранения исходной Usage до нормализации, только
на стенде, без deployment, новых журналов и новой тестовой инфраструктуры.
Ранее разрешённый стендовый calendar-floor patch остаётся отдельным неизменным
срезом двух функций. Прочие патчи ядра не подразумеваются.
Production, платные API, реальные тарифы/лимиты, deployment и изменение рабочих
маршрутов требуют отдельного согласования; его нет. Office/Tasks/Skills/Files/STT,
контекст модели, reasoning, права и данные сохраняются.

## Политика работы

- Существующий компонент → штатная возможность → тонкая адаптация → новый код
  только при доказанном разрыве. Один владелец состояния, обновляемое ядро.
- Достаточные проверки выбирать по изменению и продуктовому результату. Старые
  fixtures/gates — evidence, не автоматически новый договор. Принятые проверки
  повторять только при изменении значимых входов или появлении новых оснований.
- Подробные receipts хранить в артефактах, обновлять эту единственную запись.
  Независимые задачи делегировать небольшими проверяемыми срезами.
- После GOAL отдельно разобрать разрастание тестовой инфраструктуры: глобальный
  backlog, без превращения этого разбора в условие текущей поставки.

## Принято и сохранено

Аудит09.11: около4066строк собственного продукта,35677tests и26337proof/CI.
Native LiteLLM владеет spend/reservation/quotas; общий Filter/Auth/reader добавляет
привязку и отображение. Второго ledger и финансового кода по конвейерам нет.
Не относящийся к задаче WIP в MAIN и соседних рабочих копиях сохранён.

Status «Ответ / Чат» показывает начисленное на указанное UTC время; явное pending
добавляет «учёт обновляется». Удалены has_delegation и просмотр названий tools.
Девять целевых существующих проверок PASS; запрос/auth/stream не менялись.
Known0 требует native cost0, полную исходную Usage, успешный guard и защищённые
явные цены. Missing/default/unpriced0 остаётся UNKNOWN. Audit descriptor опционален,
ценовая квалификация имеет одного владельца. Целевые существующие проверки PASS.
Денежный proof связывает native строку по полному scope/call_id; request_id opaque.
Зависимость от формата provider ID убрана; native owner/key/model/rates/caps
проверки сохранены,12целевых случаев PASS.

[Known0 run42784099623](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42784099623),
source ee885845: ordinary CC/nonstream принят по native строке, reader, Details,
reload, foreignGET401/Action404 и actual PNG. Usage/spend0, native_zero_confirmed;
caps/oldrows/provider/context сохранены, cleanup0. CI FAIL относится к последнему
bookkeeping-флагу native_tasks_terminal; native task_ids[] уже подтверждён.
Исправлены только2строки finally (aaf8d135); ради зелёного CI повтор не запускался.
Artifact13748167860,784053B/61members,
SHA7c90bace7293885e54b1c8a40077ab493b81f91d458ece2dda7249b65c780b2a.

Положительный делегированный сценарий принят отдельно от полного workflow:
[run42792989666](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42792989666),
source15234064. Actual Sol6×.20=$1.20, Terra6×.02=$.12, employee/ответ/чат=$1.32;
service1×.20 — отдельный плательщик. Native scope/rows/keys/rates/Usage/counters,
caps/oldrows,12call reader, saved reasoning/context/tools/native task_ids[]
проверены до последующей ошибки DOCX proof. Actual browser PNG показывает обе1.32.
CI остаётся FAIL; quota/refusal/recovery в этом run пропущены и не приняты.
Artifact13753521948,721110B/65members,
SHAa70061d91da92964ec090ddcb97e7998fb89b403e3787a322179503879cc21a1.

DOCX proof ошибочно считал служебные изменения OfficeCLI порчей документа.
Исправлен только verify_artifacts: узкий whitelist фактических custom properties,
w14IDs/empty edited pPr/redundant xml:space; прочее содержимое/оформление сравнивается.
На неизменных actual source2305B/SHA2fd1e87f… и result3243B/SHA01a80193… старый
verifier воспроизвёл RED, исправленный GREEN. Существующая проверка порчи таблицы
также PASS0.32s; новых cases/framework/CI нет. Это package comparison, не новая
приёмка browser/ACL. Процессы завершены, исходники финансового proof не менялись.

Повторно используются прежние evidence в неизменных границах: Native48
(run41718501504) — caps/refusal/recovery/adminwrite/retention; Office81
(run42238631735,gpt5.4mini) — buffered upstream Responses с native WebUI SSE/Tools,
parent.80/service.40 и reload. Это не приёмка всего текущего кандидата.
Выключение stream в WebUI мешает native Tools и не является этим профилем.

## Текущий разрешённый срез: streaming Usage

Raw SDK draft меняет одну функцию OpenAIChatCompletion.make_openai_chat_completion_request,
до SDK coercion сохраняет request-local признак и точные исходные счётчики Usage.
Он передаёт прежние данные прежнему SDK, не меняет расчёт денег, Usage или контекст.
PatchSHA9e77444f4e8a77e0ebc343861775c6a0748e28b58c3e95176ba3dd68a481fade.
Фактическая репетиция на cached OpenAI2.54.0/LiteLLM1.105.1:6/6PASS,4.234s,
positive/true0/absent/null/partial/string0, chunks/request/tools совпали до/после,
Logging reuse reset подтверждён, outbound0, SDK unchanged, оставшихся PID0.
Это проверка механизма SDK, не exact image/proxy/DB/UI/cancellation acceptance.
Cached SDK — reference, не SBOM образа; actual image exports ещё нужны.

Guard candidate (+89/−2) использует прежнюю employee/model policy через native
post-call callback; default регистрация не менялась. Два opt-in peer выбираются
штатным callback manager; на прямом пути одна telemetry-запись на протокол.
Named registry возвращает первый peer: эквивалентность иных name-based consumers
не заявляется. Native patch затрагивает raw factory и два lifecycle-файла:
partial cleanup вызывает существующие eligible success guards, cancel без ответа —
существующий full failure hook один раз. Он пишет native failure row; reader уже
отвергает такие суммы. Точный admin Usage-reason зависит от сохранённых metadata;
без него сумма недоступна, а не известна/нулевая. Обычный error hook не дублируется,
native возврат резервов не перемещался. При иных guardrails cancel lifecycle
расширяется и на них; стендовая композиция ограничена нашими двумя peer.
Core patch SHA029e55760d4b35b7b6803e8ecefaef96edea5dd7e19c622e2d948c4e9898bfdf.
Изменения ещё не установлены, не собраны и не приняты в actual image.

Существующие builder и identity получают отдельный opt-in stream вариант,
проверяющий3native targets/8SDK файлов. Floor patch/manifest/LICENSE и прежние
prepare/load_manifest/two-function validator сохранены; identity расширен явно.
В existing test_unknown_usage_guard добавлены3метода (+151строка): actual SDK
zero/missing, cancel до/после первого chunk, read error; private marker не подделывается.
Это компонентная проверка с fixture auth/admin HTTP, не приёмка DB/UI.
Короткий dispatch stream-usage в existing native workflow пропускает37шагов
и pricing/calendar jobs, не создаёт новых jobs/framework. Bounds20min job,
10min builder,4min component; ресурсная граница8GiB disk/3GiB RAM, native test
container2GiB/2CPU/256PIDs/networknone. Native tokenizer cache готовится отдельно
без model calls. Cleanup адресует только exact-run label и проверенный built IID.
YAML/31embedded Python bodies/actionlint PASS; default inference bodies сохранены.
Следующий шаг — закончить source qualification и один ограниченный запуск exact
image. Новых ledger, журналов, SSE wrapper и тестовых framework не создавать.

Первый короткий [run42803219466](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42803219466)
на122b4078 завершён FAIL до patch/build/components: actual image содержит
OpenAI2.33.0/Python3.13.16/HTTPX0.28.1, reference rehearsal использовал SDK2.54.
Все3native исходника совпали; SDK version/pins не совпали. Upgrade не выполнялся.
Cleanup exact-run containers0, builtIID отсутствует, иных backend/UI jobs не было.
Artifact13757102706,1488B/2members,
SHAc1001d581976407b3a895d8e5f0ebe081d81f5c61e76afbadada83961cad184d.
ZIP скачан1раз, privateURL удалён. Следующий шаг — сверить официальный SDK2.33
с actual8source hashes и адаптировать reference pins без обновления runtime.
Сверка завершена: официальный PyPI wheel2.33.0 (1,162,695B,
SHA03ac37d70e8c9e3a8124214e3afa785e2cbc12e627fbd98177a086ef2fd87ad5)
побайтово совпал по всем8файлам с образом. Критические stream builder/parse/
ModelBuilderProtocol и integer Usage AST совпали с reference2.54; изменены только
sdk.version/files_sha256 manifest. Core patch и запрос неизменны, SDK не установлен
и не обновлялся. Повтор6case алгоритма не нужен; следующий5case native component
проверяет actual image2.33. ManifestSHA2f781c13ecc1580e7f26af60c494bd3eecb1ff974b8bdada69af628263754ea4.

Run42804096354 на7d147ee2 собрал и проверил exact variant/SDK2.33:
IIDsha256:4e90449df1319c59512e251c6b2a538bc06d6429d24be7e7d662ec4b2c05a91b.
Пять component methods выполнены17.005s; весь run FAIL. Legacy buffered Responses
и nonstream CC PASS, actual CC read-error и cancel до первого chunk также прошли
свои assertions. Cancel-after не дошёл до продукта: fixture повторно передал
start_time из предыдущего failure request. EOS дошёл до правильного события,
но fixture ожидал Responses worker queue вместо native CC async-success callback.
Исправлены только fresh request snapshot и наблюдение Event существующего Sink;
прежний timeout3s сохранён, private flags/callbacks не подменялись. Дополнительно
CC failure использует существующий native should_run_guardrail (+2строки),
чтобы сохранить protected admin optout; проверка добавлена в прежний error метод.
В том же EOS методе добавлен positive40/8/48; новых test methods/framework нет.
Следующий запуск повторяет только3новых CC methods;2legacy PASS используются
на неизменном native image/source. Artifact13757218630,7774B/5members,
SHAb58315d247f855ca31a8ddb621101d70327ccf78b3fadbf5babdc05e3c019b55.
Скачан1раз/privateURL удалён; exact-run containers0, builtIID удалён.

[Run42806131855](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/42806131855)
на8eb3ad06 завершён SUCCESS:3новых CC methods,12.194s, включая positive/zero/missing,
cancel до/после первого chunk, error/admin optout. Actual SDK/Router/Logging,
request/tools/stream сохранены, block/readback адресует только employee/model,
native refund/dispatch ownership сохранён. Это component acceptance с fixture
auth/admin/storage leaves; новой DB/UI приёмкой он не является. Root сверил
10build source hashes с Git blobs точного commit, native3targets/SDK8 и удалённый
IIDsha256:5b3a4b8a02b91540399abf5a13c9e743d493c9e7659a191edb78ac9db59f429e.
Actual Linux/Git-LF streammanifestSHA20dc1df2d351d8b38ae4a4ce4c6347e4af1f56516ba66421437a6edf5af20748;
2f781c13 выше — raw Windows CRLF того же JSON, а не хэш Linux-артефакта.
Artifact13758557469,7214B/5members,
SHA68ff38e22b14112ef3253d92a56471a15f826f2ef71b9ce4d9b1671723ca2bab,
скачан1раз/privateURL удалён; owned containers0, image удалён.
Native failure writer source принимает BaseException и принудительно маркирует
failure; reader отвергает числовой0 такой строки. Actual cancel DB row не
наблюдалась; повторного журнала или synthetic response не создаётся.

Финальная упаковка добавляет только2exports в существующий budget_runtime;
старый handler сохранён. Последняя компонентная проверка должна выбирать новые
exports через actual native get_instance_fn, чтобы проверить именно поставляемую
регистрацию, а не собранные отдельно fixture объекты. Core/image/SDK не меняются.

## Поставка и обязательные оставшиеся шаги

Подготовлены20строк budget_runtime.py, opt-in
[Compose overlay](../../compose/openwebui.employee-budgets.compose.yml) для тех же2сервисов
и [установка/откат](employee-budgets-installation.md). Новых services/DB/networks/volumes
и proof imports нет. YAML/import closure/source review PASS. Docker CLI локально
недоступен: Compose merge и actual image imports ещё не приняты.

Read-only production10.11: WebUI0.12.2/LiteLLM1.105.1; Responses connection0 идёт
прямо к провайдеру, CC1/2/4 к текущему LiteLLM, connection3 другая/не классифицирована.
Budget Functions не установлены; DB/custom_auth/callbacks LiteLLM не настроены.
Общий бюджетный контур не активирован; финансовый ущерб не установлен.
Маршруты/caps/services/modelcalls не менялись. Native browser лишь синхронизировал timezone.

1. Закрыть generic streaming unknown policy, включая ошибки и прерывание, на стенде;
   сохранить уже принятые known/zero/Responses и общий owner.
2. Достаточно подтвердить форму → учёт/отображение → отказ/восстановление на
   текущей композиции, применяя старые evidence в их границах. Native48 доказывает
   enforcement/recovery, actual427929 — child→тот же employee/model key.
   Текущий auth выбирает child model key и вызывает тот же native validator;
   BudgetExceededError пробрасывается. С positive run этот admission путь не менялся.
   Это обоснованный вывод по композиции evidence, не PASS пропущенного Terra-negative.
   Отдельный дорогой Office-negative не становится условием готовности без новой
   изменённой границы или явного требования к worker error UI. Оно не наблюдалось.
3. Подготовить единую сборку/профиль маршрутов и проверить installation/rollback;
   сохранить DB/Redis/SpendLogs/keys, согласовать production cutover отдельно.
4. Сохранить полезный WIP/evidence и убрать свои временные ресурсы в пределах допусков.
   Последние CI terminal/cleanup0. Автоматическая проверка дважды отклонила удаление
   owned artifact-bookkeeping-proof/pytest-owned: «blocked by policy», иных причин нет.
   Папка сохранена, обход не выполнялся; очистка остаётся явным незакрытым пунктом.

Основные evidence: local/goal584/kiss-refactor-2026-11-10/ (runtime-known-zero-native-default,
runtime-delegation-cost-resource,artifact-bookkeeping-proof,stream-usage-fix,
reused-acceptance.md,release-packaging-review.md). Исторические failures/sourcepins
сохранены там и в Git; предыдущая длинная запись также сохранена в local evidence.
Это receipts, не параллельные планы. Повторять весь Office ради зелёного CI не требуется.
