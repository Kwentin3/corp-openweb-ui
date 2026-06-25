# Stage 2 Test Data Requirements

Тестовые данные нужны до implementation planning. Без них acceptance будет проверять впечатления, а
не требования PRD-1.

## Synthetic data boundary

Для независимых proof/benchmark работ до получения customer samples использовать
[Synthetic Test Data Index](../testdata/SYNTHETIC_TEST_DATA_INDEX.md).

Synthetic data - это искусственные тестовые данные без данных заказчика. Они
подходят для проверки механики загрузки, prompts, Knowledge, простого
извлечения, Web Search safe matrix и analytics proof shape.

Synthetic data не закрывает production acceptance: реальные брокерские отчеты,
OCR/scans, XLSX, media, group matrix and provider/data policy examples остаются
customer test data package.

## Broker reports / 3-НДФЛ

- Простой отчет по брокерскому счету.
- Отчет с таблицами.
- PDF-отчет.
- XLSX-отчет, если реально используется.
- Сканированный или сложный PDF, если реально встречается.
- Пример хорошего результата из текущей схемы в Claude API / Claude models.
- Список полей, которые нельзя трактовать как налоговую консультацию.

## Transcription

- Короткий audio file.
- Короткий video file.
- Большой audio/video file.
- Большой WAV file для проверки browser ffmpeg preprocessing.
- Файл с плохим звуком, если такие встречаются.
- Owner/operator proof is accepted for ADR planning.
- Optional implementation smoke can record device, browser, file type, file
  size, duration, selected output profile, result and evidence.
- Optional smoke cases: desktop audio, desktop video, mobile audio, mobile
  video, large WAV, large video.
- Отдельно сохранить operator proof context: workflow accepted in two projects
  with same stack/architecture, including mobile and large-file cases.
- Подтвердить, какой output profile был выбран: например source-proven
  `mp3_high_compat`, `opus_webm_compact`, `opus_ogg_compact` или
  `wav_pcm_safe`.
- Зафиксировать Lemonfox adapter compatibility для выбранного output profile.
- Для Opus отдельно подтвердить, какой контейнер проходит: WebM/Opus или
  OGG/Opus.
- Подготовить отдельные короткие proof outputs для `audio/webm;codecs=opus` и
  `audio/ogg;codecs=opus`, потому что Lemonfox docs перечисляют форматы, но не
  доказывают конкретные Stage 2 ffmpeg profiles.
- Зафиксировать MP3 / `audio/mpeg` как compatibility fallback.
- Зафиксировать browser preprocessing input limit: 1 GB / 1024 MB.
- Зафиксировать Lemonfox direct prepared-audio upload limit: 100 MB.
- Зафиксировать Lemonfox public URL input limit: 1 GB, если этот путь вообще
  будет разрешен после storage access/expiry review.
- Подготовить кейс или synthetic metadata для prepared audio >100 MB, чтобы
  проверить warning + typed fail/fallback behavior без реальных sensitive
  media.
- Зафиксировать storage mode decision for prepared audio: `auto`, `s3` or
  `none`; for `s3` дополнительно bucket/prefix без секретов.
- Проверить storage health behavior: `auto` transient fallback, `s3` fail-fast,
  `none` no retention.
- Зафиксировать prepared audio retention days decision.
- Зафиксировать maximum duration cases: accepted internal limit, provider max
  duration proof or accepted Lemonfox `TBD`.
- Зафиксировать cancel behavior для preprocessing, upload and STT job where
  technically possible.
- Для Lemonfox отдельно зафиксировать provider-side cancel: proven supported,
  proven unsupported or `not documented / treated unsupported`.
- Ожидаемые шаблоны результата: протокол, задачи, решения, резюме, follow-up.
- Требования к языку, speaker labels и сроку хранения результата.

## Documents / OCR / Excel

- Простой текстовый PDF.
- Сканированный PDF.
- PDF с таблицами.
- PDF с печатями/подписями.
- DOCX.
- XLSX.
- Сложный XLSX, если есть: формулы, несколько листов, merged cells, сводные таблицы.
- Ожидаемые результаты для каждого файла.

