# Stage 2 Test Data Requirements

Тестовые данные нужны до implementation planning. Без них acceptance будет проверять впечатления, а
не требования PRD-1.

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
- Для lightweight ffmpeg proof matrix по каждому файлу: device, browser, file
  type, file size, duration, selected output profile, result,
  evidence link/screenshot/log.
- Минимальные proof cases: desktop audio, desktop video, mobile audio, mobile
  video, large WAV, large video.
- Отдельно зафиксировать operator manual proof cases: mobile large video и
  mobile large WAV, даже если точные размеры пока `TBD`.
- Подтвердить, какой output profile был выбран: например source-proven
  `mp3_high_compat`, `opus_webm_compact`, `opus_ogg_compact` или
  `wav_pcm_safe`.
- Зафиксировать Lemonfox adapter compatibility для выбранного output profile.
- Для Opus отдельно подтвердить, какой контейнер проходит: WebM/Opus или
  OGG/Opus.
- Зафиксировать MP3 / `audio/mpeg` как compatibility fallback.
- Зафиксировать browser preprocessing input limit: 1 GB / 1024 MB.
- Зафиксировать Lemonfox direct prepared-audio upload limit: 100 MB.
- Подготовить кейс или synthetic metadata для prepared audio >100 MB, чтобы
  проверить typed fail/fallback behavior без реальных sensitive media.
- Зафиксировать S3/object storage bucket/prefix decision for prepared audio
  без секретов.
- Зафиксировать prepared audio retention days decision.
- Зафиксировать cancel behavior для preprocessing, upload and STT job where
  technically possible.
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

- 5-10 типовых русскоязычных запросов.
- 3-5 англоязычных запросов.
- Примеры задач, где web-search запрещен из-за чувствительных данных.
- Ожидаемый result count.
- Требования к источникам/цитированию.

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
