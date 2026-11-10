# Реестр патчей

Срез 10.11.2026. Подробно учтены LiteLLM-патчи GOAL584, подготовленные
и проверенные в исходном/стендовом объёме; ниже добавлен ограниченный перечень
существующих OpenWebUI 0.12.2 overlays по текущему source buildpath. Это не
подтверждение установленного production. Текущая приёмка — в [записи GOAL584](employee-budgets-goal584.md),
порядок установки и отката — в [инструкции](employee-budgets-installation.md).

Версии, base image digest, base revision, исходные/итоговые SHA256 и лицензии
принадлежат указанным ниже manifests. Здесь они повторно не ведутся.
Builder — [build_native_floor_image.py](../../scripts/goal584-budget-proof/build_native_floor_image.py),
проверка floor identity — [native_floor_identity.py](../../deploy/litellm-patches/positive-floor-v1.105.1/native_floor_identity.py).

| Патч / версия | Зачем нужен и граница | Upstream на дату среза | Квалификация и условие удаления |
|---|---|---|---|
| [positive-floor-v1.105.1](../../deploy/litellm-patches/positive-floor-v1.105.1/manifest.json), [floor.patch](../../deploy/litellm-patches/positive-floor-v1.105.1/floor.patch); LiteLLM 1.105.1 | Положительный cached DB floor может поднять уже обнулённый календарным reset live counter. Повторно читает DB перед таким повышением через существующий reseed lock; затронуты только `get_current_spend` и `_authoritative_floor_spend`. | Точная замена **UNCONFIRMED**. [PR #40940](https://github.com/BerriAI/litellm/pull/40940) открыт, не merged: invalidation key/user/team caches и retry Redis reset. Это связанный reset/cache defect, а не доказанная замена данного floor fix. | Сохранена ранее принятая независимая floor-проверка; идентичность — manifest и builder. Удалять после выбора точного stock release/image и воспроизведения completed-reset → next admission без восстановления старого floor, с сохранением обычного положительного floor и защиты manual reset. Патч явно не закрывает DB read, начатый до календарного reset, который не записал marker. |
| [stream-usage-v1.105.1](../../deploy/litellm-patches/stream-usage-v1.105.1/manifest.json), [raw-usage.patch](../../deploy/litellm-patches/stream-usage-v1.105.1/raw-usage.patch); LiteLLM 1.105.1 / OpenAI SDK 2.33.0 | Request-local признак исходной CC SSE Usage до SDK/stream normalization: отсутствующая/некорректная Usage отличается от полного явного нуля. Используется существующий SDK stream/constructor; денежный расчёт остаётся native. | Точная замена **UNCONFIRMED**. Открытый [issue #37992](https://github.com/BerriAI/litellm/issues/37992) описывает замену explicit zero локальной оценкой при disconnect. Он близок по симптомам, но не подтверждает сохранение raw evidence на SDK boundary. | SDK/component evidence actual42807487227 и native acceptance actual42825996133 перечислены в записи GOAL. Удалять после проверки конкретного stock image/SDK на raw omitted/null/invalid/explicit0/nonzero и нормальном/ошибочном/отменённом завершении; normalized zero или успешный API-вызов сами по себе недостаточны. |
| Тот же [stream manifest](../../deploy/litellm-patches/stream-usage-v1.105.1/manifest.json), [core-cancel.patch](../../deploy/litellm-patches/stream-usage-v1.105.1/core-cancel.patch); LiteLLM 1.105.1 | Передаёт отмену фактического CC generator в общий native cleanup; deferred post-call guardrail проверяется перед partial success, а при отсутствии success вызывается failure hook с тем же Logging evidence для CustomGuardrail. Targets и изменённые функции задаёт manifest. | [PR #33736](https://github.com/BerriAI/litellm/pull/33736) merged 17.07.2026: штатная partial-disconnect billing основа уже существует. Открытый [PR #49715](https://github.com/BerriAI/litellm/pull/49715) предлагает detached drain до полной provider Usage; это другое поведение. Точная замена всего нашего lifecycle delta **UNCONFIRMED**. | Actual42825996133: upstream HTTP200 → cancel до первого chunk/Usage → одна native failure row → reader unknown → адресная блокировка; повтор без второго dispatch. Удалять после той же наблюдаемой lifecycle-проверки на конкретном stock release, включая partial output и отсутствие дублированного учёта. |

`stream-usage-v1.105.1` — составной стендовый вариант поверх неизменённого floor
patch. Его manifest связывает floor manifest, четыре native targets и восемь SDK
files. Stock tag без этих проверок не равен принятому составному артефакту.
Deployment и платные provider calls этой записью не разрешаются.

## Что проверено upstream и пределы поиска

Использован GitHub plugin, только официальный `BerriAI/litellm`: семь адресных
поисков issues/PR (`budget reset stale spend`, `budget reset cache`,
`streaming usage missing`, `streaming disconnect partial spend`,
`"spend_db_floor"`, `streaming "usage" "zero" "missing"`,
`disconnect "guardrail"`), до пяти результатов на запрос; затем одно адресное
code lookup `_authoritative_floor_spend` и чтение ближайших issues/PR/source.
Это ограниченный поиск, не доказательство отсутствия другого upstream fix.

Issue #37992 прочитан со state `open`; PR #40940 и #49715 — `open`,
`merged=false`; PR #33736 — `merged=true`. Первый fetch #40940 вернул Internal
error, повтор успешно прочитал метаданные и diff. Дополнительно найденный
[PR #47721](https://github.com/BerriAI/litellm/pull/47721) остаётся unmerged и меняет
integration assertions, поэтому не считается заменой lifecycle patch.

Прочитаны текущие [OpenAI request owner](https://github.com/BerriAI/litellm/blob/main/litellm/llms/openai/openai.py)
и [common request processing](https://github.com/BerriAI/litellm/blob/main/litellm/proxy/common_request_processing.py):
blob SHA `f330d7fc6d4716e82b8de9c0e756683a735de77f` и
`9e2b49ef6928375c85faf9c086a412c0eee6e081`. Эти исходники отличаются от
проверенного 1.105.1: текущий OpenAI owner использует `post`/`raw_response.parse`,
а partial disconnect по-прежнему собирает response и вызывает success dispatch.
Более новый код требует своей квалификации; чтение `main` не доказывает поведение
выпущенного image. Отдельный SDK upstream fix и полный latest-release replay
не проверялись. Внешних issues/comments/PR не создано.

## Существующие OpenWebUI 0.12.2 overlays

Новых WebUI core patches в этом GOAL — **0**. В существующем stack их число
может быть ненулевым. Следующие три пакета имеют state **source-build known;
current runtime UNVERIFIED**: прочитаны текущие recipe/installer/verifier и
датированный [cutover record](openwebui-0122-cutover.md), но live container/image
и его исходники в этом исследовании не читались. Историческая приёмка 15/29 октября
не выдаётся за актуальную runtime-проверку 10 ноября.

Общий build owner — [runtime.Dockerfile](../../deploy/openwebui-upgrade-0122/runtime.Dockerfile)
и [make_runtime_context.py](../../deploy/openwebui-upgrade-0122/make_runtime_context.py):
tool-context → media backend → provider-context, затем проверенный полный
frontend build. Все три пакета привязаны к OpenWebUI 0.12.2, commit
`6a18585ff4c2e5f6805f682222cfbc46dc669ef8`; точные source hashes остаются
в существующих manifest/installer, отдельного списка хэшей здесь нет.

| Пакет / необходимость | Existing identity, installer/verifier и build path | Upstream / уже объявленное условие удаления |
|---|---|---|
| [Responses context](../../deploy/openwebui-patches/tool-context-v0.12.2/README.md): три backend files; reasoning/tool-result images, API field admission, длинные outgoing call/result IDs без изменения stored history. | [apply_context.py](../../deploy/openwebui-patches/tool-context-v0.12.2/apply_context.py), его `ORIGINAL`/`PATCHED`, [verify_context.py](../../deploy/openwebui-patches/tool-context-v0.12.2/verify_context.py); применяется общим runtime Dockerfile. Stateful Responses и compaction требуют сохранения принятых ограничений. | Существующие [issue #32473](https://github.com/open-webui/open-webui/issues/32473) и [discussion #32474](https://github.com/open-webui/open-webui/discussions/32474); их текущее состояние здесь не перепроверялось. Удалить изменения, когда выбранный upstream release проходит те же reconstruction и ordinary-chat continuation checks штатно. Старый history-ordering backport уже native и сюда не включается. |
| [Media upload](../../deploy/openwebui-patches/media-upload-v0.12.2/README.md): два backend и два frontend files; bounded upload, claimed processing handoff, authoritative prepared-file metadata. | [manifest.json](../../deploy/openwebui-patches/media-upload-v0.12.2/manifest.json), [apply_media.py](../../deploy/openwebui-patches/media-upload-v0.12.2/apply_media.py), [verify_installer.py](../../deploy/openwebui-patches/media-upload-v0.12.2/verify_installer.py), [verify_backend.py](../../deploy/openwebui-patches/media-upload-v0.12.2/verify_backend.py), [verify_frontend.mjs](../../deploy/openwebui-patches/media-upload-v0.12.2/verify_frontend.mjs); frontend — [frontend.Dockerfile](../../deploy/openwebui-patches/media-upload-v0.12.2/frontend.Dockerfile), backend/assets — общий runtime build. | [Существующий upstream workflow discussion](https://github.com/open-webui/open-webui/discussions/24239#discussioncomment-18949752), без заявления об upstream acceptance. Удалить соответствующие изменения после native same-ID preparation, waiting/failure, Send/STT и ordinary-document product checks. |
| [Provider context capture](../../deploy/openwebui-patches/provider-context-v0.12.2/README.md): default-off observer final serialized request; один router seam и существующие helper/control modules, без нового sender/tool loop. | [apply_capture.py](../../deploy/openwebui-patches/provider-context-v0.12.2/apply_capture.py), его `SUPPORTED`, [verify_capture.py](../../deploy/openwebui-patches/provider-context-v0.12.2/verify_capture.py); общий runtime build включает пакет после tool-context. [Отдельный recipe](../../deploy/openwebui-patches/provider-context-v0.12.2/runtime.Dockerfile) требует выбранного accepted base для сохранения остальных overlays. | Датированный cutover record описывает существующую поставку PR #579; текущая активация capture здесь **UNVERIFIED**. Удалить overlay, когда pinned upstream release даёт эквивалентный supported final-request debugging seam и проходит те же проверки. Отключение capture и удаление overlay — разные операции. |

У tool-context нет собственного `runtime.Dockerfile`; его installer/verifier
вызывает общий composition owner выше. `deploy/openwebui-patches/Dockerfile`
по умолчанию относится к 0.9.6 и не принимается за текущий 0.12.2 buildpath.
Исторические 0.11.4/0.9.6 overlays отдельно не инвентаризировались.
Полная installed-stack инвентаризация и latest-upstream qualification остаются
за пределами этого source slice; весь стек не объявляется patch-free.
