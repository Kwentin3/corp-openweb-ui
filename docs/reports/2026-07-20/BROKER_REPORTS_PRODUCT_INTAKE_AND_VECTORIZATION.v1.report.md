# Broker Reports — product intake и риск vectorization

Дата: 2026-07-20

Итог: `GUARD_GAP_IDENTIFIED` — P0 correctness/security.

## Полный пользовательский путь

1. Общий OpenWebUI uploader отправляет документ на `POST /api/v1/files/`.
2. Browser loader перехватывает `window.fetch`, распознаёт media и Broker Reports
   documents.
3. Только для `sttUploadFile` запрос переписывается функцией `withProcessFalse`.
   Для `brokerGate1UploadFile` rewrite отсутствует.
4. После upload loader запоминает Broker document и показывает attachment/composer
   action `Gate 1`.
5. Action отправляет уже существующие file refs на
   `/api/chat/actions/broker_reports_gate1_normalizer_action`.
6. Backend pipe получает refs и читает file content, но не владеет upload endpoint,
   не проверяет native-processing state и не может отменить processing, уже
   стартовавший до action.

Следовательно, путь не является структурно неспособным войти в native processing.
UI обычно может отправить `process=false` только после будущей правки, но это всё
равно не server-authoritative proof: другой клиент, XHR, reload, прежний upload или
прямой API-вызов обходят browser monkey patch.

## Прямые доказательства

- `deploy/openwebui-static/loader.js:419-425`: Broker file распознаётся, но
  `withProcessFalse` вызывается только внутри `if (sttUploadFile)`.
- `deploy/openwebui-static/loader.js:428-439`: upload уже выполнен через original
  fetch, после чего Broker file лишь добавляется в local state.
- `deploy/openwebui-static/loader.js:687-695`: reload/list route снова принимает
  все совместимые ранее загруженные документы независимо от способа processing.
- `deploy/openwebui-static/loader.js:1566-1591`: Broker action получает file refs,
  а не source bytes через feature-owned upload contract.
- `broker_reports_gate1_pipe.py:193-205`: pipe собирает refs и начинает
  normalization; pre-processing invariant отсутствует.
- Live `/static/loader.js` вернул HTTP 200 и SHA-256
  `28c5eadf…703b2`, точно равный repository loader. Gap реально развернут, а не
  является локальным drift.
- Прежний accepted smoke с явным `process=false` дал нулевые Knowledge/vector
  deltas; это доказывает безопасность только этого диагностического маршрута.
  Native default route ранее создавал vector state до cleanup, поэтому риск не
  теоретический.

## Узкая необходимая коррекция

Следующий implementation GOAL должен создать server-authoritative Broker Reports
upload endpoint или эквивалентный backend contract:

- endpoint всегда принудительно создаёт private upload с `process=false`;
- client не может переопределить flag;
- response содержит typed intake receipt с feature ownership;
- Broker action принимает только такие receipts;
- действие отклоняет ref, если native processing state/artifacts уже существуют;
- post-upload invariant проверяет отсутствие Knowledge, RAG documents, vector
  collections, embeddings и native document-processing artifacts;
- cleanup остаётся defence in depth, но не основным safety control;
- старый generic uploader не должен создавать Broker action eligibility.

Локальная правка `if (sttUploadFile || brokerGate1UploadFile)` полезна как
немедленное сокращение риска, но не закрывает P0 и не должна быть acceptance proof.

## UI integrity audit

Status: `FAIL`.

Violations:

- safety-critical upload semantics зависят от browser monkey patch;
- action появляется для файлов из generic list после reload;
- UI не показывает, был ли source принят как private/no-processing;
- backend action не отделяет eligible receipt от произвольного file ref.

Required fixes:

- feature-owned server route и typed receipt;
- fail-closed action eligibility;
- видимый terminal intake status: accepted-private или rejected-native-processed;
- retry должен быть идемпотентным по receipt и не повторять generic upload.

Evidence:

- state coverage: ready/running/completed/error есть у action, но intake safety
  state отсутствует;
- accessibility: button focus/label существуют, дефект не визуальный;
- feedback: normalization status не сообщает processing mode upload;
- action hierarchy: Gate 1 action ошибочно доступен после generic upload/list;
- separation: safety policy находится в UI interception вместо server contract.

Escalation: P0 владельцу product intake/backend; не включать native-upload Broker
Reports path в безопасный product claim до server-side proof.