## VL OCR pilot

- Скан брокерского отчета.
- Фото документа.
- PDF с печатями/подписями.
- PDF с таблицей.
- Плохой скан.
- Образец ожидаемого распознавания.
- Указать, можно ли использовать эти файлы с зарубежными provider.
- Указать, можно ли использовать эти файлы с российскими/cloud provider.
- Указать, требуется ли обезличивание перед OCR provider.
- Указать, какие файлы должны остаться только в local/self-hosted path.

## Web-search

- 5-10 типовых безопасных русскоязычных запросов, без персональных данных,
  клиентских данных, реквизитов, налоговых идентификаторов, внутренних URL и
  секретов.
- 3-5 безопасных англоязычных запросов.
- 3-5 forbidden sensitive examples:
  - запрос с паспортными/налоговыми/банковскими данными;
  - запрос с текстом клиентского документа;
  - запрос с internal/private URL;
  - запрос с token/API key/password;
  - запрос с payroll/customer-confidential data.
- 2 freshness-sensitive examples where current date/source recency matters.
- 2 conflicting-source examples where the answer must mention conflict.
- 2 no-sufficient-evidence examples where the expected answer is a visible
  insufficient-evidence/no-results state.
- Ожидаемый result count для первого smoke: `3`, если owner не утвердит другое.
- Ожидаемая search concurrency для первого smoke: `1`, если owner не утвердит
  другое.
- For the current Brave `brave_llm_context` baseline:
  - web loader bypass must be enabled;
  - web-search embedding/retrieval bypass must be enabled;
  - Code Interpreter must not be enabled by default for the selected Web Search
    smoke model.
- Требования к источникам/цитированию:
  - title;
  - URL;
  - snippet/excerpt;
  - provider;
  - searched_at or fetched_at when available.
- Expected behavior for quota/rate-limit, timeout, no-results and
  policy-blocked states.
- Confirmation that provider key is available only through approved server-side
  secret path and never in browser/test data.
- Confirmation whether native/provider-dashboard cost visibility is enough for
  pilot or hard budget enforcement is required first.
- For private SearXNG:
  - direct JSON API smoke query, for example `OpenWebUI`;
  - accepted upstream engine list for the pilot;
  - CAPTCHA/rate-limit/empty-results evidence;
  - confirmation that public SearXNG instances are not used;
  - confirmation that SearXNG is internal-only or debug-local-only;
  - confirmation that upstream query leakage is accepted by owner.
- Brave / Yandex / SearXNG comparison matrix:
  - same RU ordinary queries for all allowed paths;
  - same EN ordinary queries for all allowed paths;
  - same freshness-sensitive queries for all allowed paths;
  - same conflicting-source queries for all allowed paths;
  - same no-sufficient-evidence queries for all allowed paths;
  - candidate set capture for each provider/path;
  - final answer capture for each provider/path;
  - source visibility and loaded-evidence notes;
  - search latency, page load/extraction latency and total answer latency;
  - log check for raw query/result/provider key exposure.

## Groups / roles / manager visibility

- Список групп: админы, РО, менеджеры ОС / ОП / КО / БО, специалисты / бухгалтеры ОВ / ИТС / АУП /
  БО / ТО.
- Кто владелец каждого workspace.
- Какие рабочие чаты может видеть руководитель.
- Какие чаты считаются личными/черновыми.
- Должен ли сотрудник видеть правило просмотра.
- Нужно ли логировать просмотр.

## Provider and cost testing

- Какие keys/access может предоставить оператор для research.
- Какие providers production-required, pilot, research-only.
- Пример expected monthly usage для LLM, web-search, STT.
- Ограничения по зарубежным/российским providers.
- Allowed/prohibited examples by provider class: foreign, Russian, local/self-hosted, future
  masked/tokenized.
- Confirmation that provider setup may start only after data policy approval.

## Security policy examples

- Примеры разрешенных данных.
- Примеры запрещенных данных.
- Примеры данных, разрешенных только для отечественного provider.
- Примеры, которые требуют ручного обезличивания.
