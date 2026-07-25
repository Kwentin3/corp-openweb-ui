# Broker Reports — Gate 2 v4, Goal 3a: persisted domain receipts

Дата: 2026-07-25

Статус: `COMPLETED`

## Результат

Исправлен локальный evidence-capture defect Goal 3:

- live execution запрещён без explicit `--receipt-path`;
- receipt path обязан оканчиваться на `.safe.json`;
- safe checkpoint атомарно записывается до первого provider call;
- следующий checkpoint записывается после каждого case;
- запись использует UTF-8 без BOM, `flush`, `fsync` и atomic replace;
- terminal stdout сокращён до безопасного summary и SHA-256 receipt;
- raw provider output не записывается.

Live provider calls в этом PR: `0`.

## Git

- execution revision:
  `ba5fedbc505e11290bbdc09a6d5958d21bc8b122`;
- branch:
  `codex/broker-reports-gate2-v4-goal3a-domain-receipt-persistence`;
- PR: [#117](https://github.com/Kwentin3/corp-openweb-ui/pull/117).

## Contracts changed

Только qualification-only runner:

- `scripts/live_gate2_domain_economy_qualification.py`;
- focused tests для pre-call и per-case checkpoint sequence.

Изменение не включает production route и не активирует модель.

## Contracts explicitly unchanged

- canonical production parser/validator;
- domain package/finalization contracts;
- frozen manifest content;
- provider profile and route;
- prompt and provider schema projection;
- production request profiles and admissions;
- Registry и four-disposition contract;
- Gate 1 visual behavior;
- stage Functions/Pipes/Prompts;
- Knowledge/RAG/vectorization;
- Gate 3.

## Verification

Focused:

- `66 passed in 1.12s`.

Full service suite:

- `1394 passed`;
- `20 skipped`;
- `5` existing SWIG warnings;
- `93.14s`.

Дополнительно:

- Ruff format/check: passed;
- live CLI without `--receipt-path`: exit `2` before authentication/provider
  access;
- atomic checkpoint sequence in test:
  provider call counters `0, 1, 2, 3, 4, 5`;
- final persisted receipt equals terminal result;
- temporary file residue: `0`;
- safe JSON BOM: absent.

## Preflight and discovered boundary

Обе exact Gemini-модели прошли provider/schema preflight:

- published inventory total: `41`;
- provider calls: `0`;
- estimated input tokens per model: `16665`;
- Gemini 3.1 maximum estimate: `USD 0.034886250`;
- Gemini 3.5 maximum estimate: `USD 0.056199500`.

Preflight выявил отдельный identity defect: manifest SHA-256 вычисляется по
raw bytes. На Windows checkout перевод LF в CRLF, поэтому неизменённый JSON
получил новую identity:

- ранее: `ee6a8ac0...`;
- текущий working tree: `6b8aa060...`.

Live qualification под нестабильной identity не запускалась.

## Required terminal accounting

- provider calls: `0`;
- customer calls: `0`;
- model IDs:
  `models/gemini-3.1-flash-lite`,
  `models/gemini-3.5-flash-lite` (preflight only);
- tokens: `0`;
- cost: `USD 0`;
- fallback calls: `0`;
- repair attempts: `0`;
- expensive model calls: `0`;
- stage mutations: `0`.

## Privacy

`PASSED`.

- customer corpus read: `false`;
- raw provider output in Git: `false`;
- secrets in report/receipt: `false`.

## Next permitted goal

Только отдельный corrective Goal 3b:
canonical JSON manifest identity independent of CRLF/LF, with regression
test and zero provider calls.

После его merge разрешён новый evidence-only domain requalification PR.
