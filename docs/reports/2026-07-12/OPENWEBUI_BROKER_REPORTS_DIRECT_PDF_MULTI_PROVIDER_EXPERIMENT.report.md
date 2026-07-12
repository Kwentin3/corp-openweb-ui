# OpenWebUI Broker Reports: direct whole-PDF multi-provider experiment

Дата: 2026-07-12

Режим: research/controlled experiment. Production PDF pipeline, OpenWebUI core, Gate 2 validators, Knowledge/RAG/vector и live bundles не менялись.

## 1. Исполнительный вердикт

Direct whole-PDF analysis **не заменяет** текущий normalization/table reconstruction layer.

- Ни OpenAI, ни Gemini, ни Claude не вернули один валидный structured result со всеми таблицами шестистраничного PDF.
- Ни один провайдер не доказал независимое обнаружение всех 14 reference table identities.
- OpenAI оказался сильнейшим в отдельном business arm: strict result прошёл локальную схему, 386/393 полей и 234/234 numeric fields точно найдены на заявленной странице.
- Но ни один direct result не получил Level 4 source-value binding. Все direct business facts отклонены как authoritative facts.
- Gemini и Claude стабильно исчерпали monolithic table output budget. OpenAI завершал ответы, но нарушал межполевые row/column invariants и обнаруживал только 12, 10 и 11 из 14 page/order identities.
- Controlled gridless fixture доказал базовую direct-PDF способность: Gemini и Claude дали 12/12 exact cells; OpenAI при финальном `temperature=0` нарушил `row_count` contract.

Рекомендуемая роль direct PDF:

```text
business recall auditor / challenge path / human-review assistant

not:
authoritative table reconstruction
not:
authoritative source-fact extraction
```

## 2. Контрольный источник и fairness

| Параметр | Значение |
|---|---|
| PDF | тот же approved six-page broker PDF |
| SHA-256 | `79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d` |
| Bytes | 176 458 |
| Pages | 6/6 |
| MIME | `application/pdf` |
| Experiment version | `broker_reports_direct_pdf_multi_provider_experiment_v1` |
| Table repeats | 3 на провайдера |
| Business calls | 1 на провайдера |
| Gridless calls | 1 на провайдера |
| Common output budget | 32 768 requested tokens |

Для всех canonical jobs доказано:

- identical original PDF bytes;
- no page removal;
- no crop;
- no raster preprocessing;
- no locally extracted text in prompt;
- no 22 MB normalized payload;
- no table projections or source-value candidates;
- no file search, Knowledge, RAG or vector search;
- no hidden retry/failover;
- provider-neutral prompts and canonical semantics.

OpenAI и Gemini использовали `temperature=0`. `claude-sonnet-5` отвергает `temperature` как deprecated, поэтому Claude использовал ближайший доступный provider-default sampling; это явно записано в safe metadata.

## 3. Provider/model/transport qualification

Ключи не дублировались в research config. Harness после admin sign-in прочитал существующие OpenWebUI Connections из `/openai/config` и держал API keys только в памяти.

| Provider | Exact live model | Native transport | Model-list qualification | Strict syntax |
|---|---|---|---|---|
| OpenAI | `gpt-5.4-mini-2026-03-17` | `/v1/responses`, inline `input_file` PDF | HTTP 200; model present | `text.format` JSON Schema, strict |
| Google | `models/gemini-3.5-flash` | native `generateContent`, `inline_data` `application/pdf` | HTTP 200; model present | `responseMimeType=application/json` + `responseJsonSchema` |
| Anthropic | `claude-sonnet-5` | native `/v1/messages`, base64 `document` PDF | HTTP 200; model present | `output_config.format` JSON Schema |

Capability basis:

- OpenAI documents direct PDF/file input through Responses input files: <https://platform.openai.com/docs/quickstart> and <https://platform.openai.com/docs/api-reference/responses>.
- Gemini documents inline native PDF understanding and structured output: <https://ai.google.dev/gemini-api/docs/document-processing> and <https://ai.google.dev/gemini-api/docs/generate-content/structured-output>.
- Anthropic documents native PDF document blocks and structured outputs: <https://docs.anthropic.com/en/docs/build-with-claude/pdf-support> and <https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs>.

