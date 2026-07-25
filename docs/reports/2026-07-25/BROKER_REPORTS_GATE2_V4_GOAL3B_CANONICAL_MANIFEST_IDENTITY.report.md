# Broker Reports — Gate 2 v4, Goal 3b: canonical manifest identity

Дата: 2026-07-25

Статус: `COMPLETED`

## Результат

Qualification input identity для frozen domain manifest больше не зависит
от CRLF/LF или JSON pretty formatting.

До исправления SHA-256 считался по working-tree bytes. Теперь:

1. JSON разбирается и валидируется;
2. сериализуется с sorted keys и compact separators;
3. SHA-256 считается по canonical UTF-8 bytes.

Exact canonical manifest SHA-256:
`edfba61488378154f7e6d37b6c532f2891a3339436d3fa107cce7ce3ba3678ca`.

Provider calls: `0`.

## Git

- execution revision:
  `4add5cdbacbade716d868f914b17ffccfcf0a8c3`;
- branch:
  `codex/broker-reports-gate2-v4-goal3b-canonical-manifest-identity`;
- PR: [#118](https://github.com/Kwentin3/corp-openweb-ui/pull/118).

## Contracts changed

Только qualification input identity calculation и его regression test.

Новая identity:

- input:
  `broker_reports_gate2_domain_qualification_manifest_v1:edfba61488378154f7e6d37b6c532f2891a3339436d3fa107cce7ce3ba3678ca`;
- canonical validator revision:
  `broker_reports_gate2_domain_qualification_comparator_v1:c52a2da4d26f667b5daa841b1fd219e211e387eb6b8194f1909e47d006cffaba`.

## Contracts explicitly unchanged

- manifest semantic content and five frozen cases;
- canonical comparison behavior;
- production parser/validator;
- prompt and output schema;
- provider profile/route;
- production request profiles/admissions;
- Gate 1 visual behavior;
- Registry/four-disposition contract;
- stage Functions/Pipes/Prompts;
- Knowledge/RAG/vectorization;
- Gate 3.

## Verification

- CRLF, LF, compact JSON and pretty JSON produce one exact hash;
- focused: `67 passed in 1.13s`;
- full: `1395 passed, 20 skipped, 5 existing warnings in 90.35s`;
- Ruff format/check: passed;
- both exact Gemini preflights: passed;
- published model inventory: `41`;
- preflight provider calls: `0`.

Authorization identity:

- Gemini 3.1:
  `da3c4ec9a890cd76f619a40a7c9cd201c37382c6d781c75378bca39c7911f762`;
- Gemini 3.5:
  `29a1f31c4c35f151ce8e336ee203747c994348247d7bbd24b0d850ba2d201e55`.

## Required terminal accounting

- provider calls: `0`;
- customer calls: `0`;
- input/output tokens: `0`;
- actual cost: `USD 0`;
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

Evidence-only Goal 3c from accepted `main`:

1. Gemini 3.1 bounded domain qualification;
2. Gemini 3.5 bounded domain qualification;
3. persisted safe receipts;
4. no runtime or canonical contract change.
