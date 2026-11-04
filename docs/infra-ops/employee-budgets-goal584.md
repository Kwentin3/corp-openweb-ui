# GOAL #584: бюджеты сотрудников и стоимость чата

Текущая запись работы, 04.11.2026. Источник требований и полномочий —
[issue #584](https://github.com/Kwentin3/corp-openweb-ui/issues/584).
Заказчик согласовал начало работы в этом чате. Коммерческое описание —
[редакция 4](../commercial/planning/TOKEN_LIMITS_CUSTOMER_PROPOSAL_2026-10-20.md).

**Состояние:** GOAL в работе; полный продукт ещё не принят. Native48 завершён
SUCCESS: main/WebUI/overlap/Responses и оба calendar профиля приняты в указанном
bounded scope по actual artifacts, independent review и parent replay. Проверен
разрешённый stand-only derivative двух функций LiteLLM. Native45 остаётся
исходным FAIL с подтверждённым false denial. Следующий срез — версии/источники
тарифов. Штатная автопроверка справочника принята на Native48; в primary
подготовлен следующий source-кандидат проверки публикации версий тарифов.
Production не менялся. Подробности текущего среза ниже, после решения владельца.

**Pricing catalog: source и ограниченный runtime Native48 приняты.**
Используются native source/status/schedule/reload APIs и scheduler LiteLLM;
отдельного расписания, расчёта цен или журнала не добавлено. Dedicated pricing
project проверил первый due poll с interval1h, переход synthetic S1→S2,
отказ502 на invalid/truncated без изменения принятого native source/status,
отмену своего interval и cleanup. Прошедший первый poll не доказывает второй
цикл через час. Thin callback сохраняет whitelist защищённого descriptor
рядом с native billed rates в той же SpendLogs row; публикация/активация
версии этим не доказывается. Unsupported/anonymous/client-only контекст — unknown.
Local423 harness PASS/0skip;239 component checks (232PASS/7opt-in skips).
Independent wiring review и parent повтор:31 attestation/12profile/9startup/
6cleanup/7handoff cases,51Bash/25embeddedPython/27inlinePython/actionlint PASS.
Исторические C1 (скрытые OpenAPI routes) и C2 (final writer маскировал primary)
в source исправлены; текущие coordinator/test SHA48b0f928/7a3b5c0a.
Corrected independent C1/C2 review и parent повтор6 actual-body checks PASS.
Evidence: `local/goal584/native-pricing-{descriptor-independent-readiness,
catalog-independent-readiness,wiring-corrected-readiness}.*`,
`native-pricing-catalog-native-corrected-readiness.*`, `candidate-checks.safe.json`.
Version publication не входил в Native48; следующий source-срез описан ниже.

**Native48 завершён, четыре jobs SUCCESS.** Head
`0fccfc4f39ab06fb8e69e5d4eb27f2b4029661e1`, tested merge
`6202495ae6e2cd72a4500cb2e84a0b99d9608f6a` материализован; diff между ними пуст.
[41718501504](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41718501504):
pricing job126204716667, main126204716149 и оба calendar jobs SUCCESS;
Active CI149/41718501527 SUCCESS. Pricing ZIP
`1bc4c18a47ec2a6a40677afb804defb7d3f42c53020c4b22a105e5380a206c3d`
проверен по GitHub digest и распакован:5 safe files,23 source bindings,
37 observations/80 API records; first new S1 fetch и persisted last_run,
затем S2, два502, cancel и cleanup0/0/0. Independent acceptance и parent replay PASS;
second elapsed-hour cycle и tariff publication этим не доказаны.
Parent replay basic PASS:26sources/12mounts/10native,4sweeps/2calls,
next5.414s<60; ZIPcc4286660ff112f9fa6707f92743b5d8e419e1e9b6e096c214b941ac67c81916.
Parent replay positive-floor276checks PASS:26sources/10helpers/12mounts/18native,
critical3.839s<5; ZIP58fad3f26f30bd1e41c41853be545838fbc2a5d4617ef086c1605caf8a849ad1.
Оба calendar cleanup0/0/0. Reused accepted financial/source assertions сохранены,
заменены только exact head/merge/run/job/ZIP bindings с recorded source hashes:
`local/goal584/replay_native48_calendars.py`, соответствующие replay-adaptation
и parent-replay/replay.safe.json. Main также принят в bounded regression scope:
ZIP `317d99f89490957c1c6bb0ada63f94d0f48142729596843dcfcde63667b2107b`,
223файла/51distinct source bindings, full-input replay admin/bootstrap/employee/
cost/background/RAG и19отклонённых мутаций. Independent reviewer просмотрел54PNG;
parent повторил оба replay и проверил фактический экран Responses Details.
Main cleanup подтверждает containers[]/volumes[], без утверждения о networks.
Evidence: `local/goal584/native48-main-review/independent-acceptance.md`.

**Следующий кандидат: публикация двух synthetic tariff versions.** Существующий
pricing job последовательно проверит v1/S1→v1/S2→v2/S2: три native списания
0.20/0.20/0.40, итог0.80, сохранность полных старых SpendLogs rows и context.
v1/v2 имеют разные native deployment IDs и защищённый descriptor в той же row;
явный индивидуальный прайс не должен меняться при reload справочника.
Конечный publisher меняет только synthetic config, перезапускает только proxy
и восстанавливает исходные байты; это не atomic HA activation и не новый billing.
В primary integrated source/test SHA0552f143/a4399694, workflow73890308.
Independent readiness и parent повтор PASS:23focused/0skip, joined actual prepare/
profile/approve/drain с внешними IO doubles,8Host mutations и13handoff cases.
14Compose binds, существующий attestation, source/image/cleanup/privacy проверены;
реальные native тарификация/сохранение/восстановление этого среза ещё не приняты.
Итоговые локальные проверки:446harness PASS/0skip и239component checks
(232PASS/7opt-in skips), actionlint и diff-check PASS.
Evidence: `local/goal584/native-pricing-versions-integrated-readiness.{md,py,safe.json}`.

**Native49: новый version milestone FAIL, причина пока не установлена.**
Head `e716be6011e0d6e1f88096bcc270191b636f46bc`, tested merge
`5a9cdb08f7acce453340d3c18822bbd75dee523d` (diff пуст),
[run41794979455](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41794979455).
Pricing job126456836858: catalog gate SUCCESS, version step FAIL на call_v1_S1
с `version_worker_failed`/вложенным `version_external_failure`; v1 publication,
identity и S1 reload прошли, но ни одного financial success packet нет, v2 не достигнут.
Зафиксированы original config bytes equal/restoration failures[] и cleanup0/0/0.
ZIP pricing `de1f30b6a6d407f2de8fa6ced88e891781f8cf9da9b536349607945e2c719514`
проверен по actual GitHub digest. Общий safe code скрывает несколько разных причин;
HTTP/provider/native billing причиной не объявляются. Следующий узкий diagnostic
source-срез сохраняет только whitelist типа исключения и source basename/line
в failed worker packet: без exception text, locals, полных путей и новых API-вызовов.
25focused и448harness PASS/0skip; independent safe-FAIL review и parent повтор
4cases PASS. Source75bb6a43/test891ef79c; product/native core не меняется,
runtime ещё не повторён. Evidence дополнительно:
`local/goal584/native49-pricing-review/diagnostic-readiness.{md,py,safe.json}`.
Оба calendar jobs49 SUCCESS; parent replay basic/floor PASS,276floor checks,
next5.300s<60/critical2.707s<5; оба cleanup0/0/0. Main49 SUCCESS,
independent acceptance и parent replay PASS в bounded regression scope;
весь run49 остаётся FAIL. Main ZIP84b93929883a01fe467d70ece57c4a1e6d572f3ca67f4b7d2d7a3b9d819347f4,
221файл/51distinct source bindings,19negative mutations отвергнуты.
Final actual cost snapshot07→08 перепривязан по unchanged producer poll contract
(7→8 settled rows), financial/source assertions сохранены.
Evidence: `local/goal584/native49-pricing-review/`,
`local/goal584/replay_native49_calendars.py`.

**Native50: весь run FAIL из-за pricing; main и оба calendar SUCCESS.** Head
`cf65dbb74d467a790fe100868bfb165dd35815ac`, tested merge
`66fb3016a529e888335533e7ab13edd44b5491be` (diff пуст),
[run41796542677](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41796542677),
pricing job126461885284. Active CI151/41796542865 SUCCESS. Catalog gate PASS,
version step FAIL; actual safe packet показал AttributeError в verified_row220:
проверка вызвала .get у вложенного descriptor=None. Причина недоступности descriptor
в callback ещё не установлена; гипотезы об auth/Router/Logging проверяются отдельно.
Source50 меняет только диагностику proof, тесты и эту запись; product/native core
остаются теми же. Original config bytes restored/failures[], pricing cleanup0/0/0.
Main bounded regression принят independent review и parent replay: ZIP
42ab9248fc206ba387a77de92f402b6cb0af0b9f9abf7017d0349ff6f679669e,
221файл/51distinct source paths,6builder/6mounts,19negative mutations;
полные finance/context inputs сохранены. Final cost snapshot08→07 обоснован
unchanged producer settlement loop (06has7/07has8 rows), assertions неизменны.
Main cleanup containers[]/volumes[], без claims о networks.
Следующий local proof fix проверяет оба dict до .get и сохраняет строгий FAIL
version_row_descriptor для unknown/None;26focused PASS/0skip. Это не исправление
потери descriptor и не приёмка тарифного milestone. Source fix ещё не опубликован.
Evidence: `local/goal584/native50-pricing-review/`,
`local/goal584/pricing-catalog-proof-41796542677/receipts/versions.safe.json`.

Native50 exact-source lifecycle replay не выявил неверной premise в guard:
Router stamp/get_litellm_params/Logging update/get_deployment сохраняют identity;
server credentials добавляются после отдельного snapshot body. Normal и server
credentials witnesses available; foreign copy/client body credential — unknown.
Следующий diagnostic contract: причина первого отказа → существующий callback
`_capture_descriptor` → фиксированный `DESCRIPTOR_UNKNOWN_REASONS`/unknown.reason
→ proof читает literal из защищённого callback и возвращает короткий safe FAIL.
Это representation-only observability; native cost/auth/quotas/guards неизменны.
Unknown остаётся FAIL, произвольный reason не выводится как текст ошибки.

**Следующий source diagnostic candidate:** callback c98239d6, его тесты cc59a8f7,
proof25bcca1b/test43e0c8e4, calendar helper pin17639392. Success shape и все
guard/billed-rates AST сохранены; unknown добавляет только один из13 fixed stages.
Proof неизвестный/None descriptor отклоняет явно; известный callback-owned reason
переводит в safe failure code, прочие строки не выводит. Frozen source hashes
сверены с Git index; fixtures читают candidate index вместо старого0fcc callback.
Локально450harness PASS/0skip и242component checks(235PASS/7opt-in skips),
34callback/27proof focused PASS. Runtime причины unknown ещё не установлен.
Independent source readiness и parent replay PASS:8 integrated CLI/restoration
cases,13 fixed reasons,26 source files/14 Compose binds; source mutations
отклонены, полный callback AST после удаления reason-only изменений равен50.
Это разрешение технической готовности к следующему isolated run, не приёмка
публикации тарифов. Evidence:
`local/goal584/native50-pricing-review/diagnostic-readiness.{md,py,safe.json}`.
Historical cause-replay50 теперь использует exact-Git TemporaryDirectory mirror
и повторён parent после изменения callback; его4 native witnesses неизменны.

Временный pricing-version author worktree закрыт после сохранения10raw файлов
в ZIP67630913393ff899559bd4eb4088875cb7beb3b40e07b3761f63d0c91904a429
и local branch `agent/goal584-pricing-version`/4f85db6fa7998d524ee6b647f0d9937db240f22b.
Это historical WIP, не итоговый кандидат; удаление native Git без force, readback
worktree/ref подтверждён. Receipt: `local/goal584/pricing-author-preservation/`.

**Native51: причина descriptor unknown сужена до штатного settings owner.**
Head9899de01d6d0893e6076c86b1954e4a711c7c3e8, exact tested merge
b6d6007b39b23127be35e6e0253dc93bfaef8384 (diff пуст),
[run41800293996](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41800293996).
Active CI152 SUCCESS. Pricing job126474119751 FAIL: catalog PASS37observations/
80API/26sources/13read-only mounts; versions FAIL на call_v1_S1 с точным
`version_descriptor_settings`, без прежнего null dereference. Actual artifact
13307463293 ZIP38f27a52d30db29237b631ae96a882a8e927a35b007ae7f13f7803489a2b0308
проверен по GitHub digest;10catalog и10version mutations отклонены.
Original config bytes restored/failures[], cleanup0/0/0. Полные financial packets
версий и второй тариф этим ещё не приняты. Evidence/replay:
`local/goal584/native51-pricing-review/`.

Оба calendar jobs51 SUCCESS. Independent acceptance: basic next8.830s<60,
floor critical1.848s<5;26exact-Git sources/12mounts на worker, native core/patch
неизменны, cleanup0/0/0,6financial mutations на каждый профиль отклонены.
Independent acceptance и parent повтор:
`local/goal584/native51-calendar-review/replay.py`.
Main51 SUCCESS; независимая проверка его artifacts пока выполняется.

**Следующий узкий callback fix:** native ProxyConfig после загрузки вызывает
`_bind_general_settings_store(self.settings)`; actual SettingsStore реализует
MutableMapping, не dict. Это существующий native owner, не новый state store.
Регрессия исполняет полные pinned settings_store/settings_rules/_descriptors и
exact native bind: старый callback отвергает два допустимых mapping-контекста
(36tests,2fails). Изменение только import Mapping и isinstance(settings,Mapping)
устраняет эти отказы:36focused PASS. YAML/DB precedence остаётся у native owner,
allow_client_side_credentials=true и не-mapping объекты по-прежнему unknown;
остальные guards и billed rates сохранены. Callback SHA7c36fb9d/testb81cd7e4;
три существующих source pins обновлены. Полный local runner450harness PASS/0skip,
244component checks(237PASS/7opt-in skips), новые future failure probes исключены.
Independent source readiness и parent replay PASS:2expected before failures,
36after PASS/0skip,4actual native owner→callback→consumer cases. Полный callback
AST отличается только Mapping import/type predicate; native core не меняется.
Replay: `local/goal584/native51-pricing-review/settings-fix-readiness.py`.
Это source-кандидат, runtime ещё не проверен.

После version proof остаются конкретные независимые срезы: native provider500
до usage → release reservation → следующий affordable success без reset/TTL/restart;
затем ordinary-user OfficeCLI export уже готового ответа → native render/download
со сравнением полного контекста и ledger. Это предложения, не runtime acceptance.
STT имеет отдельные microphone и Stage2 audio credential/billing paths, которые
одним budget Filter автоматически не покрываются; historical deployment evidence
не объявляется текущей конфигурацией. Read-only источники и representative inputs:
`local/goal584/next-accounting-slice.md`,
`local/goal584/current-route-compatibility-next-slice.md`.

**Повторная upstream-сверка по напоминанию владельца о KISS.** Новые изменения
и запуск стенда придержаны на время read-only проверки. Live GitHub readback
04.11.2026 подтвердил:36953 closed/unmerged, авторский эскиз shared invalidation есть;
45974 и40940 остаются open/unmerged, scheduled positive-floor gap ими не закрыт.
В актуальном45974 head `61b61fa1a7d8cfeebd21ec871d59c648cbb6ac8b`
авторский body прямо оставляет scheduled reset без нового reset fence;
review также описывает восстановление старого пятисекундного floor после reset.
Это эскиз защиты от гонки и распространения сброса между workers, а не готовая
замена нашего stand-only патча. В36953 human author
[подтвердил shared invalidation](https://github.com/BerriAI/litellm/pull/36953#discussion_r3796884419),
но final patch ограничен global budget и не меняет общий local floor memo.
Дополнительно найден open46409: native floor/broadcast для global reset,
не календарного job. Merged47044 относится к Rust gateway, не исправляет
Python `_authoritative_floor_spend`. Готовое released-исправление exact кейса
этим ограниченным поиском не установлено. Приоритет — существующий native
reset/floor owner; новый учёт или самостоятельный reset owner не вводить.

Предыдущий полностью зелёный native41
[41663679301](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41663679301):
оба jobs PASS, Active CI41663679293 PASS. HEAD
`adae068e108d3260e014f4af84493c99b2999452`, tested merge
`3a871f85d8a982706a5b750cae4d1f5ca6e343c9`. RAG принят независимо в run40,
calendar job-only profile — независимо в run41. Native41 повторил основной
WebUI/RAG gate. Main ZIP `015e94a93fc5454b290e65a8454a3ec341e58765bb4faf30621f73fd41291863`:
208 файлов/43 source hashes/6 mounts/cleanup0/0 сверены parent. Calendar ZIP
`bd6075c4a1c111ed6745f8dafbf1b9b2415f03a2fd45eeead5694ca51e95b8e7`:
4 файла/14 source hashes/5 mounts/10 native hashes, cleanup0/0/0. Независимое
C1–C5 review и parent replay PASS:
`local/goal584/calendar-proof-41663679301/independent-calendar-acceptance.md`.
Четыре actual native sweeps: T−1/T без изменений, T+1/repeat — период0,
next boundary1января00:00Moscow, caps/lifetime/история сохранены. Следующий
тот же worker вызов прошёл за0.970s<60s; новый period$0.20/lifetime$0.40,
две positive rows. Raw DB/provider/Redis/API/lease assertions частично
source-bound, не raw replay. Actual successful lease acquisition/HA не заявлены.
Проверка stale-positive DB floor, scheduler/inflight и multiworker reset не
входит в эту приёмку. На run41 реально сохранены naive UTC даты; значение
упавшей даты run40 по-прежнему неизвестно.

**Кандидат42 завершён: main/basic PASS, positive-floor FAIL, workflow FAIL.**
[41684602955](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41684602955),
HEAD `d1f3b5a2e2c764b0964c7683d84aef879b28e8ce`; Active CI41684603261 PASS.
Main повторил все прежние WebUI/service/pricing/overlap/RAG gates с новыми
capture/cost component bytes. Parent сверил206 files/43 source hashes/6 mounts,
51PNG/cleanup0/0. Main ZIP
`f2efe60e8ecbc7c313b2fa556ecdd45ffd59eaf3e305a43a03a2c9343226de77`;
`local/goal584/runtime-proof-41684602955/parent-source-check.safe.json`.
Новый matrix `positive-floor` остановился на
`FAILED_BOUNDARY/first_post_reset/unexpected_journal_rows`: old200/prime422/post200,
затем guard обнаружил3 raw own journal rows при2 expected success IDs
(source-bound вывод из exact guard, не экспортированный raw snapshot).
Причина/сумма/статус лишней строки и post Redis/provider readback неизвестны;
final headroom request не отправлялся. Это не подтверждение stale-offset defect.
Actual native reset записан как DB0/Redis null-null, прежний journal hash сохранён.
Независимый replay138 checks и parent повтор PASS; сам профиль FAIL.
ZIP `ecafe9db6cc717101aeb78604be6561ff3d959001ecb87b3ec5c16bf33c16e3e`,
tested merge `3a1c2fbed1808dff1b802b8b486dbcb0404ba436`.
Cleanup0containers/0volumes/0networks. Evidence:
`local/goal584/calendar-floor42-review/independent-acceptance.md`.
Basic calendar job PASS; parent повторил исходные calendar assertions с новой
matrix manifest/diagnostic формой:19 source/10 mounts/10 native hashes,
2 calls, next same-worker response5.203s<60s, cleanup0/0/0.
Компоненты Responses (fixture/capture/покрытие стоимости signed nonce) включены
для повторной проверки прежних маршрутов; сам Responses GUI probe не входит в42.
Локально:219 component checks (212 PASS/7 opt-in skips),302 harness checks PASS;
42 Bash/18 embedded Python/3 Python-c, actionlint и33 mount bindings PASS.
Evidence: `local/goal584/candidate-checks.safe.json`,
`calendar-floor-wiring-independent-readiness.md`,
`responses-call-coverage-independent-readiness.md`.
Закрыта только завершённая RAG worktree после проверки patch equivalence;
ветка provenance и общие source caches сохранены. Исходная рабочая копия с двумя
пользовательскими WIP-файлами не менялась.

Следующий source-срез сохраняет bounded failure snapshot до повторного выброса
того же journal guard: raw rows/counters/provider только existing private file;
наружу every-row hashes/status/cost/usage без metadata/body. Никакие строки не
отфильтровываются, max3/TTL5s/financial assertions не ослаблены.
Responses GUI probe исправлен по actual native TypedDict/точному missing-capsule
guard,22 focused tests PASS и независимое повторное ревью READY. Два frozen
файла перенесены byte-for-byte; CI mount/wiring прошёл source replay без native
операций. Calendar matrix не менялась. Общий CI budget75m/Rstep40m и always
teardown5m/upload2m — ограничение CI, не гарантия внутреннего browser restoration
при зависшем driver или внешней потере runner.
В existing browser requirements добавлен PyYAML6.0.2: clean-driver imports,
actual config append/validator и pip check PASS. Runtime Responses пока не принят;
полная reasoning continuity явно не квалифицируется этим финансовым профилем.
Актуальный следующий кандидат:326 harness checks PASS/0skip;
43 Bash/18 embedded Python/actionlint/34 literal mounts PASS.
Диагностика floor отдельно проверена25 focused tests и independent replay:
исходный failure leaf сохраняется даже при сбое всех diagnostic I/O.
Кандидат `69eaaa67d1851d87b4779f3e10a178b83c213879` отправлен:
[native43 41687079410](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41687079410),
Active CI41687079532 PASS. Native43 завершён: main FAIL в новом Responses
negative-ledger guard; прежние phases, включая RAG, PASS. R positive partial:
обычный Send/Tool/2 provider calls,2 native rows по$0.20, same-dispatch nonce и
decoded SDK/provider ID, User/key$0.40; native costs/details/reload$0.40.
Parent просмотрел details PNG:2 calls/20 input/10 output/30 total tokens.
Unsigned403/exact required-signature guard и native hard-zero422 подтверждены.
Ordinary GUI denial отрисован; следующий combined guard сравнивал одновременно
полный provider snapshot и raw own journal, failed без диагностических данных.
Причина R negative failure пока не различена; весь финансовый профиль FAIL,
положительный префикс не заменяет его приёмку. Все независимые restoration
readbacks completed:true, YAML original bytes equal; cleanup0containers/0volumes.
Main ZIP `3b26723d158c17670813c1c0c930d7998c3c0606fe092fafc7cf49c19c2bdf54`:
parent byte/Git/mount check220files/44source/6mounts/54PNG PASS.
Evidence: `local/goal584/runtime-proof-41687079410` и `responses43-review`.
Matrix floor43 снова FAIL на том же journal guard. Новая диагностика реально
сохранила3 raw rows:2 expected success по$0.20/usage10-5-15 и1 unmatched
`failure`/$0/usage0-0-0. Provider count2, Redis key/user$0.40/$0.40; ошибок
diagnostic I/O нет, cleanup0/0/0. Post DB snapshot остаётся только private,
final headroom request не отправлялся; полный stale-offset false-denial ещё не
доказан. Прямая привязка failure row к prime attempt пока отсутствует.
ZIP `0875913d4f38efa2624e20d3affff06a837697c9631fc5730bce2f75ad38195e`,
tested merge `191fac209d1020f90788df6b9d18d7b78a6d773e`.
Native `_ProxyDBLogger.async_post_call_failure_hook` действительно записывает
ошибки в тот же SpendLogs (по умолчанию), сохраняя request metadata. Поэтому
предпосылка proof «денежный журнал не содержит zero-cost failure rows» ошибочна.
Следующий verifier должен явно привязать и проверить каждую такую строку по
реально зафиксированной denial attempt; неизвестные/дублированные/не нулевые
строки по-прежнему FAIL. Нельзя скрывать строки или отключать native error logs.

По exact0.12.2 изучен отдельный reasoning gap: stateless ordinary middleware
теряет reasoning items до Responses router. Native experimental global
`ENABLE_RESPONSES_API_STATEFUL` — возможный отдельный путь через upstream
storage/previous_response_id, несовместимый с текущим fixedR store:false.
Конфигурация не включалась; новые history owners/core patches не добавлялись.
Evidence: `local/goal584/responses-native-reasoning-options.md`.

**Следующий кандидат: native audit contract + R negative diagnostics.**
Floor verifier учитывает все raw rows: максимум4 на4 отправленные попытки,
не более3 успешных списаний. Каждая нулевая failure row обязана точно совпасть
с own payer/key/model и записанной native422 attempt через уникальную lineage,
native BudgetExceededError/422, нулевые cost/usage и уникальный request ID.
Неизвестная/дублированная/платная failure row отклоняется. Поздние известные
audit rows допускаются при промежуточных чтениях; terminal требует их полноты
в60s окне заключительного наблюдения. Все ранее увиденные raw rows неизменны.
При собственном append между count/payload — максимум3 полных повторных чтения,
без merge/filter, возврат только согласованного снимка. Строгий TTL5s сохранён.
Independent review закрыл два source blockers (append race и late-ready61s);
50 calendar tests и actual-owner replay PASS. Native runtime ещё не принят.
R diagnostics сохраняет provider/capture/raw rows/User/key в existing private
state и отдаёт только закрытую schema со счётчиками/хэшами/суммами/статусами.
Provider и journal guards разделены; новая zero-cost row всё ещё FAIL.
Принятие audit rows для Responses не добавлялось. Ошибки diagnostic I/O не
маскируют известное первичное нарушение; worker/host protocol остаётся строгим.
Свежий независимый reviewer:34 focused tests+8 extra checks PASS.
Всего347 harness tests PASS/0skip; product bytes не менялись,219 component
checks (212PASS/7opt-in skips) переиспользованы.34 literal binds PASS;
workflow/Compose/host dependencies не менялись после source-проверенного43.
Evidence: `calendar-floor-native-audit-independent-readiness.md`,
`responses-negative-diagnostics-independent-readiness.md`,
`local/goal584/candidate-checks.safe.json`.
Завершённая Responses worktree закрыта после проверки4 patch equivalents и
exact SHA перенесённых файлов; ветка provenance сохранена. Остаются primary
GOAL-worktree и исходная main с двумя прежними пользовательскими WIP.
Кандидат `b6a00d0ce5a278e7da2a3b55d118ee34ab23b67e` отправлен:
[native44 41692849568](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41692849568),
Active CI41692849565. Runtime выполняется, источник результата ещё ожидается.
Floor44 завершил полный выбранный reproducer:
`FAIL_STALE_POSITIVE_FLOOR`, observed native false-denial подтверждён независимым
review/238-check replay и parent повтором. Old200/prime422/resetDB0+Redis absent/
post200: DBUser/key$0.20 при cap$0.40, lifetime$0.40, Redis$0.40/$0.40;
final тот же worker422 без нового provider dispatch. Всего2 actual charged
rows по$0.20 и2 строгих native audit0, точно связанных с prime/final;
все4 raw rows учтены. Critical2.937201738s(real)/2.937201748s(monotonic)<5;
final retained projection+2.956943s<60. Helperclosed, cleanup0/0/0.
Feature acceptance FAIL; L1 причина source-inferred, не live cache dump.
ZIP `0bb15c99a97f5814e282e13a3dd0368874259c0fbe8aa0d027f80103f288357a`,
tested merge `8df81e372414928337556c19b62e92c9c2c9f9a0`.
Evidence: `local/goal584/calendar-floor44-review/independent-acceptance.md`.
Основной WebUI/Responses job44 завершился FAIL на известном strict raw-journal
guard; Active CI41692849565 PASS. Новая диагностика различила причину predicate:
provider snapshot exact equal/19 calls до и после; raw own-R rows3 вместо2 —
2 original success по$0.20 byte-unchanged и1 failure/$0/usage0. User/key spend
остался$0.40, caps20/0, protected fields except key cap equal; diagnostic I/O
без ошибок, raw privately retained. Источник именно этой audit row не привязан
по intrinsic ID; не приписывать её задним числом direct422 или GUI422.
Исходный whole R-profile всё ещё FAIL; новый verifier должен явно учитывать
строго классифицированный native audit в serial direct-key422 bracket до UI,
а затем проверять отсутствие новых own-R rows/provider/spend после UI.
Restoration5/5 completed, original YAML bytes equal; cleanup0containers/0volumes.
Main ZIP `5c60ca98af4722c857fd31eb68c9470c9b30b1a54e246c69c6e36a685c865804`:
parent exact ZIP/source check220files/44sources/6mounts/54PNG PASS.
Basic44 PASS/parent replay:19sources/10mounts/10native,2calls,$0.20period/
$0.40lifetime, next same-worker3.411s<60s, cleanup0/0/0.
R diagnostic test reviewed Windows bytes SHA65cef81e… нормализованы Git в LF
SHA54569790…; обе стороны byte-for-byte CRLF→LF совпали, semantic delta нет.
Полные SHA сохранены independent R44 reviewer в `responses44-review`.
Патч LiteLLM не применялся:
issue584 требует отдельного согласования узкого native patch. До решения
готовятся конкретные варианты/лицензия/upstream comparison/test+rollback scope;
другая независимая работа GOAL продолжается.
Владельцу задан отдельный вопрос об одобрении stand-only prototype в двух
функциях `proxy_server.get_current_spend` / `_authoritative_floor_spend`.
Ответ ещё не получен; постановка вопроса не является разрешением. Пакет
`local/goal584/calendar-floor-native-fix-options.md` содержит source/race scope,
проверку лицензии, upstream seam comparison, критерии теста, сборки и отката.
R45 serial native-audit correction выполняется независимо в прежнем разрешённом
объёме proof; native package/production/финансовые данные не меняются.
R45 source candidate: прежний direct-key zero422 остаётся единственным таким
вызовом, до GUI. После него read-only bounded poll обязан получить ровно1 own-R
audit: точные user/key/model/deployment/aresponses, BudgetExceededError/422,
нулевые spend/int-usage и уникальный ID; обе положительные строки неизменны.
Существующие native budget-owner поля проверяются, если сериализованы; если
их нет, key-scope опирается на прежний exactHTTP witness и capsUser20/key0.
Привязка audit причинная — изолированный before/after одного HTTP-вызова;
intrinsic provider ID не заявляется. Полный снимок3 rows сохраняется ДО GUI.
Последующий GUI отказ обязан сохранить все3 rows/provider/counters/period,
плюс все прежние signed/unsigned/body/cardinality/old5/restore guards.
Неизвестная, вторая, изменённая или ненулевая audit row сразу FAIL. Ошибки API
не трактуются как pending. Нативные request body/count и positive context не
менялись; новые metadata markers/подписи/финансовые записи не генерируются.
44 focused tests и independent18-check/AST review PASS, source READY.
Рабочий source SHA662eca59… совпадает с GitLF; test workingCRLF6bd2893d…
переходит в GitLF5c25977b… без semantic delta. Полные identities:
`local/goal584/responses45-reviewed-byte-identities.safe.json`.
Полный актуальный harness357 tests PASS/0skip;34 literal bindings PASS.
219 component checks (212PASS/7opt-in skips) переиспользованы при неизменных
product bytes. При отправке R45 разрешение на native patch ещё не было получено.
**Новое решение владельца:** «Разрешаю узкий патч и проверку только на стенде».
Разрешены реализация/тесты stand-only prototype в двух согласованных функциях
LiteLLM1.105.1 `proxy_server.get_current_spend` и `_authoritative_floor_spend`.
Восстанавливаем проверку устаревшего positive DB floor, сохраняя квоты,
резервирование/монотонность live counter и защиту manual reset marker.
Production/deployment/финансовые схемы/данные не входят в это разрешение.
Исходный SDK cache остаётся read-only; кандидат и tests изолируются отдельно.

**Последующее уточнение владельца: KISS и upstream first.** Подготовка native
patch остановлена для read-only проверки известных issues/PR и штатного эскиза.
Разрешение на ограниченный стендовый prototype сохраняется; production и
расширение изменений за две согласованные функции по-прежнему не разрешены.
Подтверждено: [PR36953](https://github.com/BerriAI/litellm/pull/36953)
обсуждает тот же stale worker-local floor → восстановление прежнего расхода
после reset; автор предложил общий counter и invalidated Redis hint. PR закрыт
без merge и касается global budget, готового key/user исправления не даёт.
[PR45974](https://github.com/BerriAI/litellm/pull/45974), на момент проверки open,
head `784f352eaeb2cbac0628af39ce318681ffb2be4b`, содержит reset fence перед
записью counter и проверку fence в Redis repair Lua для global/org reset.
Его описание прямо сохраняет scheduled reset среди unfenced путей; перенос
целиком не устраняет доказанный календарный кейс GOAL584 и меняет больше двух
согласованных функций. [PR41693](https://github.com/BerriAI/litellm/pull/41693)
закрыт без merge; автор отдельно воспроизвёл тот же stale floor window на
scheduled linked-row reset, включая baseline. Это evidence известного дефекта,
а не поставленный фикс. Следующий шаг — сопоставить native fence/инвалидацию с
нашим exact reproducer, прежде чем выбирать ограниченный compatibility patch;
новый самостоятельный reset/accounting owner не создавать. Полные read-only
сверки: `local/goal584/upstream-floor-{pr-discovery,developer-discussions}.md`.
Merged manual-reset fixes37971/38686 уже входят в pinned v1.105.1/d665:
remote compare подтвердил ancestry обоих merge commits. Open40940 меняет
scheduled cache invalidation/retries, но его diff не содержит floor logic.
Подготовка сохранила только untracked, неприменённый/непроверенный `floor.patch`
в отдельной native-floor worktree; native build/test/CI не запускались.

**Native45 завершён и проверен.**
[41698427403](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41698427403),
HEAD `c11df5b8732f5d6203d75ad2dcfa133a12cfb240`, tested merge
`c08f5c3f7f0b8d005dec4f2436a5a6f5a5f6dd11`. Main job126135006833 PASS,
Active CI41698427312 PASS; basic PASS, positive-floor FAIL, workflow FAIL.
Responses financial profile принят независимым review и parent повтором replay:
2 actual charged dispatch по$0.20; direct native422 дал ровно1 own-R audit
BudgetExceededError/aresponses с cost/usage0. Все4 native budget-owner поля
действительно присутствовали и проверены. Перед/после GUI полный3-row hash
совпал, provider19/19 и User/key$0.40 неизменны; signed/unsigned/body/cardinality/
old5/restoration guards завершены, UI/Details/reload/denial проверены, cleanup0/0.
ZIP `e7a723a3d22924fec690fc45f32cc50109d381a73fd40cba851f8967f773c7f5`:
219 files/45 manifest sources сверены с actual Git merge;10 receipt mutations
отвергнуты. Audit привязан причинным serial bracket, не intrinsic provider ID.
Reasoning continuity остаётся наблюдаемым gap и этим финансовым профилем не
принята. Evidence: `local/goal584/responses45-review/independent-acceptance.md`.
Calendar45 повторён parent: basic19sources/10mounts/10native,4 native sweeps,
period$0.20/lifetime$0.40, next same-worker6.131s<60; ZIP25102a41… . Floor45
полный reproducer FAIL_STALE_POSITIVE_FLOOR:238 replay checks, critical1.258901s
<5, те же DB$0.20/Redis$0.40/cap$0.40/final422 без dispatch; ZIP9da862d4… .
Оба cleanup0containers/0volumes/0networks. Evidence:
`local/goal584/calendar45-parent-review.py` и два calendar packets41698427403.

**Следующий разрешённый срез — two-function prototype и явный derivative.**
Patch SHA `1d71ad80cca52b98e16f7909643f6d3f862b3f381c050ea57cfae1070065f906`;
base proxy SHA227a704e…, patched LF SHAe354f6e9… . Изменены только
`get_current_spend` и `_authoritative_floor_spend`; public admission signature,
reservations/monotonic repair/financial writes/reset job остаются прежними.
Would-raise positive floor перечитывает существующий DB owner под native reseed
lock; later manual-reset marker сохраняется, failure/cancel не разрешает новый
непроверенный ноль. Native TTL5/auth60 не изменены.24 exact-AST tests PASS;
native memory cache/reseed/DB gate/manual helper исполняются с явными IO doubles,
это не native Redis/Prisma/runtime acceptance. Нагрузка измерена:21 followers
после удаления marker дают1 DB read;8 callers, успевших прочитать old marker до
lock, дают8 последовательных reads. Гарантии1read/5s больше нет; штатный DB gate
и lookup deadlines сохранены. Inflight calendar cutover, noRedis stale L1 и
active-lock eviction pressure остаются непокрытыми; дополнительный reset fence
потребует отдельного согласованного scope, а не скрытого расширения двух функций.
Windows implicit Git apply первоначально дал CRLF SHAaa71f7df… вместо LF.
Подтверждено точное LF→CRLF равенство; apply теперь явно задаёт core.autocrlf=false
и core.eol=lf и проверяет реальные patched LF bytes. Патч/алгоритм не изменены.
Статический manifest различает base/patch/after, builder читает исходники из
точного pinned image и проверяет полный AST delta; MIT notice сохранён. Provider
и WebUI используют stock images, только proxy получает явно выбранный immutable
derivative image ID. Runtime hashes проверяются по выбранному manifest; modified
proxy нельзя выдать за pristine d665. Independent native readiness24+14 PASS,
builder review15 PASS; общий harness396 PASS/0skip. Actual CI-body replay28
calendar cases и5 overlap cases PASS, parent повторил;45 Bash/20 embedded Python/
23 literal Python-c/actionlint PASS.4 полных модуля импортированы с реальными
shallow /proof путями. До runtime устранены два wiring blockers: indexed parents
при /proof import и непроверенные extra/duplicate bind mounts.18 native source
guards и financial/timing assertions не ослаблены. Product bytes прежние;
219 component checks (212PASS/7opt-in skips) переиспользованы по exact identity.
Следующий gate — реальный derivative стенд с прежними financial/timing/cleanup
assertions; source readiness не является runtime acceptance.
Данные production, реальные тарифы/лимиты, платные API и рабочие маршруты не
входят в этот срез. Evidence: `native-floor-prototype-preparation.md`,
`native-floor-independent-readiness.*`, `native-floor-build-integration-readiness.md`
в existing ignored `local/goal584/`.

**Native46: derivative принят в выбранном bounded scope, все3 jobs SUCCESS.**
[41705184241](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41705184241),
HEAD `9e2d93efe1367edf5f1231bca7725be17548944e`, tested merge
`f80c868a3e5cde4bad7c23d7c31cfec2a3c5b057`. Basic job126158483172 SUCCESS:
ZIP `ea13d97e5a4361ddf572c7dab851368358691ea9bae60f39dbe10d4bba803a05`,
5 actual files,26 source hashes/12 mounts/10 native hashes. Parent воспроизвёл
Git/base/patch/AST/build-image/source bindings и прежние financial assertions:
4 sweeps,2 calls, period$0.20/lifetime$0.40, next1.899s<60, cleanup0/0/0.
Floor job126158483451 SUCCESS, ZIP
`ac4f23f40934f92f8bab22c73c90c61670f4fec7d978a8a448b548013ef84aa8`:
независимый replay и parent повтор276 checks PASS. Actual200/422/200/200,
3 charged rows по$0.20 и1 строго связанный prime audit0, final DB/Redis$0.40,
lifetime$0.60, critical2.051011s real/mono<5; caps/history/next period сохранены,
cleanup0/0/0.26 tested sources/10 helpers/12 mounts/18 native source hashes;
actual patched proxy SHAe354… выведен из pristine Git + exact patch + AST, а не
принят из receipt. В каждом job собран собственный immutable derivative image:
basic f9c52a1a…; floor86d05062… на обоих workers. Разные image IDs не выдаются за
одну сборку; совпадение base/patch/manifest и resulting SDK bytes проверено.
Raw full-row/provider/lease/context assertions остаются source-bound; live L1
не экспортирован. General inflight/noRedis/scheduler/load/full GOAL не приняты.
Evidence: `calendar-basic-proof-41705184241/parent-replay.safe.json` и
`calendar-floor46-review/replay.safe.json` в `local/goal584/`.
Main job126158482865 SUCCESS, Active CI41705184340/147 SUCCESS. Main ZIP
`972542eab3e378d02e1d9bbb75324baba477496eae50e30f76d55840ab12c606`:
220 files/52 actual source hashes/6 build bindings/SDK5 сверены с tested merge.
Независимый review и parent повтор actual replay+16 mutations PASS; parent
просмотрел actual Responses Details PNG. Main immutable image76a4df7d… на обоих
overlap workers, provider/WebUI stock. Overlap9 charged calls+2 budget denials,
12 counters, old finance unchanged; settlement/re-admission7.759s(key)/7.776s(user)
<15s без TTL workaround. Responses2×$0.20, full3-row native audit baseline до/после
GUI неизменен, provider19/19/counters$0.40; UI/cost/details/reload/negative guards/
restoration завершены, cleanup0containers/0volumes. Прежние main gates выполнены;
reasoning continuity, общие inflight/noRedis/lock-pressure/production не приняты.
Evidence: `local/goal584/native46-main-review/independent-acceptance.md` и
`verdict.safe.json`. Завершённая native-floor worktree закрыта штатным Git;
исходные patch/test291c… сохранены локальным provenance commit
`e722fff4c4fa8a48b9d1d2f37efd12cdb8e07e40` в прежней ветке. Receipt:
`local/goal584/native-floor-worktree-cleanup.safe.json`; исходная main с двумя
пользовательскими WIP по-прежнему не менялась.

**Следующий pricing срез.** Existing native Router/config, request-owned callback,
единственный SpendLogs и native periodic model-cost-map reload остаются владельцами;
второй каталог/ledger/scheduler не вводится. Readiness сверила15 source hashes и
native schedule edge cases; generic effective interval, source/time в HA и live
inflight activation не следуют из native timestamps. `user_config` dispatch сам
по себе не доказывает обход: native auth запрещает этот body param до custom auth
при отключённых client-side opt-ins. Никакой exploit/необходимость gateway patch
этим не заявлены. Проверяется descriptor, связанный с protected global deployment
и actual native billed rates; клиентский metadata marker не является источником.
Изолированная `corp-openweb-ui-goal584-pricing-version`, branch
`agent/goal584-pricing-version`, base9e2d93ef хранит source WIP fixture; callback
ещё в работе. В main ничего из pricing implementation пока не интегрировано. Opt-in synthetic
catalog fixture source-ready,51 focused checks PASS; настоящий native scheduled
fetch/version publication и финансовая/контекстная приёмка ещё предстоят.
Подробности: existing `local/goal584/native-pricing-version-next.md`,
`native-pricing-version-readiness.md`, `native-pricing-catalog-fixture-preparation.md`.
После docs-only commit09eeeb86 GitHub автоматически запустил дублирующий native47
41708950623. Actual merge6c6381ba… отличается от принятого f80c868a… только этой
записью; runtime code идентичен. Root отменил лишний run через GitHub CLI после
проверки live state; terminal cancelled. Оба calendar jobs успели SUCCESS;
main cleanup receipt подтверждает containers[]/volumes[], ZIP07112b12… .
Active CI148 SUCCESS. Последняя полная product acceptance — native46, не47.
Evidence: `local/goal584/native47-duplicate-cancel/cancellation.safe.json`.
Этот локальный отчёт не отправляется отдельным docs-only push, чтобы не запускать
ещё один одинаковый native CI. Для будущего catalog gate учтено native CLI:
начальный bundled source может иметь is_env_forced=true даже при envFalse;
первый реальный remote scheduled fetch обязан сменить этот source, а не считаться
проверенным по начальному bundled readback. Это source finding, не runtime PASS.

Предыдущий полный workflow до добавления RAG/calendar:
[41648991609](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41648991609),
HEAD `f84a57af7679d82828eaa507a21399d2198d3d31`, tested merge
`73c711a5571f9a478a89577d00dd7fdabcde5c52`; Active CI41648991628 PASS.
Повторены main/defaults/new-hire/cost/details/OFF, direct-title service,
обычный admin footer и удаление чата с сохранением учёта. Впервые прошли
три автоматические native задачи из обычного employee Send. Принят также
bounded pricing-срез: actual native rate snapshot, новая цена$0.40, старая
история сохранена. Независимый report/replay PASS:
`local/goal584/runtime-proof-41640329097/independent-pricing-acceptance.md`.
Предыдущая независимая приёмка direct service/admin/retention PASS:
`local/goal584/runtime-proof-41626578069/independent-service-acceptance.md`.
Review повторно исполнил сравнение actual service/admin inputs: один service row,
nonce/key hash/ответ, неизменные4 personal users/8 keys и34 исторические rows;
admin34→36 с двумя личными вызовами. Retention принят по source-bound evidence
с явно сохранённым ограничением независимого raw DB replay.
Parent для run38 сверил ZIP `e5ddfd802ac7a804f54b37c97d3cc0d6dfdcb63ec1b595b13f104eadbd71abe5`,
203 файла,42 source SHA и6 mounted SHA; cleanup0 containers/0 volumes.
Native direct service$0.20, automatic service$0.60 и personal reporting$0.40 разделены.
Retention: DELETE200 → exact native GET401 → тот же user auth200;
44 raw rows/5 payers/9 keys до/после имеют одинаковый финансовый hash.
Raw privacy scan выполнен source-bound runtime script; private DB JSON не
загружается в artifact и независимо из hashes не воспроизводится. Проверены
пустые body-поля, точные сохранённые значения, подстроки от32 символов и полные
credentials в выбранном scope; global privacy/failure/cancel этим не приняты.

**Текущий RAG-кандидат — ошибка подготовки, не принят.**
[run39 41655596690](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41655596690),
HEAD `23c03af13191f3967ee378d9b75e52e97d02bef4`, tested merge
`5844cd3a4e6bc6822ba48e625e7ebf6eee869f1a`, Active CI41655596820 PASS:
все прежние stages, включая pricing
и два proxy, прошли; новый RAG stage остановился в `prepare`. Подтверждены
runtime pgvector/prefix environment и один proxy. Worker receipt не сохранён:
ошибка возникла до записи `rag-prepare.json`. Source replay exact mounted
`/proof/prove_rag_service.py` независимо воспроизвёл `IndexError` на строке29:
`Path(__file__).resolve().parents[2]` не существует у этого короткого пути.
Это детерминированный blocker до worker_main/JSON; stderr самого run39 не
сохранён и не выдаётся за прочитанное доказательство. Parent replay:
`local/goal584/runtime-proof-41655596690/parent-mounted-import.safe.json`.
Это не доказательство сбоя embeddings, начисления или векторной БД.
Parent сверил ZIP `4b7e251976412dd18839b51874e871559342cfa81b8ae627dba780fabf42547c`,
204 файла,43 source hashes/6 mounts и cleanup0 containers/0 volumes.
Evidence: `local/goal584/runtime-proof-41655596690/parent-source-check.safe.json`.
Следующий шаг — исправить только вычисление host root, проверить импорт всего
модуля с mounted path и сохранить bounded boundary diagnostics перед повторным
native запуском; production и реальные API не затронуты.

Исправление интегрировано `edb1e450` из отдельной RAG ветки `a6fc41ac`:
host root вычисляется без индексирования отсутствующего parent. Полный модуль
импортируется из `/proof`; строгий whole-stdout JSON protocol сохранён. Ошибки
имеют fixed leaf/check ID, returncode/byte counts и allowlisted stderr class;
raw stderr/commands/секреты в receipt не попадают. Исходная ошибка сохраняется
при неудачном restoration.24 focused tests и независимое review READY:
`local/goal584/rag-mounted-fix-readiness.md`. Денежные/context/history assertions
не менялись. Кандидат целиком:203 component PASS/7 opt-in Chrome skips,
249 harness PASS,42 Bash/18 embedded Python/actionlint/32 bind/import checks PASS.
Один existing real-HTTP test вернул ожидаемый `incomplete_pagination`, но его
30ms wait завершился до второго чтения. Test-only window теперь200ms; assertions
повтора, page1-only и terminal error сохранены,20 reader tests/полный component
suite PASS. Runtime RAG и calendar ещё не приняты.

**Native40 завершён — RAG принят, calendar не принят:**
[41660087821](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41660087821),
HEAD `e51a2df6d1843d18bb89650dbbf6331fa43664c7`, tested merge
`7d1925b9aa690770a43880f29948c52d3ac807a6`, Active CI41660088091 PASS.
Основной WebUI/RAG job126000683806 PASS. Parent сверил native ZIP
`31a6ae10ebbfe65aea55bb9bf85abd16a9ec715bfd38a739cb9ba245deb7e741`,206 файлов,
43 source hashes/6 mounts и cleanup0 containers/0 volumes. Независимое R1–R4
review и parent replay322 checks PASS:
`local/goal584/runtime-proof-41660087821/independent-rag-acceptance.md`.
Две native RAG операции text/query создали2 positive E rows по$0.10 с usage10/0/10;
сохранены45 прежних full-row hashes и4 personal DTO. Service A$0.80 не изменился,
E$0.20, общий service$1.00. Exact prefixes/3D vectors/owned collection/retrieval
проверены. Ordinary protected config GET/POST:401+точный ACCESS_PROHIBITED при
валидной session до/после. Cap-only Ezero дал RAG500; budget denial дополнительно
подтверждён auth422/native422 budget_exceeded и отсутствием provider dispatch,
расхода и новых financial rows. Сам500 не является доказательством лимита.
Cap restore точно восстанавливает прежние exported fields. Часть raw HTTP/config/
DB invariants подтверждена source-bound private assertions, не независимым raw
replay; intrinsic provider/native embedding response ID, File GUI и globalprivacy
не заявляются.
Отдельный calendar job остановился после startup/attestation/native schema и
создания одного собственного user/key, до первого inference: `Native reset
timestamp is not timezone-aware`. Значение самой даты не экспортировано;
native PostgreSQL/Prisma UTC representation проверяется по exact source, а не
угадывается. Sweeps и восстановление допуска этим не проверены. Calendar ZIP
`3418ebd6475d144c14fd24ab69953274cdfdcda71f93373c8c892bae5522df7c`,4 файла,
14 source hashes/5 mounted hashes, private-config derivation и cleanup0
containers/volumes/networks сверены parent:
`local/goal584/calendar-proof-41660087821/parent-source-check.safe.json`.
Следующий calendar candidate следует exact native `_as_utc`: naive datetime
трактуется как UTC; None/date-only/неверные типы остаются ошибкой. Прочитан полный
API creation→helper→Prisma path сохранения user/key reset_at. Само упавшее значение
native40 неизвестно, поэтому naive JSONB остаётся обоснованной гипотезой, а не
прочитанным фактом. Теперь created public profile сохраняется до decode и ошибки
имеют fixed phase.16 focused tests и независимое source review READY;253 harness
tests PASS. Native job/SQL/clocks/TTL/invariants не менялись. Evidence:
`local/goal584/calendar-timestamp-fix.md`.

**Месячный сброс — отдельная подготовка.** Новый calendar job использует свой
проект `goal584-calendar-<12hex>`, БД `goal584_calendar` и Redis; штатный global
ResetBudgetJob не запускается на общем WebUI fixture. Source review обнаружил
несовместимость старого NativeProof (`30d`, A+B, lifetime вместо period spend).
Тонкая calendar проверка сохраняет общий inference transport и отдельно
сверяет журнал/период/накопительный расход. Readback выполняется однократно после
DB/Redis settlement, без API retry/ожидания TTL; после сброса до следующего вызова
нет management read или очистки кэша.12 focused tests PASS,42 Bash/18 embedded
Python и actionlint PASS. Первый календарный runtime описан выше; stale positive
DB floor, live scheduler и multiworker invalidation этим не приняты.
Рабочий review: `local/goal584/calendar-independent-readiness.md`.

После этих двух runtime gates остаётся совместимость Responses: отдельный
source-only review `local/goal584/responses-native-next.md` сохраняет exact
native-ID rewriting, минимум max_output_tokens16 и gap восстановления plain
encrypted reasoning из сохранённой истории. Replay нормализации system/Tool
context прошёл; это не runtime приёмка Responses/OfficeCLI/STT/Terminal.
Только provider fixture готовится отдельно в task-owned worktree
`D:/Users/Roman/Desktop/Проекты/corp-openweb-ui-goal584-responses`, branch
`agent/goal584-responses-contract`, base `e51a2df6`. Он не входит в native40;
cleanup после интеграции/приёмки, когда уникальная работа сохранена.

**BG-срез run35:** три автоматические задачи title/tags/follow-up после
двух обычных свежих Hi-чатов с одной выбранной моделью A. Тот же native service
payer и journal; новых регистров, frontend/core patch или фиктивных answer IDs нет.
Baseline дал один личный вызов и3 unsigned custom-auth403, signed phase —
один личный и3 service: вместе5 provider calls/$1.00, personal+$0.40,
service+$0.60 (итог$0.80). Сверяются полный реальный context до/после auth и
на provider boundary, native title/tags/follow-up и личная цена ответа/чата.
Полные TaskConfig/provider controls восстанавливаются, история сохраняется.
Runtime и независимая приёмка BG/newhire cost path PASS:
`local/goal584/runtime-proof-41632718620/independent-background-acceptance.md`.
Пять новых rows совпали с пятью provider IDs, все37 прежних positive rows
сохранены;4 personal и1 service payer/9 keys согласованы с журналом.
Baseline cost доказан visible+native GET, signed results — также после reload.
Итоговый scan-retry в run35 не наблюдался и не заявляется. Fanout/arena/automation,
embeddings и другие модели остаются неквалифицированными; source guard не
доказывает запрет fanout. Pricing snapshot и overlap в этот run не включены.
Перед исходным BG-кандидатом локально проверены180 component tests (173 PASS,
7 opt-in Chrome skips) и157 harness tests PASS; pricing/overlap WIP исключён.
34 Bash/14 embedded Python, actionlint и26 literal bind/import checks PASS.
До runtime исправлены два proof gaps: provider controls восстанавливаются
точно, включая отсутствие optional keys, без удаления receipts; внутренний
native stream-usage marker сравнивается существующей semantic projection.
Capture получает cross-process lock/собственный observation ID, чтобы три
параллельные native задачи не перезаписывали evidence друг друга. Это только
диагностика; native auth/резервирование/учёт остаются прежними владельцами.
Независимый source/integration review готовности к ограниченному native run:
`local/goal584/background-proof-integration-review.md`;20 focused checks и
actual AST native stream patch replay PASS. Это не runtime приёмка BG.
Кандидат `52d57df1700af4719bb4eebd59653fdd620421f0`:
[native run41630590813](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41630590813)
завершился ошибкой bootstrap29 до BG; Active CI41630590821 PASS,
cleanup0/0. Tested merge `340b0b4bad7548280559e96707ef9e495d80f75c`, ZIP
`b7292cb5ee7d35ddc95b0ad1066bf5943b3709dbaa5e9986a872a3d48efd6c8c`.
Newhire provider ответил200/10+5 tokens; native auth/scope/body совпали.
Но Filter сообщил `incomplete_pagination`, UI сохранил неподтверждённую цену;
post-call native snapshot отсутствует. Это не доказательство отсутствия
расхода или повторной задержки materialized counters. Исходники reader/Filter
совпадают с успешным run33; точный ответ cost API не был сохранён.
Pinned native session API читает count и data двумя отдельными awaits.
Offline исполнение actual endpoint AST воспроизводит count0/data1 и отказ
exact tested reader; конкретное содержимое страницы run34 остаётся неизвестным.
Evidence: `local/goal584/runtime-proof-41630590813/replay-session-pagination.safe.json`.
Следующее минимальное исправление существующего reader: при изменении count
или длины страницы отбросить весь scan и начать чтение заново только внутри
уже заданного wait/deadline. Capped/over-limit/schema/duplicate/foreign data
по-прежнему отклоняются; partial pages не объединяются, новых inference или
финансовых записей нет. Непрерывно неверный ответ остаётся ошибкой; вывод нуля
из неподтверждённого расхода не появляется.20 real-HTTP reader tests PASS.
Независимый candidate replay actual native handler через local HTTP подтвердил
recovery двух чтений и отказ непрерывно несовместимых страниц; source READY,
не runtime PASS. Ровно candidate suites:186 component tests (179 PASS/7 opt-in
skips) и157 harness PASS. Diagnostics/review:
`local/goal584/runtime-proof-41630590813/cost-pending-diagnosis.md`.
Pricing-кандидат run37 — actual billed-rate snapshot в той же native
SpendLogs row: существующий per-request Logging/CustomLogger копирует7 nullable
полей BilledTokenRates после расчёта, без price lookup/пересчёта/нового журнала.
Controlled synthetic modelA price0.01/0.02 →0.02/0.04, proxy restart, один обычный
Hi должен дать$0.40; старые суммы/usage/ставки/идентичности должны сохраниться,
service — не измениться. Полные исходные YAML bytes и native readiness
восстанавливаются в finally, включая ошибки. В next candidate добавлены только
callback, readonly mounts и этот phase после retention; production не затронут.
Source reviews: `local/goal584/pricing-snapshot-independent-review.md`,
`local/goal584/pricing-browser-independent-review.md`; actual run34 Hi context
повторно проверен.197 component tests (190 PASS/7 opt-in skips),183 harness PASS,
35 Bash/14 Python/actionlint/28 binds/imports PASS. Native flat pricing принят ниже;
source/version/effective interval, atomic tariff binding и regular automatic
checks этим снимком не доказаны. Overlap/calendar/RAG остаются отдельной
source-подготовкой и не включены в next pricing candidate.
Pricing candidate `bb8a78a3a9292a36e8bc6504e30f9ccc43199a00`:
[run41635338717](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41635338717)
завершился ошибкой только на новом pricing phase; Active CI41635338778 PASS.
Tested merge `bd1b325c8868c16623db29cfee6b6e43bea01709`, ZIP
`1cced4d87754cdc735bb510d517735d58f87ae06e63f72c47598e9736d75bca7`.
Actual callback/import/old-rate record прошёл, обычный новый ответ UI$0.40/$0.40
успешен; исходные YAML bytes/readiness восстановлены, cleanup0/0.
Точная ошибка воспроизведена на retained pair: proof ожидал отсутствие Tool,
хотя разрешённый `budget_echo` штатно сохранён в modelA после cost fixture.
Полные gateway/provider bodies с этой схемой совпадают; это не доказанная
ошибка начисления или callback. Следующий proof сохраняет этот legitimate Tool
и сверяет с его существующим model/schema owner. Историческое сравнение после
новой цены ещё не исполнилось и остаётся обязательным; native pricing не принят.
Proof correction прошёл28 focused tests,185 tracked harness tests и independent
source review; actual run36 pair/financial snapshots replay PASS. Продуктовый
callback не менялся. Добавлены только exact approved Tool checks и fixed
phase/category diagnostics, сохраняющие исходную ошибку при выполнении finally:
`local/goal584/runtime-proof-41635338717/independent-pricing-fix-review.md`.

**Принятый pricing-срез run37.** Native callback сохранил7 полей фактического
BilledTokenRates в существующей строке учёта.44 старые pricing projections
(42 positive +2 zero) сохранили cost/usage/ставки/IDs/user/key/model; у42 positive
полные scopes неизменны. Произвольная raw metadata нулевых строк этой
проекцией не проверяется. Один новый запрос дал actual input/output0.02/0.04,
usage10/5/15 и$0.40; его provider ID/key hash/nonce/actor/model связаны точно.
Полный контекст с legitimate budget_echo сохранён; пять payer/key counters
согласованы, вырос только личный A на$0.40, service остался$0.80. Исходные YAML
bytes/монтированный hash, native financial/task/Tool state и readiness
восстановлены. Snapshot capture time не является source/version/effective
interval; atomic tariff binding и другие категории этим не доказаны.

**Принятый run38 — два native proxy процесса.** Один общий native
PostgreSQL/Redis, реальные3s unfinished provider witnesses, второй worker
проверяет KEY и отдельно USER reservation denial без provider dispatch,
другие модель/пользователь остаются доступны, после settlement допуск
восстанавливается без TTL wait. План9 успешных calls/2 denials; прежние строки
и fixtures, новые caps/roles/allowlists/alias/metadata/blocked/period/reset и
нетронутые нули сравниваются строго. USER fixture намеренно имеет key caps
выше personal cap, чтобы изолировать native USER guard; это не admin policy.
Synthetic B выбран строго между R+C и2R. Source closure16 custom modules
и provider bytes проверяются у двух отдельных контейнеров.19 focused tests,
204 tracked harness,36 Bash/14 Python/actionlint/30 bind/import checks PASS;
Native runtime и независимая приёмка PASS. Реальные R$0.98/B$1.57,
9 successes/2 native422,9 positive rows/12 counters; recovery после held result
1.54s(KEY)/1.49s(USER). Новые роли/allowlist/alias/metadata/reset и old baseline
приняты по строгим source-bound runtime assertions, а не выдуманному raw replay.
Readiness review и точные источники:
`local/goal584/overlap-independent-readiness.md`.
Независимая приёмка/replay:
`local/goal584/runtime-proof-41648991609/independent-overlap-acceptance.md`.

Для последующего RAG обнаружен конкретный fixture gap: stock0.12.2-slim
возвращает native503 при default SQLite vector URL до embeddings. Поэтому
следующий stand сохраняет metadata SQLite и использует тот же PostgreSQL
service с официальным pgvector16 образом, отдельной пустой DB
`goal584_vectors`, native PGVECTOR_DB_URL и synthetic dimension3. Registry
digest `0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f`
проверен; package0.8.7/PG16.15. SQL создаёт только пустую vector DB, financial
tables остаются в прежней DB. Read-only startup проверяет наличие extension,
а не выдаёт его за RAG acceptance. Worker/reader/transport RAG ветка и calendar
в run38 не включены. Production не затронут.

**Следующий кандидат — штатный RAG HTTP text/query.** Reader/transport/proof
из isolated ветки интегрированы в primary без изменения личного read_employee
и gateway monetary logic. Один прежний service User/counter, canonical A+E
keys; expected service models читаются строго из native User.models, не из
нового каталога. E secret находится только в protected native RAG config,
fixed server key metadata содержит schema1/category service/operation
rag_embedding без выдуманных Actor/Chat/root IDs. Scope syntax отдельно не
доказывает origin: proof сверяет actual key hash/payer/model/native logging ID.
Provider embedding response ID отсутствует; diagnostic history ID не выдаётся
за native ID, причинность проверяется по одному вызову за шаг и native rows.
Обычный user0 создаёт собственную native owner-bound collection и запрашивает
её: ожидаются2 embeddings/$0.10 каждый, сохранённый документ/пригодные vectors,
personal4 и serviceA$0.80 без изменений. E hard-zero даёт native422 без
provider, cap восстанавливается с прежними spend/reset/identity. Ordinary
settings denial — exact native401/ACCESS_PROHIBITED при живой той же session.
Перед RAG parent явно возвращает proxy=1; proof только проверяет topology,
shared worker bind находится в существующем webui overlay. Success оставляет
E active до disposable teardown; ошибки не стирают финансовую историю.
Непустые document:/query: prefixes и PGCRYPTO=false задаются только в stand.
210 component tests (203 PASS/7 opt-in skips),234 harness PASS,
37 Bash/14 Python/actionlint/31 binds/imports PASS.21 focused source tests и
independent readiness review PASS; native RAG ещё не принят. Это не File GUI,
универсальный публичный embedding API или runtime-demotion qualification.
Evidence: `local/goal584/rag-proof-independent-readiness.md`,
`local/goal584/rag-native-proof-preparation.md`. Calendar остаётся untracked
source-подготовкой; tariff versions/checks, failures/cancel и действующие
Responses/OfficeCLI/STT/Terminal остаются в полном GOAL.

Обычный admin login → намерение в чате → штатные Skill/Tool → редактируемый HTML
→ JSON через native confirmed prompt → Tool читает сохранённый parent user turn
→ подтверждение server diff → native cap update/readback → реальные employee
quota denials и восстановление через ту же форму доказаны на stock0.12.2/1.105.1.
Прямой iframe RPC, отдельный bridge и изменение sandbox не понадобились.
Стоимость ответа/чата, Tool rounds, regeneration, детали и OFF enforcement также
прошли повторную проверку. Все данные и provider в стенде синтетические.
Платные вызовы не разрешены и в стенд не входят.

Реализованный путь HTML → исходный JSON в native user turn → Tool →
подтверждение серверного diff → native cap-only update/readback. Границы реализации:
Open WebUI владеет сотрудниками, ACL, моделями, сохранённым сообщением и подтверждением;
`assignment.py` — единственным контрактом связи user/model с native key;
`admin_client.py` переводит native API в server-only DTO;
`admin_policy.py` проверяет явные доли и рассчитывает предлагаемые caps;
`admin_tools.py` координирует эти вызовы, повторную авторизацию и порядок записи;
`admin_ui.py` только отображает данные и собирает JSON. Существующий Filter остаётся
единственным владельцем URL учёта, отдельный operator key не попадает в HTML/LLM.
Общий native model binding выделен из Filter без изменения поведения.
Defaults/new-hire прошёл native run выше; локальные проверки кандидата:
135 component tests, 128 PASS и7 opt-in Chrome skips, отдельно все14 renderer/Chrome.
Независимые части native provisioner, synthetic provider Tool turns и browser
driver интегрированы; native list/hash-update, hard-zero и подтверждённая запись
формы квалифицированы. Следующие обязательные gaps — служебные расходы,
lifecycle отказов/параллельности/календаря, исторические тарифы
и полнота действующих маршрутов. Локализованные budget errors приняты отдельно
по pre-service phases run41605241110; служебный этап этого run завершился ошибкой,
поэтому весь прогон успешным не считается.
Полностью отсутствующий бюджет нового сотрудника создаётся только после явного
выбора и подтверждения. Неполные/конфликтующие назначения показываются без ремонта;
сброса spend/reset, скрытых повторов или обещания общей транзакции нет.
Подготовлены native Tool/Skill и admin-only preset, отдельный synthetic личный
плательщик администратора, actual list/hash/zero-cap probe и обычный браузерный
сценарий cancel → apply двум сотрудникам → model/personal denial → recovery через
ту же форму. Перед каждым cap POST и показом приватных данных повторно проверяется
роль после сетевых чтений; имена сотрудников/моделей экранируются для Markdown
native confirmation. Отмена/частичная ошибка различаются и в коротком LLM context.
Успешный admin proof: отмена не меняет staff caps/spend/reset/identity; применение
даёт U1 total40/A40/B0 и U2 total0.4/A0.2/B0.2. Три отказа, три успешных employee
ответа и восстановление U2 до0.8 через форму подтверждены UI и native readback.
В main phase11 physical calls = 11 новых native rows,14 signed attempts;
admin8 calls/$1.60, staff3/$0.60, всего $2.20. Финальный ledger: U1$2.80,
U2$0.60, admin$1.60. Native Float-counter U2 raw0.6000000000000001 сохранён
как есть; exact ledger sum0.60 и существующий tolerance1e-9 не подменяют hard-zero.
Staff05 — KEY denial при одновременно исчерпанных personal/model budgets;
изолированный personal guard через GUI этим опытом не доказан (native core отдельно
проверен ранее). Оба уровня не следует смешивать в отчёте.
27 source SHA и6 mounted-module SHA совпали с tested merge; ZIP digest
`abd771a0ca92bd95c32f4fa29ea67d56d27f6f6a8214094fb953568be5da6dc5`.
Parent replay и независимый review E1–E7 PASS:
`local/goal584/runtime-proof-41504333246/{parent-review.safe.json,independent-admin-review.safe.json}`.
Полный Skill, схемы, исходный JSON/history, пустые apply arguments и короткие
Tool results сверены с фактическим provider context. Cleanup0 containers/0 volumes.

**Последний принятый срез:** закрыт доступ к management credential после
понижения Tool owner. Native Tools GET Valves разрешает владельцу role=user и
возвращает raw persisted blob; permission на изменение Python проверяется отдельно.
Предыдущий E7 проверял обычных non-owner сотрудников и не доказывает эту границу.
Ключ перенесён в существующие Function Valves с native `get_admin_user`, без
fallback на старое Tool поле; old persisted ToolValves очищаются полным update.
Для actual role-probe fixture primary admin используется только как контроллер, а Tool
owner — отдельный обычный admin: primary в0.12.2 нельзя понизить. Квоты и provider
calls при этом не меняются. Production установок этого feature не было.
Код переноса подготовлен: `ledger_admin_key` в Function Valves, Tool Valves
без credential, fresh lookup без legacy/reader fallback. 18 Tool tests и10
provisioner tests PASS; role-probe делает native demote/signin/GET/POST/restore,
проверяет запрет изменения Python и неизменность native state. Run41508244311
подтвердил native demote → fresh user signin → Tool Valves200 с ровно двумя
безопасными полями → Function Valves GET/POST401 → Tool source update401 →
restore admin. Caps/spend/reset/identities, source, модельные профили и ключ не
изменились. Внешний provider snapshot до/после обоих probes: те же8 IDs,
дополнительных вызовов нет. Основной admin/cost/details/OFF сценарий повторён:
11 новых positive rows/11 physical calls,14 signed attempts/$2.20; cleanup0/0.
Parent сверил27 source SHA и6 mounted SHA, заново исполнил verifier на raw inputs;
ZIP SHA256 `4be1aee54582b1a360ee0939f008a3c57301b5820dc00af96f29d2723cb05bbe`.
Evidence: `local/goal584/runtime-proof-41508244311`, parent-review.safe.json и
role-independent-review.md. Это приёмка указанной границы и повторение main slice,
не полная квалификация безопасности или всего продукта.

**Принятый срез defaults/new-hire.** Отдельная native inspection
различает полностью отсутствующий budget identity, готовое назначение,
частичное/повреждённое состояние и недоступность. Только exact user404 + полная
пустая key/list доказывают отсутствие. Никакого скрытого создания/ремонта.
Форма показывает готовые и неподготовленные
бюджеты отдельно; шаблон сохраняется за admin-only Function API. Сохранение
шаблона и создание явно выбранных личных бюджетов — разные JSON-планы и
подтверждения. Шаблон не меняет существующие назначения. Его доли предлагаются
только при точном совпадении разрешённых моделей, без перенормировки.
Перед созданием повторно проверяются saved source, admin, directory/model ACL,
template/config и actual absence; перед каждым POST — свежие полномочия/источник/
конфигурация. Native confirmation показывает1 personal budget + число назначений,
точные USD caps каждой модели и календарный1mo период владельца учёта.
Native /user/new создаёт только пользователя; /key/generate получает канонические
alias/metadata и deterministic key от существующего gateway secret с отдельным
HMAC domain. Native token primary key/upsert(update={}) не перезаписывает winner;
400/409 не превращаются в скрытый retry/repair. После каждого шага читаются
actual state/caps/identity/period/routes; частичный результат показывается явно.
Это не общая транзакция или runtime-доказательство конкурентного bootstrap.
Native Function Valves заменяются целиком без CAS; свежие unrelated/secret fields
сохраняются и сверяются, конкурентная замена конфигурации остаётся ограничением.
Policy17/Tool25/real HTTP client28 и Chrome14 checks PASS. Независимый server-source
review PASS после уточнения финансового diff и нормализации untrusted labels;
10 изменений source/role/model ACL/template/credential во время confirmation
не допустили записей. Harness49 checks, actionlint и static30 Bash/14 embedded
Python scripts PASS. Подготовлен отдельный
post-main native fixture: third staff не меняет старый11-call baseline; save
template → cancel initialize → confirmed initialize → employee success/zero-cap
denial. Run41596060610 подтвердил этот сценарий: before/template/cancel остаются
absent; после подтверждения создан ровно1 native user и2 key assignments с
caps0.8/0.8/0, периодом1mo и одинаковым reset timestamp. Ответ A начислил0.20,
B cap0 отклонён до provider.4 admin turns/8 physical +1 staff physical =9 новых
native rows,10 signed attempts/$1.80. Все25 прежних positive rows сохранены
полностью; итог34. Existing staff caps/spend/reset/identity неизменны.
Parent сверил29 source SHA/6 mounted SHA с tested merge, ZIP SHA256
`9688537008871d740f40a8e91eae96f638cdeda7bd47b83654f3929462e9c3d8`, заново
исполнил оба verifier на raw inputs. Независимый reviewer сверил source/context,
native user/key totals со всеми ledger rows и11 PNG: PASS. Native primary order
controller1793690822 < server Date1793690823 <= owner1793690823 стабилен в12
base readbacks. Cleanup0/0. Evidence:
`local/goal584/runtime-proof-41596060610/{parent-review.safe.json,independent-bootstrap-review.md}`.
Это не runtime-приёмка concurrent bootstrap, partial recovery или перехода месяца.
Первый native кандидат `aed366b48d25cebafe1b0bdf00281b64f54c4c3c`,
[run41591143766](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41591143766),
прошёл прежний main/cost/details/OFF и owner-role сценарии; parent replay PASS,
29 source SHA/6 mounted SHA совпали, cleanup0/0. Остановился до нового GUI на
bootstrap model grant readback. Native `replace_access_grants` удаляет старые
строки и создаёт новые UUID/created_at; сравнение whole access_grants с запросом
было ошибочным. Фикстура исправлена: сверяет точный semantic grant set/count и все
остальные MODEL_FIELDS, как существующий add_model_meta;13 focused tests PASS,
включая native ID regeneration/reordering и отрицательный дрейф прав/профиля.
Следующий шаг — повтор native GUI gate. Bootstrap runtime всё ещё не принят. Artifact SHA256
`d6ef00a2c4870317ba0999b7faa262b7556d144c6c07bdff7dc9d37b1159a254`;
evidence `local/goal584/runtime-proof-41591143766`.
Следующий run41592272718 (`40e5f5b1`) прошёл cost/details/OFF, но остановился
раньше admin GUI: native role-probe получил403 при понижении владельца. Источник
показал ошибочную предпосылку fixture: `get_first_user` сортирует admins с одинаковым
second-resolution created_at по UUID. Controller и owner могли создаться в одну
секунду, и owner оказывался защищённым primary. Исправлено без изменения native
timestamps/прав: fixture ждёт подтверждённый переход серверного HTTP Date,
читает actual created_at обоих admins и требует строгий порядок. Каждая base
snapshot повторяет readback и сохраняет три безопасных временных значения.
6 HTTP clock/order tests и13 provisioner tests PASS. Следующий шаг — новый native
прогон до bootstrap GUI. Cleanup0/0; artifact SHA256
`1fe07833946752fddef9aa03e1bbd40e541050339184ace9150d9b3dc7dddb30`,
`local/goal584/runtime-proof-41592272718`. Bootstrap runtime по-прежнему не принят.
**Текущий следующий срез:** services. Native task paths обходят Function request
Filter, а X-Task из raw OpenAI proxy не является доверенным выбором плательщика.
Подготовлен локальный native Pipe для direct title endpoint: fresh actor/chat ACL,
существующий model binding, отдельный signed service audience и native service payer.
Нет выдуманных answer/root IDs; service session отделена от personal cost readback.
Код ещё не квалифицирован в native runtime. Native Users дополнительно запрещает
service payer, совпадающий с существующей учётной записью WebUI; ошибка directory
не считается отсутствием. Read-only блок служебных расходов в admin форме читает
native service user/model counters без включения их в personal totals. Обязательный следующий
proof сравнит фактический native target-model task (unsigned отказ до provider)
и Pipe→тот же target (signed service оплата) при одинаковых native task params,
включая финальный provider context. Task-model fallback max_tokens и target system/
custom params нельзя считать сохранёнными лишь по mock dispatch. Реальный Pipe
также требует Workspace Model/ACL; отдельный Function без этой регистрации
не виден обычному actor. Raw negatives принимают только403 с причиной отказа
подписанного provenance, а не произвольную HTTP ошибку. Title phase ожидает1
physical call/$0.20; последующий отдельный admin GUI open — ещё2 personal admin
calls/$0.40, footer20/0.2/19.8 и неизменные staff/service counters. Эти фазы
сохраняют раздельные provider/context receipts и полный native ledger.
Локально172 component tests (165 PASS/7 opt-in Chrome skips),73 harness checks,
static32 Bash/14 embedded Python scripts,24 bind paths/imports и actionlint PASS
включая4 focused checks нового admin-browser fixture.
Automatic
background tasks и RAG/public embeddings остаются отдельными gaps. Источники:
`local/goal584/{service-native-path-review.md,service-pipe-independent-review.md}`.
Реализована штатная CustomLogger failure hook для понятного budget error без изменения
status/type/учёта; её кандидат также требует actual422/UI gate. Исходная фраза
«исчерпан» была неверна для strict reservation с остатком0.6 и оценкой0.7;
используется «недостаточно бюджета для этого запроса». Actual native reservation/
exception/converter source и независимые10 targeted checks подтверждают сохранение
422/budget_exceeded и остальных полей исключения. Native prompt-body storage
явно выключен config/env; полная DB privacy и failure/cancel paths остаются отдельным gate.
Далее остаются остальные перечисленные gaps;
Первый service/error кандидат `afdf38dcef916a5f46e2fce72f10e706b8746c14`,
[run41603889448](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41603889448),
подтвердил native callback на scalar key/user, gateway и cold restart с сохранением
422/budget_exceeded. До WebUI не дошёл: старый config transition требовал отсутствия
store_prompts_in_spend_logs, уже заданного в новом базовом конфиге. Исправлено:
проверяется ровно одно значение false, повторной вставки нет. Локальная репетиция
двух фактических workflow Python stages на полном базовом YAML PASS; callback,
common checks, capture delegate и privacy flag сохранены. Static32/14 и actionlint PASS.
Следующий шаг — повтор того же native GUI/service gate. Cleanup0/0, ZIP SHA256
`e4347afc172b0e7de19571a9040d21ab3aa3a3764eefc412f14269e2f999bf4c`,
`local/goal584/runtime-proof-41603889448`. Service/UI этой попыткой не квалифицированы.
Повтор [run41605241110](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41605241110),
HEAD `35b4405779c9a0170aef7f35d59de7e21e234fe7`, tested merge
`750d9d4efaf814c37d19702b227793dc600efc53`, прошёл прежние GUI phases,
включая локализованные budget errors, и остановился на первом service negative.
Native title baseline вернул403 signed-provenance guard; подписанный title вернул200
и дал один physical provider call с отдельным service payer в auth scope.
Обычный запрос с выбранным Pipe вернул409 до ожидаемого `unsupported_task`;
такой отказ не доказывает нужную защиту. Причина и валидность fixture-запроса
проверяются; service accounting/context и admin footer ещё не приняты.
Настройки native task восстановлены; cleanup0/0. Evidence:
`local/goal584/runtime-proof-41605241110`; ZIP SHA256
`aa4bac96a08f5c1ad32ead453ee84eaafcfd77896c8d397ad40031e8c39ff332`.
Независимая повторная сверка pre-service phases PASS:33 source SHA и6 mounted
SHA совпали с tested merge; main11/14/$2.20 и defaults9/10/$1.80 согласованы с
physical provider calls, signed scopes, native ledger и всеми personal/model
counters. Все25 исторических rows сохранены, итог34. Проверены14 PNG, включая
понятные model-specific/generic отказы и OFF enforcement; native422 и
budget_exceeded сохранены. Evidence:
`local/goal584/runtime-proof-41605241110/independent-pre-service-review.safe.json`.
Причина409 подтверждена исполнением actual native main admission AST и
`Chats.insert_chat_turn`: сохранённый chat_id без нового message ID отклоняется
до Pipe. Negative fixture использует штатный stateless synchronous путь без
chat/message IDs, со всеми background flags=false; требование точного
`unsupported_task` сохранено. Safe case/status/known-code/hash diagnostics и
частичные стадии теперь сохраняются до проверки, без публикации raw response.
Перед новым runtime:172 component tests (165 PASS/7 opt-in skips),85 harness
tests PASS,33 Bash/14 Python workflow snippets, actionlint и24 literal bindings
проверены. Это локальная проверка кандидата, runtime result ещё ожидается.
Кандидат `4543f6e91d36fb0faab45a611c4820692c14560d`,
[run41608210940](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41608210940),
tested merge `0005e2f2016cd09892a2d137c8a583f7a8e9c446`, прошёл все четыре
service negative guards с нулевым приростом provider calls. Остановился дальше:
сравнение ожидало явное `stream:false` на provider wire, а actual native OpenAI
handler извлекает этот параметр до non-stream dispatch. Остальные captured поля,
кроме ожидаемого model alias, совпали. Исправление ограничено proof: baseline/signed
и before/after auth остаются строго равны; provider должен опускать stream,
остальные поля сравниваются целиком. Исполнение трёх assignments exact native
handler (SHA e6d25eea6d0a12d16f781ea175982830ab7eaa945ca32b4c5b424580d84f8831)
подтвердило преобразование;13 targeted tests PASS, включая запрет wire stream=true/false.
Service/admin-footer/retention runtime всё ещё не принят; следующий gate повторяет
эти этапы. Cleanup0/0; evidence `local/goal584/runtime-proof-41608210940`, ZIP SHA256
`0792c7104ee908546a4141e054276194962467364e9a525e9eb0e98c69eb5334`.
Независимый replay actual raw gateway/provider bodies подтвердил полное равенство
после этих двух native transport преобразований (model alias и отсутствие
stream=false), без конструирования фиктивной native ledger row. Отдельно проверены
точные bytes handler из pinned Git blob и13 targeted tests:
`local/goal584/service-nonstream-run28-review.md`. Следующий кандидат меняет только
proof и эту запись; product guard, provenance и финансовые проверки сохранены.
Повтор [run41610342231](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41610342231),
HEAD `864663badbdea6a27ef5c98058fdc494785e3bd4`, tested merge
`265db70804d895aafac80bd9c904239179905951`: direct-title и отдельный service-admin
GUI этапы PASS. Финальный retention stage остановился с общей ошибкой readonly
observation, без указания конкретной команды; удаление ещё не квалифицировано.
Проверка исходного SQL парсером PostgreSQL (`pglast7.22`, только local dev venv)
PASS: гипотеза о лишних слешах не подтвердилась, SQL не изменён.
Найден конкретный packaging gap в отдельном `python -c`: plain import `provenance`
не учитывал config-relative mount `/proof/provenance.py`. Теперь используется
существующий native `get_instance_fn` с `/proof/config.yaml`; добавлены safe stage
и фиксированная классификация ошибок без raw stderr. Следующий gate проверяет
runtime loader и весь retention path. Evidence `local/goal584/runtime-proof-41610342231`,
cleanup0/0, ZIP SHA256 `0030a3a5c43f19fe40d1a12e5ddd66d69ad31b64d3876dbbcfe7d3888f4e8476`.
Для следующих срезов подготовлен отдельный source WIP, не включённый в этот
direct-title/retention кандидат: background title/tags/follow-up guard существующего
Pipe (53 checks), безопасное слияние параллельных diagnostic captures (6 checks),
controlled500/stream pauses в прежнем synthetic provider (23 HTTP checks),
копирование native request-owned billed rates в metadata той же spend row (11 checks).
Это не приёмка runtime, не версия коммерческого тарифа и не новый money owner.
Контракты и gaps: `local/goal584/{background-service-source-slice.md,capture-concurrency-slice.md,provider-lifecycle-controls-slice.md,pricing-snapshot-source-slice.md}`.
Для calendar reset отдельно найден concrete native constructor/cache/lock seam;
job выбирает due rows строго `<now`, и контроль времени нужен в двух native модулях.
Глобальный job не имеет payer whitelist, поэтому нужна отдельная fixture/due population;
native helper checks не заменяют runtime rollover.
Перед повтором retention14 targeted tests PASS: actual `VALIDATE_ROOTS` исполняется
отдельным процессом с exact native loader AST и real provenance при заблокированном
обычном import; неверный UUID отклоняется. SQL grammar PASS, известные/неизвестные
process errors не публикуют stdout/stderr/credentials. Service proof дополнительно
сохраняет whitelist actual native row с API-key hash, personal/service before/after
DTO и config fingerprints/readbacks до context assertions; raw metadata/headers и
prompt bodies не экспортируются. Эти наблюдения закрывают пробел предыдущей
квитанции, где row/key/config проверки были только source-attested.17 service tests
PASS, включая сохранение actual observations при поздней ошибке и restore.
Run30 [41613261580](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41613261580),
HEAD `8ed6f03f71dea7d186120bf816ce3e85f7528dc5`, tested merge
`e7ff2dd454ebef092d594012bb898515f4264488`, прошёл loader и initial raw privacy,
выполнил native DELETE200 и получил GET401. Pinned get_chat_by_id возвращает401
с exact `ERROR_MESSAGES.NOT_FOUND` для отсутствующего чата; прежнее ожидание403/404
было неверным. Теперь проверяются именно401+native detail и последующий authsGET200
для того же user.17 retention tests PASS, включая исполнение actual native route AST,
проверку истёкшей/чужой сессии и запрет принятия произвольного401. SQL/финансовые
и privacy guards не изменены. Финальное сравнение after snapshot остаётся runtime gate.
Service receipt следующего кандидата также сохраняет actual native title response
и existing-read history-ID maps всех4 payers, включая newhire;19 targeted tests PASS.
Содержимое native response сверяется с контрактом synthetic provider, его ID/usage —
с actual provider record; отсутствующий raw provider response не выдумывается.
Run30 cleanup0/0, evidence `local/goal584/runtime-proof-41613261580`, ZIP SHA256
`286b8e9a8857209b61b0b5b415fe1e323be25a134bbda22e6e0d9e3919c36bc0`.
Independent run29 service review подтвердил admin footer/turn и context/source hashes,
но дал NEEDS_EVIDENCE для полных raw financial/config/response readbacks; это учтено
в расширенных квитанциях, а не ретроспективной приёмке отсутствовавших данных.
Background source review не нашёл authority/money-owner defect для выбранного
native primary A. Fan-out не различим в унаследованной metadata и может пройти
guard при первом A; он остаётся runtime-unqualified, запрет fan-out не заявляется.
Run31 [41615522053](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41615522053),
HEAD `30c0f306263aafedc6767fa88c5e57bd2b476906`, tested merge
`d1865d44ac344999ead65bd22f0b31261ff55205`, остановился раньше service/retention:
после successful newhire A и hard-zero B в actual34-row ledger есть один новый
employee event0.20, но однократный final snapshot user/key ещё0.0. Причина задержки
в этой попытке не доказана; сходимость не наблюдалась. Browser driver теперь только
повторно читает native snapshots до совпадения counters/ledger (не более60s ожидания),
сохраняя каждое наблюдение. Identity/caps/period меняются — немедленный отказ;
лишний расход/строка и ненулевой hard-zero B также отклоняются. Новых inference,
budget writes, repair или пересчёта нет.9 targeted tests PASS. Offline replay
неизменённого actual failing input корректно заканчивается timeout, не PASS:
`local/goal584/bootstrap-settlement-run31.safe.json`. Нужно новое native наблюдение
сходимости; после него остаются прежние полные финансовые/context проверки.
Evidence `local/goal584/runtime-proof-41615522053`, cleanup0/0, ZIP SHA256
`17aaa04cf26e9d65970237a8070ff4f39d6992b31bbe789d778444d4dab8de3d`.
Run32 [41618051782](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41618051782),
HEAD `31ddd53ac790a3d780dd76452cc1eddd62622d96`, tested merge
`dd16f0810abd34422524988a389caebad72841c1`, остановился на аналогичном однократном
admin final readback: ledger24→25, ровно один новый U2/B event0.20, но user/key
ещё0.4/0.2 вместо0.6/0.4. Остальные поля сохранены. Bootstrap/service/retention
этой попыткой не проверены; cleanup0/0, ZIP SHA256
`4006aa96870e9543ba7fd48f21f12f7afcbfd24becbbd36d19b7f37939c770b7`.
Общий read-only `wait_inference_delta` теперь обслуживает admin и newhire,
проверяя каждое неизменяемое поле и точные новые события; старые финальные
assertions сохранены.24 focused tests PASS, оба неизменённых failing inputs
завершаются timeout, а не ложным PASS.
Для полного personal history используется существующий owner
`verify_admin_calls.accounting_totals_ready`: deficit может ждать, surplus,
неверные identities, строки и суммы отклоняются; zero total требует exact zero.
Он применён к pre-service baseline и service-admin snapshot. Последний теперь
включает newhire history (полные34→36 rows вместо прежних33→35) и ждёт counters
после достижения количества строк. Финальный verifier остаётся строгим.
Для proxy CLI добавлен readonly bind этого же owner;25 literal sources/imports,
33 Bash/14 Python snippets и actionlint PASS. В admin HTML добавлено пояснение,
что недавние расходы могут появляться с задержкой; финансовая логика не менялась.
Вся текущая рабочая копия, включая отдельные неинтегрированные следующие срезы:
191 component tests (184 PASS/7 opt-in skips),176 harness tests PASS.
Source audit15 pinned native files подтвердил раздельные journal/entity queues и
management DB reads: configured interval1 получает startup jitter0..5s. Это
lag-permitting механизм, не наблюдённая сходимость конкретных runs. Cap-only updates
на проверенных путях не удаляют prefixed scalar Redis counters; explicit spend
update — другой путь. Подробности и следующий bounded probe:
`local/goal584/native-materialized-spend-read-seam.md`.
К следующему кандидату добавлена отдельная финальная retention-проверка: свежий
native login сотрудника, один его завершённый оплаченный synthetic Hi/Proof chat,
native DELETE и повторный GET, readonly PostgreSQL snapshots всех колонок
финансовых строк пяти fixture payers до/после. Требуются неизменные строки,
идентичности/caps/spend/reset и provider IDs. Raw snapshots пишутся только в новый
0600 private-файл вне artifact tree. Публичная квитанция содержит hashes/counts,
пустые native body columns и результат проверки exact saved content values/full
credentials; короткий текст внутри иных строк и глобальная DB privacy этим не
квалифицируются. Это подготовленный исходный срез с9 локальными tests PASS,
а не выполненное удаление или принятый runtime результат.
business default template должен храниться за admin-role API, не в owner-writable
Tool Valves. Source review bootstrap: `local/goal584/admin-bootstrap-source-review.md`.

История предыдущих неуспешных admin-кандидатов (их ограничения не являются
текущим состоянием принятого среза):
Кандидат `f1fc321e` прошёл Active CI. Native run
[41499123999](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41499123999)
прошёл core/gateway/restart/provider-boundary и остановился до запуска WebUI:
opt-in renderer test использовал Windows-путь Chrome на Linux. Исправлен выбор
штатного browser channel `chrome`; teardown отработал, artifact digest
`9c58a6f6c8adc894c9189d83a40ca06ce0f03425bc6441812baef567b103890a`, cleanup 0/0.
Ожидание 11 physical calls и 3 отказов всё ещё нужно сверить с provider,
signed context, native ledger и фактическими caps на следующем кандидате.
Повторный native run
[41499920317](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41499920317)
на `912483f0` прошёл Chrome, mounted-module SHA checks, native suite96
(89 executed, 7 skips), ordinary chats и прежний полный cost/details/OFF сценарий.
Admin Tool/Skill/preset успешно установлены штатными API; REAL BudgetAdminClient
прочитал `/key/list`, staff caps и отдельные admin caps1000/500/500, ACL сохранены.
Остановка случилась при чтении runner-ом root-owned 0600 browser handoff, до
native zero-cap probe и admin GUI. Передача исправлена как у существующих staff
accounts: отдельная runner-owned копия0600 через container exec, без ослабления
прав исходного файла. Artifact digest
`217a8c0b7c95049349d57ef07bcc2832ccce9c66c85b03eda8eefc0aa95c0e4c`, cleanup 0/0.
Native run [41501136863](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41501136863)
на `b51ed93c` дополнительно подтвердил hash cap update и hard-zero: unused admin B
spend0/cap0 дал native422 budget_exceeded, provider IDs не изменились, затем
cap500 и все identities/spend/reset восстановились точно. Admin browser остановился
до первого запроса: штатное первое окно What's New перекрыло model selector.
Screenshot и zero provider attempts сохранены; driver теперь нажимает его обычную
кнопку Okay, Let's Go!, не меняя frontend/storage. Artifact digest
`586f7d7d0818e9cdcaddde6e66c50c0153b32eea8825aa1c773626e88e00efc3`, cleanup 0/0.
Независимая scoped приёмка предыдущего run18: 27 точных source SHA, cost/details/OFF
и admin installation PASS (`local/goal584/runtime-proof-41499920317/independent-review.safe.json`).
Текущий кандидат `c97a7025b928d651244fc1d14c132c397ca96771`: Active CI
[41502403380](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41502403380) PASS;
native [41502403795](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41502403795)
остановился на первом чтении формы. По PNG форма уже видна с actual staff/caps/spend;
2 provider calls содержат native open_budget_form и короткий success без HTML.
Driver ошибочно искал Tool HTML в верхнем `message.embeds` как у Action.
Pinned middleware6194–6201 и structuredOutput.ts236 хранят его в correlated
`function_call_output.embeds`; чтение исправлено с проверкой call_id/method/status,
добавлены отрицательные проверки foreign/failed/Action-only output и bounded
technical-state receipt при таймауте. 7 driver + 8 boundary групп PASS.
Artifact digest `8cdb61b2a19a6735921d8e8cde8daf64bf0408b4fc1ee463a1ac85a05b75a0f6`,
cleanup 0/0. Apply/quotas/recovery формы всё ещё не приняты. Следующий шаг —
повторить этот native GUI gate; Production и полный GOAL по-прежнему не приняты.
Следующий source-кандидат для исторических тарифов найден, но не реализован:
native frozen `Logging.billed_token_rates` и `add_dynamic_callback`; authoritative
version/source/effective_at и гонки native resolution требуют отдельного proof.
Подробности: `local/goal584/litellm/pricing-used-snapshot-review.md`.

## Цель и ограничения

Из обычного чата открыть актуальное управление денежными бюджетами сотрудников,
подтвердить изменение и реально ограничить последующие API-вызовы. Сотрудник
видит стоимость ответа со всеми LLM-шагами и итог чата со всеми ветками.
Отключение отображения не отключает учёт. Служебные расходы учитываются отдельно;
история не пересчитывается при изменении тарифа и не исчезает с удалением чата.

Разрешены собственная ветка, ограниченный изолированный стенд, реализация,
локальные проверки и PR. Production, реальные тарифы и лимиты, платные API-вызовы
и изменения рабочих маршрутов требуют отдельного согласования. Ядро Open WebUI,
фронтенд, DOM/fetch и защиту iframe не изменяем. Не создаём второй каталог
сотрудников, журнал расходов, постоянную админ-платформу или sidecar.

## Проверенная исходная конфигурация

Read-only сверка 02.11.2026, 13:35 МСК; ключ SSH и адрес проверены по текущему
локальному указателю и DNS, host-key проверка не ослаблялась.

- Open WebUI: `/api/version` = `0.12.2`; runtime image
  `sha256:6cc2c633a09e325b31c03acf57a5c846e381577e98ab43a993c932c599044139`.
- LiteLLM: установленный пакет `1.105.1`, runtime image
  `sha256:b7b9e2c306343721802253d0dd9436b9634a2eb4e14da7c7cf06c5c7b7530802`.
  Нет `DATABASE_URL`; единственный mount — read-only `/app/config.yaml`.
  Это текущий транспорт, а не уже действующий постоянный бюджетный учёт.
- Native config прочитана из SQLite через `mode=ro`: connection 0 — прямой
  OpenAI Responses; 3 — прямой DeepSeek; 1/2/4 — LiteLLM. У всех пяти нет
  дополнительных connection headers. Другие способы передачи идентичности
  этим наблюдением не исключены.
- Оба контейнера healthy, `RestartCount=0`. Ничего не перезапускалось;
  чаты, пользователи, тарифы, лимиты, конфигурация и маршруты не изменялись.
- Локально есть Python 3.11, Node 22 и Chrome. Docker CLI не найден;
  пригодный Linux/Docker-стенд пока не подтверждён. Производственный VPS
  не используется для сборки или репетиции.

Защищённая локальная квитанция и read-only сборщик —
`local/goal584/runtime.safe.json` и `runtime_inventory.py` в рабочей копии GOAL.
Ключи, значения секретных переменных, реальные пользователи и переписки не
попадали в отчёт. Ошибка первого чтения `config.data` исправлена после проверки
схемы: текущая таблица содержит `key/value`, а не один общий JSON-документ.

## Матрица штатных возможностей и решений

Проверенные исходники: Open WebUI v0.12.2,
`6a18585ff4c2e5f6805f682222cfbc46dc669ef8`; LiteLLM v1.105.1,
`d665dc1a6315847fcad6cc2c1264ceb47c06abce`. Текущие docs используются как
указатель, а поведение сверяется с этими версиями.

| Требование | Штатная возможность | Подтверждение на версии | Недостающий минимум | Решение на текущем шаге |
| --- | --- | --- | --- | --- |
| Tool открывает Rich UI без HTML в контексте модели | `HTMLResponse` + короткий result context | Middleware отделяет embeds от текста результата [1] | Привязать к авторизованному чтению владельца расходов | Подходит для свежего снимка при вызове Tool; старый экран обозначать снимком |
| Форма читает свежие данные и сохраняет подтверждённое изменение | Tool fresh read → prepared editable HTML → input:prompt:submit JSON → native confirmation/user turn → fixed Tool | Прямого RPC нет, но для LLM-mediated flow он не обязателен. Native own opaque embed допускается prompt handler [2] | На runtime доказать exact stored user-parent JSON, ACL/admin checks, backend diff/confirmation/apply/readback | Штатный candidate исходной живой формы; custom bridge не строим. Прежний вывод об обязательной замене формы был слишком широким |
| Серверные полномочия и подтверждение | Tool/Action получают `__user__`, `__request__`, `__event_call__` | Native Action проходит авторизацию и проверку чата; confirmation/input вызываются из Python [3] | Проверять текущую admin-роль, точные изменения и актуальность состояния после ожидания | Существующий владелец пользователей; подтверждение отправки prompt не считать подтверждением бюджета |
| Общий месячный бюджет и доли моделей | Scalar user/key budgets; отдельный `model_max_budget` | Native scalar core и adapter user/model проверены на actual image; per-model механизм относится к EE и устроен иначе [4] | Реальный WebUI, сумма долей, смена периода и параллельные вызовы | Один native user + ключ на user/model с отдельным scalar budget. Подбор ключа проверен с имитированными server headers; EE не обходится |
| Один журнал, историческая цена, принадлежность вызова | LiteLLM PostgreSQL spend logs и cost tracking | Есть стоимость события, provider-call ID, session/request metadata [5] | Зафиксированная версия тарифа/usage, полнота, неизвестная цена, служебные операции, durable recovery | Сохраняем одного владельца; отдельный ledger не создаём. Полная пригодность ещё не доказана |
| Стоимость ответа и всего чата со всеми ветками | Native usage merge и status events | Usage складывается по native tool rounds; outlet видит только выбранную ветку [6] | Читать итог по chat/answer из владельца расходов, а не суммировать только активную историю | Показ — отдельное расширение; стоимость из одного регистра |
| Штатное отключение отображения | Filter/UserValves; сохранённый `statusHistory` | Toggleable Filter отключает весь pipeline; UserValves может пропускать будущий status, но не скрывает сохранённые строки [7] | Обычная UI-проверка области сохранения и исторических статусов | Не размещать enforcement в отключаемом фильтре. Полное ретроспективное скрытие не обещаем |
| Охват платных маршрутов и LLM-контекста | Native custom header templates для CC и converted Responses | Есть user/chat/message/task; `MODEL_ID` на обычном пути пуст, root-call template нет; raw `/openai/responses` имеет иной путь [8] | Авторитетная привязка calls, два прямых подключения, provider clients внутри Tools/Pipes | Не переводить всё в CC. До выпуска доказать совместимость и полноту; клиентскую metadata не принимать за серверную принадлежность |

## Штатный candidate формы и альтернативный путь

**Основной candidate: живая HTML-форма и JSON через native prompt.** Tool читает
актуальные данные и возвращает редактируемую форму с временем и версией. Кнопка
формы передаёт ограниченный JSON через `input:prompt:submit`. Open WebUI спрашивает
разрешение отправить текст; затем модель может вызвать фиксированный Tool без
бизнес-аргументов. Tool читает оригинал JSON из native user-parent текущего
assistant, а не доверяет пересказу/аргументам LLM. Сервер заново читает
состояние, проверяет admin-роль, показывает точное «было → станет» штатным
confirmation и применяет изменение через владельца бюджетов после повторной
проверки. Обновление даёт новый экран. Это дополнительные ходы модели и,
возможно, два подтверждения; прямого RPC и гарантии выбора Tool моделью нет.

**B. Native Action и штатные диалоги, Rich UI для результата.** Tool открывает
снимок в чате. Кнопка Action под сообщением вызывает Python напрямую через
штатную авторизацию; ввод и точное подтверждение выполняются штатными диалогами.
Сервер повторно проверяет права/состояние и возвращает новый снимок/квитанцию.
Это более предсказуемый административный путь без выбора Tool моделью при записи,
но редактирование происходит в диалогах, а не внутри HTML-формы.

Основной candidate сохраняет редактирование в карточке и соответствует исходному
описанию пользователя; дополнительный model turn и native prompt confirmation
являются реальными пределами этого механизма. JSON виден в чате и модели, выбор
Tool не гарантирован, незавершённый draft не переживает rerender. Отдельная
авторизованная загрузка/запись из iframe не нужна для этой цепочки, но безопасное
изменение бюджета ещё не доказано на runtime. Альтернатива B меняет форму ввода и
не выбрана. Ослабление sandbox, инъекция `execute`, новый bridge не строятся.

## Владельцы и ближайший срез

Оставшиеся технические ограничения LiteLLM проверены по source, а не runtime:
`custom_auth` возвращает собственный auth-объект и сам по себе не доказывает
сохранение штатного scalar-key enforcement. Обнаружен существующий MIT-владелец
`authorize_internal_virtual_key`, который native Lens использует для проверки
серверного назначения ключа. Его результат нельзя просто вернуть из custom auth:
внешний auth-путь обнуляет поле reservation и может резервировать повторно.
Нужен один проверенный жизненный цикл проверки, резервирования, списания и
освобождения. Кандидат с model-specific keys остаётся возможным, но не выбран
как реализация. Native `model_max_budget` — отдельный EE-вариант, у которого в этой
версии также не доказана надёжность per-model счётчиков после cache miss и при
параллельной нагрузке. Покупка лицензии сама по себе эти вопросы не закрывает.

Более узкий кандидат для проверки: custom auth аутентифицирует доверенный
WebUI-вызов и выбирает серверное назначение ключа; `IdentityStore` и
`validate_resolved_virtual_key` выполняют штатную проверку без reservation;
внешний auth с `custom_auth_run_common_checks=true` единожды проверяет личный
бюджет и резервирует расход. Это внутренний seam точной версии, а не готовый
документированный продуктовый контракт. До принятия нужны проверка жизненного
цикла на pinned image, отказов/отмены/streaming, отсутствия orphan holds и
невозможности выбрать ключ другого пользователя. Производственный патч,
новый auth-владелец или обход EE для этого исследования не создавались.

Цена тоже требует отдельной проверки: default cost map изменяемый, блокировка
моделей без цены по умолчанию выключена, а отсутствие оценки может пропустить
reservation даже в строгом режиме. Есть штатные настройки заморозки map и
отклонения неизвестной цены. Их надо испытать на реальных категориях usage.
Raw `/spend/logs/v2` доступен в OSS; `/spend/report` относится к premium.

| Смысл → владелец → контракт → потребитель | Классификация |
| --- | --- |
| Пользователь и admin-роль → Open WebUI → native verified user / Tool/Action args → операция управления | Существующий владелец |
| Расход, допуск и остаток → LiteLLM → native auth/budget/spend API → управление и отображение | Предпочтительный существующий владелец; полнота пути проверяется |
| HTML, короткий контекст и видимый статус → штатные Tool/Action/Filter → embeds/context/status → пользователь чата | Тонкая адаптация представления; бюджетных вычислений не содержит |
| Последовательность чтение → предложение → подтверждение → проверка → запись → readback | Координатор; не владелец отдельного бюджета или регистра |

Прежнее требование обязательно выбрать A/B опиралось на слишком узкую предпосылку
о необходимости direct RPC. Повторная source-проверка нашла native путь исходной
формы; следующий административный proof проверит его без подмены интерфейса и
без обходной подсистемы. Независимый cost slice — связь native spend с
ответом/чатом и чтение стоимости из того же регистра — проверен ниже. Следующий
минимум: admin editable-form JSON/prompt/Tool vertical proof и native key access
по hash без employee secrets; затем readback historical rates и controlled native
reset. Далее остаются служебные категории, история цен,
calendar/concurrency/failure lifecycle и совместимость текущих маршрутов/Tools.
Полный изолированный пользовательский сценарий остаётся критерием закрытия;
отдельный live-check с платным API возможен только после отдельного согласования.

Срез native Action с read-only Rich UI детализацией и OFF budget-denial proof
принят ниже. Он не доказывает административную HTML-запись; для неё найден
отдельный штатный JSON/prompt candidate, также описанный ниже.

| Смысл → existing owner → контракт → потребитель | Роль нового блока |
| --- | --- |
| Доступ к своему ответу/чату → native Users/Chats → verified Action args + повторное native чтение → details Action | Representation-only adapter с проверкой owner output |
| Ledger URL/reader key → существующие native Filter Valves → Functions.get_function_valves_by_id → общий cost_readback | Повторное использование конфигурации, без второго ключа/хранилища |
| Начисленные суммы/модели/usage → native spend rows → CostSnapshot → подготовленный датированный HTML | Только отображение, не расчёт тарифов; каждый click читает свежие данные |
| Синтетический cap/restore → native key API → update max_budget + readback → browser OFF-denial | Только fixture call-order coordinator; никакого изменения production |

Proof сохраняет 6 успешных ответов / 8 physical calls / $1.60 и добавляет отдельный
fresh-chat отказ при OFF. Подписанный отказ нельзя скрывать: отдельный scope,
неизменные provider IDs/spend и все native rows отказного чата, включая zero/failure,
проверяются отдельно. Details Action не меняет content ответа и не вызывает LLM;
последующий модельный вызов должен подтвердить отсутствие HTML в контексте.

Candidate details/OFF реализован: новый `cost_action.py` возвращает native
`HTMLResponse` tuple, использует прежние Filter Valves/reader и повторно проверяет
native user/chat/assistant/model. Модель/цена не вызываются и не рассчитываются.
48 component tests прошли (включая 6 Action cases с реальным локальным HTTP reader),
синтаксис Python/22 Bash/8 embedded Python и actionlint прошли. Offline OFF phase
rehearsal подтверждает только `max_budget` writes, restore, drift rejection и
проекцию всех zero/unknown rows. Exact verifier replay использует 8 прежних actual
positive rows с явно synthetic additions для OFF/details: 5 допустимых вариантов
приняты, 8 подмен отклонены. Это не runtime acceptance новых сценариев.
Локальные evidence: `local/goal584/litellm/rehearse-off-denial.py`,
`local/goal584/cost-display/rehearse_details_off_verify.safe.json`.
HTML renderer rehearsal в Chrome156.0.8078.76 также прошёл: native sandbox без
same-origin, точные DOM markers/Decimal/tokens/UTC, fresh-first порядок new+old,
height518/550 без обрезания на ширинах1440/640, CSP/page errors0 и HTTP/WS0.
Browser закрыт, серверы не запускались. Evidence:
`local/goal584/cost-display/details-preview/browser.safe.json` и PNG рядом.
Это проверка подготовленного renderer, не доказательство native Action API.
Candidate `041c0a31bb086ad97010822a8db933ee51b3d4f9` отправлен в PR #585;
[native run 41480903008](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41480903008)
завершился failure на driver assumption о формате Action result; Active CI прошёл.
Stock runtime установил Action и показал правильный $0.40/$0.40 Rich UI, POST
Action вернул200. Native `process_tool_result` (middleware1304–1317) сериализует
short context в строку, Action endpoint JSON-encoded эту строку; driver ошибочно
ждал объект. Exact native function replay подтвердил wire string + HTML embed.
Driver исправлен под этот контракт без изменения продукта. OFF фаза ещё не
выполнялась; provider содержит2 вызова первого Tool-ответа, cleanup0/0. Артефакты:
`local/goal584/runtime-proof-41480903008/receipts`; нормализация —
`local/goal584/cost-display/rehearse_native_action_result.safe.json`.
Fresh corrected candidate `456d8ba1c79835fd93645a9c138218ae41391f07`,
[native run 41483259887](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41483259887),
завершился failure на ожидании driver, что число persisted details embeds
обязательно вырастет с1 до2; Active CI success. OFF helper перед
изменением cap теперь bounded-polls native counters до ожидаемой границы, сохраняя
точные ожидаемые суммы и запрет на изменение spend/reset/identity. Новые
Action/OFF результаты полностью ещё не приняты. Raw evidence уже подтверждает
6 successful replies / 8 provider calls, native key cap0.8 при spend0.8,
OFF-denial с provider IDs4→4 и неизменными user/key spend, restore10 и успешное
продолжение при OFF. В exact-session и user-delta readback отказа строк не найдено;
это явно отмечено отсутствием, а не доказательством бесплатности. Финальный
скриншот показывает refreshed answer0.4/chat1.2 с корректными A/B token tables.
Но driver не сохранил сам последний API metadata sample, поэтому причина
неизменного count ещё не доказана. Fixed criterion теперь требует **новый HTML
из native persisted message**, новый timestamp и верные суммы/tokens, независимо
от append/replace поведения; на timeout сохраняет counts и same-as-prior flags.
Не требуется выдуманное накопление карточек. Локальная репетиция принимает
6 вариантов (включая replace) и отвергает10 подмен (включая stale snapshot).
Артефакты failure: `local/goal584/runtime-proof-41483259887/receipts`, cleanup0/0.

Candidate `3af2cf7f001781d1a59693c95b6fa9909c69f7c8`,
[run41485475419](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41485475419),
подтвердил свежие persisted details: первый снимок0.4/0.4, второй0.4/1.2;
actual counts в этом run1→2, новый HTML/timestamp добавлен первым. У предыдущего
failure456d8ba1 count не был записан; причину нельзя восстанавливать по одному PNG.
OFF block/restore и все6success/8physical вызовов также прошли. Driver остановился
на ожидании foreign Action401, но actual native gate вернул404. Это корректный
`main.verify_chat_ownership`2112–2130 contract, отличный от chat GET401; чужие
данные не вернулись. Driver и verifier исправлены на точный404, проверки доступа
не отключаются. Артефакты: `local/goal584/runtime-proof-41485475419/receipts`, cleanup0/0.

Перепроверка основного GUI: `local/goal584/rich-ui/native-form-json-prompt-recheck.md`
подтверждает source-feasible editable HTML → `input:prompt:submit` JSON → native
confirmation/user turn → fixed zero-arg Tool → DB user-parent текущего assistant.
`action:submit` для точного JSON не подходит: отправляет текущий prompt вместо
event.data.text. Native Chats helper не проверяет ACL сам, поэтому backend должен
сначала проверить native owner/роль и ещё раз полномочия после confirmation.
Это исправляет прежнюю слишком широкую предпосылку про обязательный direct RPC;
следующий административный vertical slice проверит original flow на runtime.
JSON виден модели/пользователю; HTML остаётся prepared UI, draft при rerender
не сохраняется, выбор Tool моделью не гарантируется. Новая bridge-подсистема
или ослабление iframe для этого candidate не нужны.

Для следующего admin proof источник назначения остаётся native LiteLLM key
metadata. Source API review подтвердил `/key/list` exact user_id/key_alias с
пагинацией и `/key/info`, `/key/update` по hash: employee secrets в WebUI не нужны.
Существующий pure assignment contract из `litellm_auth.py` нужно переиспользовать
нейтральным модулем, не копировать alias/predicate в Tool. Fixture operator уже
имеет info/update/new/generate; для listing требуется добавить только `/key/list`.
Сначала проверить перечисление/изменение/restore по hash на стенде без inference.

**Details/OFF accepted slice:** candidate `53192f603e741d6f488b84762a6f335a5832d61e`,
tested merge `e77cc2d2ff6de16e68b2add97fd34b16fcb3bdd4`,
[run41487063627](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41487063627)
и Active CI — success. Parent прочитал59 JSON/2 HTML, сверил17 Git blob hashes
и ZIP digest с GitHub, повторно выполнил exact verifier на raw runtime receipts;
просмотрены initial/refreshed details и OFF denial PNG. Full suite48 содержит
3 skipped native-source checks; 9 provider tests ранее прошли локально.

Native Action повторно показывает тот же ответ0.4, свежий чат0.4→1.2 с breakdown
A2calls20/10/30tokens0.4 и B4calls40/20/60tokens0.8. В этом run fresh persisted
snapshot заменил один прежний embed (1→1); счётчик карточек не часть контракта.
Content/output и provider IDs вокруг Action не менялись, HTML не попал в следующий
native/provider context. OFF key denial: cap0.8/spend0.8/user1.8personalcap20,
provider4→4 и неизменные spend/reset/identity; native restore10 вернул B при OFF.
Отказ сохранён отдельным signed attempt:9 signed =8 completed +1 denied,
плюс1unsignedraw. All exact-session и user-delta rows отказа явно отсутствовали;
это не объявляется zero-cost evidence. Финал6success/8physical/$1.60,
первый чат1.20; user totals2.60/0.20. Доступы: chat GET401, foreign Action404,
forged own-chat answer400, unsigned raw403. Cleanup0containers/0volumes.

Независимый contract-outcome-review D1–D5 — PASS по raw artifacts и исходникам;
нормативный источник — полный issue584. Native core/gateway/restart и прежний6/2
browser сценарий сохранены. Evidence:
`local/goal584/runtime-proof-41487063627/receipts`, `parent-review.safe.json`
и `contract-details-off-review.md` рядом. Полный GOAL остаётся в работе:
административная форма пока не реализована; service/delegation settlement,
failure/concurrency/calendar/pricing и полный current-route coverage не приняты.

## Воспроизведение и границы доказательств

### Независимый срез: штатный бюджетный core

Подготовлена ограниченная репетиция на закреплённом LiteLLM image без custom auth:
[Compose](../../compose/goal584.native-budget-proof.yml),
[HTTP driver](../../scripts/goal584-budget-proof/prove_native_budgets.py) и
[сверка полученных провайдером вызовов](../../scripts/goal584-budget-proof/verify_provider_calls.py).
[Узкий workflow](../../.github/workflows/goal584-native-budget-proof.yml) запускает
только этот срез на изолированном GitHub runner; существующий Active CI сохраняется.
Runtime proof прошёл в
[run 41435187180](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41435187180):
branch head `2044cb8995852365c4a0f3bffee5cde9c345c279`, испытанный merge
`2b2f015b80a37763cd4f5417b90e120e9aa5684a`. Артефакты прочитаны и независимо
приняты только для native scalar user/key core: 7 положительных spend rows и
7 совпавших provider response IDs, по 10/5 tokens и синтетическим $0.20 на вызов;
итоговые user spends $1.20/$0.20 совпадают с ключами и журналом. Два typed
budget denials не дошли до имитатора; повышение бюджетов восстановило доступ.
Подмена body user/metadata не изменила native владельца расхода. Фактические
образы и SHA-256 fixture файлов связаны с runtime receipt; после теста осталось
0 контейнеров и 0 volumes проекта. Локальная копия пяти квитанций —
`local/goal584/runtime-proof-41435187180/`; hosted artifact имеет retention 7 дней.
Это не приёмка GOAL целиком.

Сохранённые ошибки предыдущих попыток: в запуске
[41433766446](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41433766446)
четыре сервиса стали healthy и миграции завершились, но runner не смог обратиться
к опубликованному loopback-порту. Ошибка не доказывает дефект бюджета: API-вызовы
не начались. Следующий кандидат исполняет тот же standalone driver внутри
существующего proxy-контейнера через его native HTTP endpoint; защита сети и
авторизации сохраняется. Затем
[41434395675](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41434395675)
подтвердил первые три расхода и отказ по бюджету, но обнаружил ошибочную предпосылку
driver о HTTP 400/429: pinned `litellm.budget_exceeded_status_code` равен 422.
Проверка исправлена на точный 422 + `budget_exceeded` + native Key/User scope;
квоты и конфигурация ради зелёного результата не менялись.
Ранее workflow был отклонён до job из-за `runner` context
в job-level env; исправлено и проверено actionlint 1.7.12.
Продуктовая приёмка не подменяется этим тестом.

Четыре временных сервиса: LiteLLM, PostgreSQL, Redis и stdlib-имитатор провайдера
в том же pinned LiteLLM image. Образы закреплены digest, сеть internal, host ports
отсутствуют; платных провайдеров нет. Credentials генерируются
для каждого запуска. Проверка создаёт двух синтетических пользователей и четыре
single-model ключа, сопоставляет реальные native spend logs, суммы пользователя
и ключей, usage, модель и root-answer metadata с семью успешными вызовами. Два
дальнейших запроса должны быть отклонены по разным пределам без обращения к
имитатору. Изменение бюджетов через native API должно восстановить доступ.

Денежные суммы здесь синтетические: 10 input × $0.01 + 5 output × $0.02 = $0.20.
В тесте отдельные key caps намеренно в сумме превышают personal cap, чтобы
проверить оба независимых native ограничения. Это не допустимый шаблон долей
для конечного интерфейса: правило суммы 100% ещё предстоит реализовать и принять.
Также не приняты GUI, доверенный подбор ключа по WebUI-user/model, реальный тариф,
Responses, streaming/cancel/concurrency, смена месяца и полная история чата.
Перед внешним запуском проверены точные source/API/schema, локальный HTTP mock,
синтаксис, изоляция и независимое ревью. Сверка provider receipts отвергает
изменённые context/model/usage и лишний вызов.

Следующий независимый backend-срез — узкий native custom-auth adapter без изменения
LiteLLM source. Он должен выбирать существующий user/model key, передавать проверку
и единственный reservation native владельцам и сохранять management RBAC. Master
recovery и master-only routes требуют явной границы; ad-hoc admin auth не допускается.
Service-task exemption пока не включать: один shared gateway secret доказывает
происхождение соединения, но не достоверность всех TASK/CHAT/MESSAGE metadata.

Уточнение происхождения подтверждено по pinned source и replay: raw
`/openai/chat/completions` переносит клиентские TASK/CHAT_ID/MESSAGE_ID в headers,
тогда как USER_ID берёт из аутентифицированного пользователя. Raw Responses
оставляет клиентскую metadata в body и даёт пустые task/chat headers. Даже native
task endpoints принимают caller chat_id без проверки владельца. Поэтому не
освобождаем от личного бюджета произвольный nonempty TASK и не связываем сервисный
расход с чатом только по этому полю. Legacy function_calling и MOA также нельзя
автоматически считать служебными: это части пользовательского ответа.
Закрытие внешних raw-путей через существующий ingress — только условный кандидат,
требующий согласования совместимости и проверки всех обходных маршрутов, включая
generic proxy, Anthropic/Ollama/embedding paths. Рабочие маршруты не менялись.
Подробные URL и source replay — ignored
`local/goal584/cost-display/provenance-followup.md`.

Кандидат этого среза —
[litellm_auth.py](../../deploy/openwebui-budgets/litellm_auth.py), без изменения
LiteLLM source. Native key alias и metadata задают назначение user/model в
существующей таблице ключей; bounded lookup и native IdentityStore/validator
не ведут собственных расходов. Gateway-ветка требует server-held credential,
native USER_ID и присутствующий пустой TASK. Missing/nonempty TASK и model-less
discovery пока отклоняются, а не становятся бесплатным обходом. Management
работает через настоящий scoped proxy_admin virtual key, созданный stock API
до включения hook; master-only routes читаются из native enum, stock master
не подменяется. Для его восстановления требуется stock config.

[Qualifier](../../scripts/goal584-budget-proof/prove_gateway_auth.py) подготовлен
для bootstrap → hook-enabled run → cold proxy/Redis restart. Он повторно использует
native 7/2 сценарий с имитацией trusted WebUI headers, отдельно проверяет запреты
и native operator access. Сырые fixture-ключи остаются в private state 0600 вне
публикуемых квитанций. Повторный alias проверяется через native API rejection,
а не через внедрённый дубликат БД.
Actual-image runtime прошёл в
[run 41440455795](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41440455795):
head `0bbe61deb13e3ae682237f71d1155866d0255b51`, испытанный merge
`5bb26cbafb1d4c019c1ee7b5b87a6efdba05dbd4`. Source hashes сверены, 11 артефактов
прочитаны и независимо приняты только для этого среза. После bootstrap native
operator сохранил management role/allowed_routes; через gateway повторились
7 успехов и 2 бюджетных отказа. Девять дополнительных auth/provisioning отказов
не создали лишних provider calls. После cold restart proxy и Redis сохранились
users/keys/7 log rows и повторился personal-budget denial. Сверка actual provider
IDs/context/usage и cleanup подтвердила 0 лишних вызовов, 0 контейнеров/volumes.
Квитанции — `local/goal584/runtime-proof-41440455795/`.
Предварительно проверены точные symbols/signatures, исходные контракты, обычная
импортируемость mounted файлов, HTTP-пакет с присутствующим пустым TASK, YAML,
Bash, Python и независимое source review. Это не приёмка WebUI или lifecycle
резервирования при параллельных вызовах/сбоях. Единственность inflight hold отдельно
не измерялась; вывод о владельце reservation пока ограничен исходниковой делегацией
и проверенными завершёнными вызовами.

Настоящий WebUI native model-discovery и пользовательский chat-path с этим
адаптером проверены ниже. Pinned source обнаружил более простой штатный путь:
непустой connection `model_ids` строит каталог внутри WebUI без upstream GET
`/models`; native Workspace model read grants задают доступ обычным сотрудникам.
Отдельный catalog principal не требуется. Native `/openai/verify` при этом всё
ещё вызывает gateway discovery и не поддерживается текущим hook.
Управление формой,
служебные задачи, ingress/provenance, price versions и полный chat/tool accounting
остаются отдельной незавершённой частью того же GOAL. Диалоговая альтернатива B не
выбрана; native JSON/prompt candidate сохраняет исходное редактирование в HTML.

### Настоящий WebUI-стенд

[Compose overlay](../../compose/goal584.webui-proof.yml) добавляет официальный
`v0.12.2-slim` с immutable index
`sha256:34db70a8e8f305dc996c4b459db0949b715400a489ca8a2d1a2a31ae5ddc67bb`.
Registry labels и `WEBUI_BUILD_HASH` совпадают с pinned source `6a18585…`.
У сервиса отдельный disposable volume, internal network и нет host ports.

[Provisioner](../../scripts/goal584-budget-proof/provision_webui.py) использует
native signup/admin-add, connection config, model grants и task config. Два
реальных WebUI UUID становятся LiteLLM user IDs; каждому назначаются $0.80 и
две доли по $0.40. Credentials хранятся вне публикуемых артефактов. Для этого
plain-chat среза генерация title/tags/follow-up и прочих auxiliary tasks выключена
штатной настройкой; это не решение их учёта и не настройка production.

[Browser qualifier](../../scripts/goal584-budget-proof/prove_webui_browser.py)
входит двумя обычными пользователями через форму и отправляет восемь свежих чатов
через native selector/input/send. Ожидаются шесть streamed ответов, два видимых
бюджетных отказа, сохранённый terminal outcome каждого чата, независимость второго
сотрудника и восстановление первого после fixture-увеличения user/key caps.
После каждого действия readback сверяет native user/key spend; provider IDs,
контекст, usage и число фактических dispatch сверяются отдельно. Увеличение
fixture caps через native API не считается приёмкой административной GUI.

Предварительные Python/YAML/actionlint и независимая source/schema проверка
прошли. Репетиция verifier отклонила лишний dispatch, лишний контекст, чужого
владельца, потерю output cap, пропавший отказ, изменённый usage и повторный chat ID.
Локально нет Docker; фактический запуск будет в том же ограниченном Actions job.
Ни эти проверки, ни registry metadata пока не доказывают runtime WebUI.

Первый [runtime 41446525429](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41446525429)
на head `97609bd3306bca126dcef3c61e4eaf5cbb00bea9` запустил healthy stock WebUI,
подтвердил image/source identity, native users/config/model grants/output cap и
обычный вход в Chrome `156.0.8078.47`. UI qualifier остановился на ошибочной
предпосылке `messages` в browser submit: свежий native чат передаёт `user_message`,
а сервер восстанавливает контекст. Дополнительно реальный шлюз отклонил первый
запрос с оценкой $32.61 при spend=0/cap=$0.40. Cleanup подтвердил 0 containers/volumes.
Артефакты сохранены в `local/goal584/runtime-proof-41446525429/`.

Наблюдаемая причина пока уточняется: source подтвердил, что пустая model meta
в реальной UI session включает native built-in tool schemas по умолчанию, даже
без selected tool IDs. Это расходится с заявленным plain-chat fixture. Кандидат
повторной проверки сначала воспроизводит такой запрос и записывает реальный
gateway context/native estimate через **стендовый** документированный custom-auth
delegate; затем native model capability `builtin_tools=false` переводит только
fixture в plain-chat режим. Caps/цены сохраняются. Проверка требует actual context
до/после, terminal отказа и исходного 6-success/2-denial сценария. Delegate
только наблюдает ограниченный синтетический контекст и вызывает тот же product
auth; ни user/key selection, ни резервирование он не заменяет. Production этот
диагностический delegate не использует.

Повторный [run 41448622582](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41448622582)
на `24aabaa1ad07c6f2fc34569af366ccc8d95f18e2` прошёл прежние native/adapter
контроли, но остановился при загрузке диагностического delegate, до WebUI-чата.
Pinned config loader загружает файл относительно YAML, не добавляя `/proof` в
`sys.path`; top-level sibling imports оказались неверной предпосылкой. Ошибка
воспроизведена локально **тем же** `get_instance_fn` из pinned source. Исправление
оставляет top-level зависимости stdlib и загружает product delegate через тот же
native config-relative loader; отдельные load-проверки wrapper/product прошли.
Это исправление стендовой диагностики, а не изменение product auth или бюджетов.

[Run 41449388745](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41449388745)
на `ff53345aa413eb494e4f58efd3e9266f019d49c5` прошёл загрузку и native model
update/readback. Реальный baseline context содержал один `Hi`, `max_tokens=5`
и **30 native tool schemas**; native estimator и сохранённая UI-ошибка совпали
на $32.61. Затем браузер подтвердил два ответа на A, terminal budget denial A
и успешный ответ на B. На сверке трёх расходов qualifier обнаружил ошибку своего
точного сравнения: native aggregate `0.6000000000000001` против Decimal `0.60`.
Необходима только tolerance для представления float; caps и расходы не меняются.
Исправленный comparator проверен на **этом фактическом snapshot**, принимает шум
до $1e-9 и отклоняет разницу $0.01/$0.20. Failure capture дополнен provider/context
readback, чтобы не терять последующие diagnostic rows. Cleanup прошёл; артефакты
— `local/goal584/runtime-proof-41449388745/`. Полный 6/2 сценарий ещё не принят.

Окончательный [run 41450358692](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41450358692)
прошёл на head `f2a0b792993b6e792a9ed76570ea3d2530ab4b2e`, испытанный merge
`0a99119c330550097437df6e85d597baf854adc3`. Parent readback 38 JSON и сверка
11 нормализованных source SHA-256 подтвердили точную идентичность. В Chrome
`156.0.8078.47` два обычных native пользователя выполнили восемь свежих чатов:
шесть ответов, два terminal key-budget отказа, успешный вызов второго сотрудника
и восстановление первого после fixture-изменения caps. Screenshots подтверждают
видимый ответ/ошибку. Последние native user spends — $1.00/$0.20; final caps
первого — user=$1.20, A=$0.80, B=$0.40. Ровно шесть positive spend rows совпали
с шестью actual provider IDs, моделями, single-Hi input, stream/output cap 5,
usage 10/5 и стоимостью $0.20 каждого. Лишних provider dispatch нет.

Девять gateway observations отдельно связаны с видимыми UI attempts по порядку,
actual USER_ID/model/TASK/input. Baseline: 30 built-in schemas, оценка $32.61 и
совпадающий сохранённый UI-отказ. После native capability update — 8 запросов без
tool/legacy function schemas, тот же `Hi`, max_tokens=5 и native estimate **$0.18**.
Это устранило fixture-context mismatch; инструменты продукта этим срезом не
принимаются. Native текст ошибки пока технический, содержит alias/маску ключа.
Оба browser-отказа — key-budget; отдельный personal-budget guard проверен прежним
native 7/2 сценарием, а не изолирован этим normalized-share UI-прогоном.

JSON-проверка не нашла сырых credential/JWT значений; screenshots сделаны после
обычного входа. Cleanup подтвердил 0 containers/volumes с project label, включая
WebUI SQLite volume. Артефакты и parent review —
`local/goal584/runtime-proof-41450358692/`. Draft PR обновлён результатом;
полный GOAL не принят. Управление через HTML и ответ/chat cost display всё ещё
отсутствуют; ни native runtime, ни этот UI-срез не подменяют оставшиеся требования.
Независимая приёмка по `contract-outcome-review` прочитала те же 38 JSON и все
9 PNG, подтвердила merge/head/source binding и дала PASS только W1–W5 этого
среза: stock identity/обычные пользователи, 6/2 UI, единый spend/provider,
контекст до/после и cleanup. Полный GOAL и перечисленные исключения не приняты.

### Следующий продуктовый срез: подписанная принадлежность и cost display

Выбран candidate без нового ingress/route: native non-toggleable `Filter.request`
передаёт server-produced JWT в native `litellm_metadata`; existing LiteLLM custom
auth проверяет его и оставляет только canonical scope в native spend metadata.
CC и converted Responses сохраняют это поле в exact source. Подпись использует
ключ **существующего** native gateway connection через `get_openai_connection`,
не дублированный secret Valve. Actual model/body/контекст выбирает прежний router.
Сверка connection/base-model нужна только для проверки и подписи связи, не
перенаправляет вызов. Raw-call metadata без валидной подписи не становится
доверенной принадлежностью; strict mode требует подпись на shared gateway.

| Смысл → владелец → контракт → потребитель | Классификация |
| --- | --- |
| Actual user/chat/assistant и выбранное соединение → native WebUI auth/Chats/models/config → server Filter args + native reads → JWT scope | Проверка существующего owner output, representation-only adapter |
| Корневая принадлежность native subagent → существующий controller `chat_context` copy → подписанная root capsule + server `internal=True` → child scope | Представление связи; импортируемой `Chat.meta` недостаточно |
| Call/chat/root IDs → signed scope → existing auth → `spend_logs_metadata.owui_budget` + native session/trace | Представление; не содержит цен, расходов, резервов или второго ledger |
| Начисленная сумма и usage → native spend API → exact session rows с native ACL → display projection/status | Только группировка уже начисленного; без расчёта тарифов |
| Видимость → native UserValves → default-enabled preference → будущие status emissions | Отдельно от обязательного signing и native enforcement |

Wire contract v1: PyJWT уже есть в обоих pinned runtime (WebUI requirement
2.13.0, LiteLLM >=2.13,<3). HS256, issuer `corp-openwebui-budget-v1`, audience
`litellm-budget-call-v1`, lifetime <=300s; claims `schema=1`, `sub`, `chat_id`,
`answer_id`, `root_chat_id`, `root_answer_id`, `model` (wire alias), `jti`, `iat`,
`exp`. Carrier key — `litellm_metadata.owui_budget_provenance`. Root capsule —
`metadata.chat_context.owui_budget_root`, separate audience `openwebui-budget-root-v1`
and <=24h lifetime for native delayed controller work. Only server internal
children may inherit it; ordinary/resumed answers use their actual new IDs.
Neither token nor secret may reach provider, displayed status, model messages
or persisted cost metadata. Persisted `owui_budget` records only validated IDs,
wire model, call nonce and category `personal`; native owns cost/usage/physical IDs.

Implementation must not equate request-filter invocations with physical calls:
resume/approval preflight invokes it without inference. Observed provider IDs
may be a request-local technical receipt for outlet readback; missing or unsettled
evidence must stay pending/unknown. Background children, non-streaming errors,
retention/loss and native queue/counter transaction boundaries need separate proof.
UserValves suppress future emissions only; historical native status remains.
This is the next implementation contract, not runtime acceptance.

Реализован candidate: `provenance.py`, `cost_filter.py`, `cost_readback.py` и
проверка/удаление подписи в существующем `litellm_auth.py`. Подпись связывает
authenticated user, actual/root chat и answer, wire model и уникальный call nonce;
native route-selected metadata получает только проверенные поля. Конкурирующая
session attribution из headers и Anthropic-compatible `metadata.user_id`
отклоняется. Native reservation и pricing не менялись.

Локально прошли 42 component/protocol/readback проверки и 9 реальных HTTP/SSE
проверок synthetic provider. Native-source AST/cache проверки используют exact
ignored checkout; в stock WebUI-контейнере без LiteLLM checkout они будут skipped,
а не runtime evidence. `Valves` сохраняются через native JSON owner; reader key
доступен только admin и ограничен session spend GET. Проверка чистоты returned
spend rows не является чтением всех DB columns: native API исключает prompt/response.

Подготовлен обычный browser сценарий: native Function install, mandatory model
attachment, default-enabled UserValves, multi-step Tool, смена модели в одном
чате, regeneration с сохранением старой ветки, выключение показа и продолжение
учёта в новом чате после reload, повторное включение и проверка итоговой суммы.
Ожидаются 6 ответов / 8 физических вызовов / $1.60 synthetic cost; новые расходы
сверяются с прежними native counters, а не обнуляют их. Это план проверки кандидата,
не утверждение, что сценарий уже выполнен. Предыдущая browser-приёмка выше остаётся
привязана к своему commit и не доказывает новые файлы.
До CI exact verifier воспроизведён на representative synthetic fixture: корректные
6/8 приняты; 12 отрицательных мутаций (компенсирующая перестановка root у скрытых
вызовов, actual scope/header и provider semantic fields) отклонены. Локальный
receipt — `local/goal584/cost-display/rehearse_cost_browser_verify.safe.json`.
Это проверка verifier, не browser acceptance. Actionlint и синтаксис 22 Bash /
8 embedded Python шагов также прошли.

Candidate `9776b4c4342a4293f55f0860db031efe27e7dd0f` отправлен в draft PR #585.
[native proof 41472124715](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41472124715)
завершился failure на browser driver regeneration: role locator нашёл и native
dropdown `span[role=button]`, и вложенную кнопку с тем же именем. До этого stock
install, unit runtime, прежние 6/2 browser outcomes с новыми cost statuses,
первый Tool-ответ ($0.40/$0.40) и смена модели ($0.20/$0.60) прошли. Полный cost
lifecycle не принят. Provider receipt нового сценария содержит 3 фактических
вызова; cleanup — 0 containers/volumes. Артефакты сохранены в
`local/goal584/runtime-proof-41472124715/receipts`. Уточнён driver selector до
native `button[aria-label=Regenerate]` внутри exact message card; продуктовый
код/квоты/проверки результата не менялись. Active CI этого candidate — success.

Повторный candidate `619e770255004441b7023ca0ea1fb5ab6b03c4d8` проверен в
[run 41473302289](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41473302289).
Отдельная сверка трёх реальных cost-scenario inputs предыдущего run показала
только штатное добавление `stream_options.include_usage=true` между gateway и
provider; auth before/after поля совпали. Это native
`common_request_processing._stream_usage_tracking_updates` (503–530, вызов 2153–2164),
а не изменение контекста нашим адаптером. Exact helper replay: 8 случаев и
3 actual receipt pairs, `local/goal584/cost-display/native_stream_usage_replay.safe.json`.
Diagnostic capture/verifier дорабатываются для явного readback этого native
преобразования; field не исключается из проверки. Общая runtime-приёмка остаётся
незавершённой.

Run 41473302289 завершился failure именно на `stream_options` сравнении старого
verifier. Все 6 browser replies, обе native UserValves смены, reload/исторический
статус, regeneration и hidden новый chat выполнены; foreign chat — 401,
unsigned raw inference — 403. В provider receipt 8 вызовов, final native receipt
содержит соответствующие scopes/usage/spend; cleanup 0/0. Эти evidence сохранены
в `local/goal584/runtime-proof-41473302289/receipts` и не переобозначаются green run.

Diagnostic delegate теперь вызывает **сам native helper** с текущими settings,
router/model support и native `auth.team_id`; сохраняется только его узкий patch.
Verifier сравнивает все captured semantic fields с body + этим patch; auth
before/after остаётся строго равным. Оба допустимых source-replay варианта и
17 отрицательных мутаций проверены. Новый verifier также проходит на фактических
8 provider/native rows предыдущего run с source-derived patch; это локальная
репетиция, а новый runtime capture ещё должен быть проверен на свежем candidate.
Receipt — `local/goal584/cost-display/replay_actual_cost_verifier.safe.json`.

Fresh candidate `b8a34e6701a4b02da6baae054890df80edf3088b`,
[run 41474653568](https://github.com/Kwentin3/corp-openweb-ui/actions/runs/41474653568),
завершился success; Active CI также success. Parent readback 53 JSON и replay
verifier на raw runtime receipts прошли; 16 Git blob SHA-256 совпали с runtime,
ZIP digest совпал с GitHub artifact. Проверены native PyJWT 2.13.0 и 42 unit
checks (3 source-AST проверки skipped в контейнере). В CI выполнены все 6 новых
ответов / 8 physical calls / $1.60; первый чат $1.20 включает regeneration,
скрытый ответ и Tool. UserValves off/on сохранены native API; hidden model/chat
после reload продолжает учёт, старые statuses видимы. Foreign chat — 401,
unsigned raw call — 403, лишних provider calls нет. Подписи удалены перед provider;
контекст auth before/after совпал, последующая native usage normalization явно
сверена. Cleanup 0 containers/volumes. Артефакты:
`local/goal584/runtime-proof-41474653568/receipts`, parent audit — `parent-review.safe.json`
рядом с ними. Ключевые hidden/restored/control PNG просмотрены; независимый
contract review C1–C5 всего этого staged slice — **PASS**. Reviewer самостоятельно
прочитал raw receipts, источники и PNG, повторно связал 8 nonce/ledger/provider IDs
и сверил 16 SHA-256. Это приёмка только явно перечисленного COST milestone,
не полного GOAL и не production. Подробный результат —
`local/goal584/runtime-proof-41474653568/contract-cost-review.md`.

Дополнительный runtime budget denial именно при выключенном показе,
details Action и delegated/background settlement остаются вне текущего cost slice.

Независимый read-only следующий срез: native `1mo` поддерживает календарное первое
число с global timezone/reset_time; текущий scalar `30d` также special-cased как
календарный. Runtime boundary/cache admission ещё не проверены. Native
`model_map_information` строится отдельным lookup при логировании, а actual custom
charge может выбирать deployment ID: фиксация реально использованной версии ставок
пока не доказана. Следующий минимум — readback этих полей и controlled native reset,
без второго ledger/scheduler. Подробности: `local/goal584/litellm/calendar-price-native-next.md`.

### Rich UI sandbox

В Chrome `156.0.8078.76` дополнительно выполнена sandbox-репетиция с теми же
реальными обработчиками и фиктивным локальным cookie-auth backend. При
`sandbox="allow-scripts allow-downloads"` iframe имел origin `null`; чтение
parent DOM/storage, собственного storage и cookie завершалось `SecurityError`.
Родитель получил 200 с тестовой cookie, запрос iframe с credentials пришёл без
cookie и получил 401; ответ iframe прочитать не смог. Прямые Tool/Action/execute
сообщения не создали backend-вызовов; prompt отправился только после подтверждения.
Это настоящая браузерная проверка границы с fake backend, **не приёмка полного
Open WebUI**, серверных ролей или бюджетов. Квитанции —
`local/goal584/rich-ui/browser-sandbox-result.json` и `browser-cleanup.json`.
Тестовый сервер и принадлежащий проверке Chrome остановлены, слушателей не осталось.
Временный профиль остался в ignored-каталоге: автоматическая проверка отклонила
удаление (`blocked by policy`), в том числе после явной проверки пути и процессов.

Из рабочей копии репозитория:

```powershell
git clone --depth 1 --branch v0.12.2 https://github.com/open-webui/open-webui.git local/goal584/open-webui
git -C local/goal584/open-webui rev-parse HEAD
node scripts/prove-goal584-rich-ui.cjs local/goal584/open-webui
```

Скрипт проверяет полные SHA-256 двух upstream-файлов после нормализации CRLF→LF
и исполняет извлечённые реальные обработчики в Node VM с минимальными host stubs.
Проверены snapshot payload, отсутствие прямого Tool/Action/execute RPC, отказ
чужому opaque window и prompt submit только после подтверждения. Это не полный
WebUI, не проверка серверной авторизации и не изменение бюджета.

Дополнительный offline replay в `local/goal584/cost-display/` исполнил функции
headers/usage/history/Responses на синтетическом system/user/tool контексте:
два шага дали 30 input, 5 output, $0.03; выбранная ветка дала $0.03 при $0.05
со всеми ветками. `statusHistory` не вошёл в поля replay. Это наблюдение над
функциями pinned source, а не фактический оплаченный provider-call или приёмка
целостности runtime-контекста. При интеграции окончательный вход провайдера
предстоит сверить до/после существующей ограниченной наблюдаемостью.

Подробные source manifests и квитанции делегированных проверок сохранены в ignored
`local/goal584/{rich-ui,litellm,cost-display}`. Два исходных checkout сверены после
нормализации строк: Chat, FullHeightIframe и middleware совпали. Сторонние
runtime-пакеты не устанавливались. Production остался без изменений.

## Источники и опыт сообщества

1. [Разделение HTML и result context](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/middleware.py#L1116-L1137), [официальный Rich UI](https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/).
2. [Полный iframe handler](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/common/FullHeightIframe.svelte#L157-L181), [prompt bridge](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/chat/Chat.svelte#L1732-L1811), [Tool embed без payload](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/common/ToolCallDisplay.svelte#L183-L192).
3. [Авторизованный Action route](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/main.py#L2151-L2161), [Action context](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/actions.py#L49-L122), [направление event_call: сервер → браузер](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/socket/main.py#L1500-L1538).
4. [Документация бюджетов](https://docs.litellm.ai/docs/proxy/users), [pinned auth](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/auth/user_api_key_auth.py), [границы custom auth](https://docs.litellm.ai/docs/proxy/custom_auth), [календарь и часовой пояс](https://docs.litellm.ai/docs/proxy/budget_reset_and_tz). Custom auth не считать автоматически эквивалентом stock key-budget enforcement; выбор токена ещё не доказан.
   [Native internal key authorization](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/auth/user_api_key_auth.py#L3938-L3977), [его Lens caller](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/lens/billing.py#L29-L109) и [обнуление reservation во внешнем auth](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/auth/user_api_key_auth.py#L3478-L3503) задают точную границу следующей проверки; это не доказательство невозможности адаптации.
5. [Cost tracking](https://docs.litellm.ai/docs/proxy/cost_tracking), [pinned Prisma schema](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/litellm/proxy/schema.prisma#L703), [основная лицензия](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/LICENSE), [Enterprise license](https://github.com/BerriAI/litellm/blob/d665dc1a6315847fcad6cc2c1264ceb47c06abce/enterprise/LICENSE.md). Собственная сборка не разрешает production-использование EE без соответствующих прав.
6. [Usage merge](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/response.py#L50-L143), [outlet reconstruction](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/middleware.py#L4177-L4202).
7. [Filter toggle](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/filter.py#L63-L105), [сохранённые status rows](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/src/lib/components/chat/Messages/ResponseMessage/StatusHistory.svelte#L7-L46).
8. [Header templates](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/utils/headers.py#L133-L165), [native CC/Responses route](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/routers/openai.py#L1433-L1589), [отдельный raw Responses](https://github.com/open-webui/open-webui/blob/6a18585ff4c2e5f6805f682222cfbc46dc669ef8/backend/open_webui/routers/openai.py#L1789-L1874).

Проверены несколько независимых community-примеров:

- [Open WebUI discussion #20915](https://github.com/open-webui/open-webui/discussions/20915): custom MCP Apps bridge — обсуждение/сторонняя реализация, а не готовая штатная возможность 0.12.2.
- [Discussion #20235](https://github.com/open-webui/open-webui/discussions/20235): HTML/prompt bridge не доказывает обратный авторизованный Tool RPC.
- [Issue #32852](https://github.com/open-webui/open-webui/issues/32852): передача темы в sandbox — отдельный пробел, не доказательство авторизации backend.
- [Token Usage & Cost Display, commit 9895be7](https://github.com/SmetDenis/openwebui-token-usage-display/blob/9895be72e2d6b0771e8435e7451cd565d83faebc/usage_display.py#L1868-L1937): полезен status/UserValves-паттерн; итог только активной ветки и оценка старых ходов по текущей модели не соответствуют этому GOAL.
- [Quota Keeper, commit 096e4e2](https://github.com/xyonium/owui-quota/blob/096e4e238e583f31d838da1b3ef2819a09b02541/README.md#L11-L44): собственный ledger и passthrough middleware противоречат выбранным ограничениям. Полностью не переносим.
- [LiteLLM #35524](https://github.com/BerriAI/litellm/issues/35524): закрыт как not planned, что не означает исправление отсутствующей оценки в этой версии; pinned source сохраняет ранний выход без reservation. [#36999](https://github.com/BerriAI/litellm/issues/36999): открытое сообщение о неизвестной цене, полезное для проверки отказа при неполных тарифах. [#34732](https://github.com/BerriAI/litellm/issues/34732): открытая проблема session-budget concurrency; её нельзя автоматически переносить на scalar user/key budgets.

## Рабочая копия и доставка

Ветка `agent/goal584-budget-ui`, base `94cd7d4b185bda4eccaf21b5740cae0da1027aa7`.
[Draft PR #585](https://github.com/Kwentin3/corp-openweb-ui/pull/585) сохраняет
коммерческую редакцию, эту запись и воспроизводимую проверку границы Rich UI.
Рабочая копия — соседняя `corp-openweb-ui-goal584`. В неё скопирована собственная
согласованная редакция коммерческого предложения; исходная рабочая копия и её
два изменённых документа сохранены. PR этой стадии не закрывает #584 и не
означает поставку бюджетов. Рабочая копия и ignored evidence нужны для продолжения
GOAL; удаление после интеграции и решения по сохранению доказательств.