### 3.1 Provider-specific projection

Canonical semantics remained identical. Anthropic schema syntax removed eight vendor-unsupported validation keywords such as `minimum`/`maxItems`; required fields, enums, object closure and the local canonical validator remained unchanged.

The harness stores both canonical and adapted schema hashes plus transform count.

## 4. Reference status

```text
table reference:
agent_visual_reviewed_pending_human_signoff

business reference:
not_human_reviewed

authoritative accuracy claims:
not allowed
```

Table comparison below is a provisional diagnostic against the existing independent PyMuPDF/visual draft. It is not human-signed ground truth.

Business precision/recall cannot be claimed. The available independent check is narrower: exact re-location of every returned field on the provider-claimed PDF page, without fuzzy matching.

## 5. Experiment 1 — direct table reconstruction

### 5.1 Terminal results

| Provider | Repeat | Strict/local result | Raw table objects | Reference page/order identities matched | Terminal class | Output tokens | Time |
|---|---:|---|---:|---:|---|---:|---:|
| OpenAI | 1 | failed: `column_count_mismatch` | 12 | 12/14 | completed response, invalid cross-field contract | 11 839 | 56,206 s |
| OpenAI | 2 | failed: `row_count_mismatch` | 10 | 10/14 | completed response, invalid cross-field contract | 12 264 | 55,190 s |
| OpenAI | 3 | failed: `row_count_mismatch` | 11 | 11/14 | completed response, invalid cross-field contract | 12 280 | 57,712 s |
| Gemini | 1 | failed: incomplete JSON | 0 accepted | 0/14 | `MAX_TOKENS` | 15 794 | 133,548 s |
| Gemini | 2 | failed: incomplete JSON | 0 accepted | 0/14 | `MAX_TOKENS` | 15 794 | 133,326 s |
| Gemini | 3 | failed: incomplete JSON | 0 accepted | 0/14 | `MAX_TOKENS` | 12 064 | 129,610 s |
| Claude | 1 | failed: no complete structured block | 0 accepted | 0/14 | `max_tokens` | 32 768 | 267,411 s |
| Claude | 2 | failed: no complete structured block | 0 accepted | 0/14 | `max_tokens` | 32 768 | 254,323 s |
| Claude | 3 | failed: no complete structured block | 0 accepted | 0/14 | `max_tokens` | 32 768 | 261,606 s |

No provider independently discovered all 14 tables in an accepted result.

OpenAI raw diagnostics are not accuracy results: provider-side strict schema can constrain types but cannot express or guarantee `row_count == len(rows)` and `column_count == len(each row cells)`. Local validation correctly rejected all three responses.

Gemini and Claude demonstrate a different failure: full-document cell reconstruction is too verbose for one monolithic result. Both providers repeatably reached their effective output limits.

### 5.2 Repeatability

- OpenAI raw detected identities varied 12 → 10 → 11; validation class varied column/row mismatch.
- Gemini repeated `MAX_TOKENS` and invalid JSON in 3/3; response hashes differed.
- Claude repeated `max_tokens` and missing complete structured block in 3/3; response hashes differed.
- No provider produced one accepted table result, so value-level repeatability cannot be established.

### 5.3 Gridless controlled fixture

The controlled synthetic PDF contains one 4×3 aligned-text table and no vector rules/drawings.

| Provider | Result | Structure | Cells | Numeric cells | Header |
|---|---|---:|---:|---:|---:|
| OpenAI, temperature 0 | failed: `row_count_mismatch` | 0/1 accepted | 0/12 accepted | 0/6 accepted | 0/1 |
| Gemini | passed | 1/1 | 12/12 | 6/6 | 1/1 |
| Claude | passed | 1/1 | 12/12 | 6/6 | 1/1 |

This proves baseline gridless capability for Gemini/Claude on a synthetic fixture only. It does not replace the missing approved human corpus case.

## 6. Experiment 2 — direct business extraction

### 6.1 Structured result and exact relocation

| Provider | Strict/local result | Typed facts | Fields exactly found on claimed page | Numeric fields exactly found | Claimed provenance | Uniform verified provenance | Authoritative acceptance |
|---|---|---:|---:|---:|---:|---:|---|
| OpenAI | passed | 55 | 386/393 = 98,22% | 234/234 = 100% | Level 3 claimed | Level 0 uniform | rejected |
| Gemini | passed | 13 | 51/63 = 80,95% | 20/32 = 62,50% | Level 3 claimed | Level 0 uniform | rejected |
| Claude | failed: `max_tokens`, incomplete JSON | 0 accepted | 0 | 0 | 0 | 0 | rejected |

OpenAI is the strongest business extractor in this run. This is not human-reviewed recall/precision:

- 55 versus 13 facts can mean better recall, over-segmentation, duplication or false positives;
- seven OpenAI fields and twelve Gemini fields were not exactly found on the claimed page;
- exact substring re-location used no fuzzy matching, so some misses may be formatting differences, but they remain unverified;
- all values remain free-form provider output without Level 4 source refs.

### 6.2 Domain coverage

OpenAI and Gemini returned all eight required domain envelopes. Claude did not return a complete parseable business result.

No tax calculation, declaration, Gate 3 consolidation or XLSX work was requested or accepted.

## 7. Provenance assessment

| Level | Direct PDF result |
|---|---|
| 1 — document hash/page | available in harness; page claims present in valid OpenAI/Gemini results |
| 2 — page/table/row/column identity | partially claimed; not complete for every fact |
| 3 — bbox/provider citation | claimed by schema fields, but not native independently verified citations for all values |
| 4 — exact independent PDF word/cell source ref | absent for every direct provider |

OpenAI: 55/55 facts claimed a page, 44/55 claimed table identity, 0/55 supplied bbox, 55/55 supplied a citation string. Gemini: 13/13 page, 12/13 table, 13/13 bbox and citation string.

These are provider claims, not proof. The exact-page re-location check found:

- OpenAI: 386/393 fields, 234/234 numeric fields;
- Gemini: 51/63 fields, 20/32 numeric fields.

Therefore a model can cite a location that does not contain an exact returned value. Page citation is insufficient for authoritative financial facts.

## 8. Operational comparison

Canonical jobs only; discarded preflight attempts are listed separately.

| Provider | Jobs | Passed structured jobs | Input tokens | Output tokens | Total time | Max response |
|---|---:|---:|---:|---:|---:|---:|
| OpenAI | 5 | 1 | 61 156 | 48 188 | 224,133 s | 78 737 B |
| Gemini | 5 | 2 | 13 904 | 48 385 | 446,057 s | 97 354 B |
| Claude | 5 | 1 | 95 993 | 131 308 | 1 080,306 s | 110 710 B |

Evidence storage:

- private raw/checkpoint JSON: 4 020 464 B; gzip 2 633 917 B;
- safe runs JSON: 30 827 B; gzip 4 364 B;
- raw PDF/model outputs remain ignored private local evidence;
- report contains no raw customer values.

### 8.1 Discarded qualification/preflight attempts

Preserved privately and excluded from canonical comparison:

1. Anthropic schema preflight: vendor rejected `minimum`; 5 HTTP 400 attempts, no inference tokens.
2. Anthropic sampling preflight: vendor rejected deprecated `temperature`; 5 HTTP 400 attempts, no inference tokens.
3. Initial OpenAI provider-default run: discarded because a live probe proved `temperature=0` is supported; canonical five jobs were rerun at zero.
4. One small OpenAI temperature capability probe: HTTP 200; excluded from arm metrics.

No failed attempt was silently overwritten; each preflight journal is archived under ignored private evidence.

## 9. Comparison with existing arms

Existing nine-table draft metrics:

| Arm | Accepted complete output | Cell accuracy | Numeric accuracy | Exact structures | Provenance |
|---|---|---:|---:|---:|---|
| A deterministic, all selected | yes/blocked split | 38,75% | 19,69% | 4/9 | Level 4-capable source refs |
| B raster-only | yes | 98,80% | 99,08% | 9/9 | crop/table only |
| C hybrid 150 DPI primary | yes | 83,75% | 77,85% | 8/9 | Level 4 candidate-bound |
| C hybrid adaptive 200 DPI | yes | 99,04% | 99,08% | 9/9 | Level 4 candidate-bound |
| D/E/F direct whole PDF | no provider produced accepted table result | not scoreable | not scoreable | 0 accepted complete results | no Level 4 |

Direct whole-PDF table reconstruction did not outperform raster-only or hybrid. It did not produce a scoreable complete table artifact.

Business extraction is a different question. OpenAI produced a strong recall-auditor candidate, but no human business ground truth exists and no direct result satisfies authoritative provenance.

## 10. Required conclusions

1. Does any provider independently discover all 14 tables? **No accepted result.**
2. Does direct PDF outperform raster/hybrid table extraction? **No.**
3. Is direct PDF stable across repeats? **Failure class is repeatable for Gemini/Claude; OpenAI table content/counts are not stable.**
4. Can it preserve exact numeric cells? **Not proven for the complete table arm.** Gridless Gemini/Claude: 6/6 synthetic numeric cells.
5. Can it provide sufficient cell-level provenance? **No Level 4 binding.**
6. Can it return one valid structured result for the complete document? **Business: OpenAI/Gemini yes. Tables: all providers no.**
7. Does monolithic PDF lose small facts/tables? **Yes for table identities/output completeness; business recall remains unmeasured without human reference.**
8. Strongest provider:
   - table reconstruction: none accepted; OpenAI got furthest structurally;
   - business extraction: OpenAI provisional;
   - provenance: none authoritative; OpenAI strongest exact numeric page relocation;
   - structured reliability: OpenAI/Gemini completed business, Gemini/Claude completed gridless.
9. Can direct PDF replace deterministic/hybrid? **No. It is an audit/fallback/human-review path.**

## 11. Recommended target role

Keep:

- deterministic/hybrid reconstruction for authoritative table/source evidence;
- current Gate 2 validators and exact source-value refs;
- compact canonical artifacts and explicit blockers.

Add later only after approval:

- direct-PDF business recall auditor comparing proposed facts against authoritative source-bound facts;
- direct-PDF table-count/challenge signal, never direct authoritative materialization;
- human-review UI for disagreements and unmatched claimed values.

Do not add:

- monolithic direct-PDF primary extractor;
- prompt-only JSON downgrade;
- free-form direct values into authoritative facts;
- provider-specific weakened semantics;
- production rollout from this experiment.

## 12. Final statuses

Proven as terminal research arms, including recorded failures:

- `BROKER_REPORTS_DIRECT_PDF_OPENAI_ARM_COMPLETED`
- `BROKER_REPORTS_DIRECT_PDF_GEMINI_ARM_COMPLETED`
- `BROKER_REPORTS_DIRECT_PDF_CLAUDE_ARM_COMPLETED`
- `BROKER_REPORTS_DIRECT_PDF_TABLE_RECONSTRUCTION_COMPARED`
- `BROKER_REPORTS_DIRECT_PDF_PROVENANCE_ASSESSED`
- `BROKER_REPORTS_DIRECT_PDF_REPEATABILITY_ASSESSED`
- `BROKER_REPORTS_DIRECT_PDF_TARGET_ROLE_RECOMMENDATION_READY`

Not proven:

- `BROKER_REPORTS_DIRECT_PDF_BUSINESS_EXTRACTION_COMPARED` — no human-reviewed business reference, and Claude returned no complete result;
- `BROKER_REPORTS_DIRECT_PDF_MULTI_PROVIDER_EXPERIMENT_READY` — authoritative reference/sign-off and corpus acceptance are absent.

Terminal verdict:

```text
DIRECT WHOLE-PDF TABLE PRIMARY:
REJECTED

DIRECT WHOLE-PDF BUSINESS AUDITOR:
PROMISING, OPENAI STRONGEST, NOT AUTHORITATIVE

NORMALIZATION / TABLE RECONSTRUCTION LAYER:
STILL REQUIRED
```
