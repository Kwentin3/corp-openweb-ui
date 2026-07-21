# OpenWebUI Broker Reports: direct PDF plain text vs hybrid experiment

Дата: 2026-07-13

Режим: research / controlled experiment only.

Статус evidence: `completed_with_failures`; 45/45 canonical jobs имеют terminal outcome.

## 1. Исполнительный вердикт

Гипотеза подтвердилась **частично**.

- Все три модели понимают общий смысл и структуру шестистраничного PDF достаточно хорошо для summary/challenge/human-review роли.
- Gemini независимо нашёл 14/14 reference table identities без false tables. Claude также вернул 14 полных inventory-блоков, но весь artifact отклонён из-за лишней строки о странице без таблиц. OpenAI нашёл все 14, но пере-сегментировал документ до 29 tables, то есть добавил 15 false identities.
- Удаление JSON Schema **не позволило ни одному провайдеру завершить валидную monolithic table transcription**.
- Gemini и Claude по-прежнему исчерпали 32 768-token output budget. OpenAI завершил ответ без token limit, но line-oriented artifact сломался на неодинаковой ширине строк после двух полных таблиц.
- Targeted whole-PDF transcription действительно снял часть output-size проблемы. У Gemini приняты 6/9 основных таблиц; на этом принятом подмножестве результат составил 396/402 = 98,51% exact cells и 156/159 = 98,11% numeric-like cells. Но с обязательным failure penalty по всем девяти cases это только 56,80% и 48,00% соответственно.
- Adaptive hybrid остаётся существенно сильнее: 823/831 = 99,04% cells, 322/325 = 99,08% numeric-like, 9/9 structures, 9/9 headers и complete candidate-bound Level 4 provenance.

Итоговая причина предыдущего direct-PDF провала — не одна JSON Schema. Доказана комбинация:

1. monolithic output volume;
2. provider reasoning/output budget;
3. table-grid reconstruction;
4. точное соблюдение line-oriented serialization;
5. отсутствие исходной source-value binding.

Строгая JSON Schema добавляла сложность и cross-field failure surface, но не была главным единственным bottleneck.

## 2. Контролируемый источник и fairness

| Параметр | Значение |
|---|---|
| PDF | тот же approved six-page broker PDF |
| SHA-256 | `79af73d5be78df446f768f516ed6eaebd5a9d4bfc6f98c98a4a53a5b5131f37d` |
| Bytes | 176 458 |
| Pages | 6/6 |
| MIME | `application/pdf` |
| Experiment version | `broker_reports_direct_pdf_plain_text_experiment_v1` |
| Canonical jobs | 15 на provider, 45 total |
| Native HTTP outcomes | 45/45 HTTP 200 |

Для каждого canonical inference доказано:

- identical original PDF bytes;
- no page removal and no crop;
- no locally extracted text in request;
- no normalized geometry or table projection in request;
- no source-value candidates in request;
- no Knowledge/RAG/vector/file-search path;
- no hidden provider failover;
- no silent retry;
- exact prompt hash, response id, usage, duration, finish reason and raw private response retained.

Production PDF pipeline, Gate 2 validators, OpenWebUI core и live bundles не менялись.

## 3. Reference status

Использован тот же девятитабличный draft:

```text
agent_visual_reviewed_pending_human_signoff
```

Actual human sign-off в репозитории и private evidence отсутствует. Поэтому:

- exact cell/numeric/header metrics ниже — provisional diagnostic;
- они сопоставимы с hybrid только потому, что используют те же 831 cell positions, NFKC, whitespace collapse и тот же numeric-like classifier;
- authoritative accuracy и production acceptance не заявляются;
- full-table PyMuPDF shapes используются только как supplementary structure diagnostic.

## 4. Provider/model/transport matrix

| Provider | Exact live model | Native transport | Qualification | Determinism |
|---|---|---|---|---|
| OpenAI | `gpt-5.4-mini-2026-03-17` | `/v1/responses`, inline `input_file` PDF | model-list HTTP 200, model present | `temperature=0` |
| Google | `models/gemini-3.5-flash` | native `generateContent`, inline PDF | model-list HTTP 200, model present | `temperature=0` |
| Anthropic | `claude-sonnet-5` | native `/v1/messages`, base64 document PDF | model-list HTTP 200, model present | provider default; model rejects deprecated temperature |

No `responseJsonSchema`, `text.format`, `output_config.format` или другой structured-output schema использовалась.

## 5. Prompt contracts and hashes

ARM 1–3 prompt pack: `broker_reports_direct_pdf_plain_text_prompts_v1`.

| Arm | Prompt SHA-256 | Max output tokens |
|---|---|---:|
| Explanation | `a1cec339cc107d31f48a1fafdb2932376f17d79fb517d4497493393d26ccbd94` | 8 192 |
| Inventory | `2bc532b67cafa9a073614ab1bf5af2f540297b5ffb2e1916d6672843fd9583f5` | 8 192 |
| Monolithic transcription | `959828d521f54b5d72b2739ac56704e7246bb4728abe3348759ef462436dfa77` | 32 768 |

ARM 4 prompt pack: `broker_reports_direct_pdf_plain_text_target_identity_fix_v2`.

| Table key | Prompt SHA-256 |
|---|---|
| `1:1` | `bd0b2432d2e6f700ee5d37bb74dc074cb2fa0ceb3bfc383d8763ed919c137b94` |
| `1:2` | `aa7e44c37b25e472d9ace189dc97c78eb33bf5b817b0a3feb3f1ad63d0a0a05f` |
| `1:3` | `f161b18019ce3503a2b843ca5d3cac166b0b63149f19cd35fbefc104bac21690` |
| `2:2` | `bfa4c0fe38fdd55cae767da16c45e981cf2aaa0aa7e1f424516c1a58ffef2830` |
| `3:2` | `2cc857a261a880764c5577f2f31cefdf76f200338043737011c990c6392d388f` |
| `4:1` | `691c25ab22361f6430f66eba6dbf62c7a5130338c46ad00c1c3ca4d032c32ba7` |
| `4:2` | `af46641520facec6ea50458762cc48225f9aa781a8b46a74000d708b8f00f550` |
| `5:3` | `0aeaa69802dc10505c3fde53d1c280f36014539ff0c1bd5ad025832a7585ea03` |
| `5:4` | `ab558964b7031190f24793e07f7c38ac222d5864527ee0d8b5aeea507d4459fd` |

Target prompts запрашивали только page + page-local table order. Reference shapes, expected counts, cells, crops и parser output модели не раскрывались.

### 5.1 Preserved excluded preflight

В первой targeted template scope называл правильный target, но format example ошибочно оставался `TABLE page=1 order=1`. Это противоречие было обнаружено во время выполнения.

- 24 уже завершившихся attempts сохранены как `journal.pre_target_header_fix.private.json`;
- они исключены из canonical metrics;
- raw responses не удалены и не перезаписаны;
- ARM 1–3 не повторялись;
- canonical ARM 4 выполнен с target-specific example header;
- это явный protocol correction, не silent retry.

## 6. Deterministic plain-text parser

Grammar transcription:

```text
TABLE page=P order=O
HEADER_ROWS=N
ROW|cell 1|cell 2|cell 3
...
END_TABLE
```

Parser:

- сохраняет empty cells между delimiters;
- требует одинаковую row width внутри table block;
- требует `END_TABLE`;
- отклоняет Markdown fences, commentary и trailing content;
- отличает `NO_TABLES`/`NO_TABLE page=P order=O` от malformed response;
- сохраняет только complete prefix blocks как non-authoritative diagnostic;
- не исправляет row width, cell values, signs или numbers;
- не использует fuzzy matching.

В reference cells literal `|` отсутствует: 0 occurrences как в selected draft, так и в full PyMuPDF cells. Поэтому доказанные width failures не объясняются легитимным source delimiter collision.

Observable tests:

```text
python -m pytest -q \
  services/broker-reports-gate1-proof/tests/test_broker_reports_direct_pdf_experiment.py \
  services/broker-reports-gate1-proof/tests/test_broker_reports_direct_pdf_plain_text_experiment.py

31 passed
```

## 7. ARM 1 — free document explanation

| Provider | Non-empty | Substantive lines with page refs | Pages covered | Manual comprehension review |
|---|---:|---:|---:|---|
| OpenAI | yes | 25/25 = 100% | 6/6 | все major section families найдены; правильные continuation families; есть unsupported claim о повторном miniature rendering на page 6 и image previews |
| Gemini | yes | 11/11 = 100% | 6/6 | все major section families найдены; sections/pages/continuations согласуются с document inventory; явных invented sections не найдено |
| Claude | yes | 25/26 = 96,15% | 6/6 | все major section families найдены; continuation families найдены; есть unsupported page-6 repeated rendering и несколько не source-bound причинных/суммирующих выводов |

Все три summary правильно распознали тип документа и основные families:

- asset/portfolio summary;
- cash summary and cash balances;
- detailed cash movements;
- securities trades and continuation;
- non-trade securities movements;
- issuer income;
- tax section;
- securities reference;
- footnotes.

Это доказывает high-level comprehension, но не complete extraction. В частности, OpenAI и Claude создали правдоподобное, но не подтверждённое утверждение о повторном визуальном рендере на page 6; actual page raster содержит footnotes only.

## 8. ARM 2 — page-by-page table inventory

### 8.1 Accepted artifact metrics

| Provider | Artifact | Reference identities | False tables | Exact rows | Exact columns | Exact headers | Continuation `4:1` from page 3 |
|---|---|---:|---:|---:|---:|---:|---:|
| OpenAI | valid | 14/14 | 15 | 0/14 | 12/14 | 7/9 | yes |
| Gemini | valid | 14/14 | 0 | 10/14 | 14/14 | 6/9 | yes |
| Claude | malformed | 0 accepted | 0 accepted | 0 accepted | 0 accepted | 0 accepted | no accepted artifact |

### 8.2 Claude complete-prefix diagnostic

До terminal format error Claude вернул 14 complete table blocks:

- raw prefix identities: 14/14;
- false identities: 0;
- exact columns: 14/14;
- exact rows: 1/14;
- exact headers: 9/9;
- continuation `4:1` from page 3: found;
- table purposes: 14 non-empty and manually aligned with known section inventory.

Artifact отклонён, потому что после `PAGE 6` модель добавила свободную строку о том, что таблиц нет, вместо завершения после последнего valid table block. Human-readable inventory оказался семантически сильным, но machine artifact остался invalid.

### 8.3 Interpretation

- Gemini доказывает, что direct native PDF способен независимо обнаружить все 14 tables без cell-level serialization.
- Claude показывает тот же semantic discovery в rejected artifact.
- OpenAI доказывает high recall, но не reliable table identity boundary: 15 false sub-tables.

Следовательно, предыдущая потеря identities не была чистой неспособностью увидеть таблицы. Для Gemini/Claude large cell output действительно был отдельным bottleneck.

## 9. ARM 3 — monolithic plain-text transcription

Ни один provider не вернул valid complete artifact.

| Provider | Finish | Input tokens | Provider output tokens | Visible output | Reasoning/thinking | Complete prefix tables | Failure |
|---|---|---:|---:|---:|---:|---:|---|
| OpenAI | `completed` | 15 050 | 9 888 | 9 888 | 0 | 2 (`1:1`, `1:2`) | `inconsistent_row_width` в `1:3`, row 4 |
| Gemini | `MAX_TOKENS` | 3 403 | 1 310 candidates | 1 310 | 31 454 | 0 | format start invalid + output budget exhausted |
| Claude | `max_tokens` | 22 527 | 32 768 | 6 908 | 25 860 | 0 | `inconsistent_row_width` в `1:1`, row 3 + output budget exhausted |

Provider counters нельзя механически сравнивать как один тип output token: Gemini считает visible candidates отдельно от thoughts, а Anthropic включает thinking в `output_tokens`. Поэтому в evidence сохранены и provider output, и visible output, и reasoning/thinking.

### 9.1 Comparison with previous strict JSON monolith

- OpenAI strict JSON: 11 839 / 12 264 / 12 280 output tokens; plain text: 9 888, то есть примерно на 18,47% ниже среднего. Но plain response содержал только два complete tables и сломался на grid width; результат не стал complete.
- Gemini strict JSON: total output-side budget около 32,75k tokens; plain text: 1 310 visible + 31 454 thoughts = 32 764. Реального снижения total output budget нет.
- Claude strict JSON: 32 768 output tokens; plain text: те же 32 768.

Plain text снизил syntactic overhead у OpenAI и увеличил visible share у Claude, но не решил monolithic completion.

## 10. ARM 4 — targeted whole-PDF transcription

Каждый запрос получал полный неизменённый PDF и только page/table order. Основные девять jobs оцениваются с failure penalty. Repeats не входят в primary accuracy.

### 10.1 Primary scheduled metrics, all 9 cases

| Metric | OpenAI | Gemini | Claude |
|---|---:|---:|---:|
| Accepted table artifacts | 3/9 | 6/9 | 5/9 |
| Matched selected identities | 3/9 | 6/9 | 5/9 |
| Exact selected-prefix structures | 0/9 | 6/9 | 4/9 |
| Exact full-engine structures, supplementary | 0/9 | 5/9 | 4/9 |
| Exact headers | 1/9 | 5/9 | 4/9 |
| Exact cells | 114/831 = 13,72% | 472/831 = 56,80% | 315/831 = 37,91% |
| Exact numeric-like | 4/325 = 1,23% | 156/325 = 48,00% | 63/325 = 19,38% |
| Empty-cell accuracy | 109/135 = 80,74% | 132/135 = 97,78% | 113/135 = 83,70% |
| Hallucinated non-empty cells | 26 | 3 | 22 |
| Omitted non-empty cells | 642 | 356 | 478 |

Failed/malformed response оценивается как empty table artifact, включая omission penalty. Expected empty positions при этом остаются exact, как и в исходном hybrid scorer.

### 10.2 Accepted-only diagnostic

Accepted-only не заменяет primary metric, но показывает качество values после успешной localization/serialization.

| Metric | OpenAI accepted 3 | Gemini accepted 6 | Claude accepted 5 |
|---|---:|---:|---:|
| Exact cells | 34/157 = 21,66% | 396/402 = 98,51% | 235/295 = 79,66% |
| Exact numeric-like | 4/50 = 8,00% | 156/159 = 98,11% | 63/83 = 75,90% |
| Empty-cell accuracy | 29/55 = 52,73% | 56/59 = 94,92% | 33/55 = 60,00% |

Gemini почти достиг hybrid на accepted subset, но не прошёл wide trade `3:2`, continuation `4:1` и grouped `4:2`. Поэтому table-by-table direct processing пока не является complete extractor.

### 10.3 Per-table outcomes

| Key | OpenAI | Gemini | Claude |
|---|---|---|---|
| `1:1` | accepted, 8/50 cells | accepted, 44/50 | accepted, 44/50 |
| `1:2` | accepted, 3/30 | accepted, 30/30 | accepted, 30/30 |
| `1:3` | width-invalid | accepted, 144/144 selected; full rows incomplete | width-invalid |
| `2:2` | width-invalid | accepted, 72/72 | accepted, 72/72 |
| `3:2` | width-invalid | missing required `ROW` prefix | width-invalid |
| `4:1` | width-invalid | width-invalid; one repeat `MAX_TOKENS` | width-invalid |
| `4:2` | accepted, 23/77 | width-invalid | accepted, 23/77 |
| `5:3` | width-invalid | accepted, 40/40 | width-invalid |
| `5:4` | width-invalid | accepted, 66/66 | accepted, 66/66 |

Width failures отражают разные actual separator counts внутри одного block. Source cells не содержат delimiter `|`; parser ничего не ремонтировал.

## 11. Repeatability

Два repeats выполнены для simple `1:2`, wide multi-row-header `1:3` и continuation `4:1`.

| Provider | Two accepted artifacts | Identical parsed artifact | Interpretation |
|---|---:|---:|---|
| OpenAI | 1/3 groups | 1/3 | simple output стабилен, но сам результат неточен; wide/continuation repeatably malformed |
| Gemini | 2/3 | 2/3 | simple и wide selected output стабильны; continuation не имеет двух accepted outcomes |
| Claude | 1/3 | 1/3 | simple correct and stable; wide/continuation repeatably malformed |

Raw response hashes различались даже при одинаковом parsed artifact. Repeatability grammar не доказывает correctness: OpenAI `1:2` был идентично неправильным.

Hybrid control также не имеет perfect repeatability: simple pair identical, а один wide repeat ранее вернул HTTP 200 + invalid JSON.

## 12. Exact post-hoc provenance relocation

После provider call каждый non-empty returned cell точно искался среди последовательностей PDF text-layer words:

- сначала внутри independently detected page/table bbox;
- затем на всей claimed page для ambiguity count;
- NFKC + whitespace collapse only;
- no fuzzy matching;
- unique exact match получал private independent `pdfword_*` refs;
- duplicate exact values оставались ambiguous.

Primary targeted accepted outputs:

| Provider | Returned non-empty | Exact in claimed table | Numeric exact | Unique exact word binding | Uniform provenance |
|---|---:|---:|---:|---:|---|
| OpenAI | 123 | 48 = 39,02% | 33/58 = 56,90% | 27 = 21,95% | Level 2 |
| Gemini | 650 | 650 = 100% | 324/324 = 100% | 259 = 39,85% | Level 2 |
| Claude | 440 | 393 = 89,32% | 131/140 = 93,57% | 158 = 35,91% | Level 2 |

Strongest individual provenance у всех providers достигает Level 4 только для uniquely relocated cells. Uniform provenance остаётся Level 2, потому что duplicate-value ambiguity и unmatched values не позволяют связать каждый returned cell с одним exact source word/cell ref.

Это не эквивалент hybrid Level 4: hybrid сохраняет candidate-bound production `source_value_ref`/`word_ref` для каждого принятого value до model call.

## 13. Direct comparison with adaptive hybrid

| Metric | Hybrid adaptive | Direct plain OpenAI | Direct plain Gemini | Direct plain Claude |
|---|---:|---:|---:|---:|
| Inventory table identities | 14/14 | 14/14 + 15 false | 14/14 | raw 14/14, artifact rejected |
| Primary targeted artifacts | 9/9 | 3/9 | 6/9 | 5/9 |
| Exact selected structures | 9/9 | 0/9 | 6/9 | 4/9 |
| Exact cells | 823/831 = 99,04% | 114/831 = 13,72% | 472/831 = 56,80% | 315/831 = 37,91% |
| Exact numeric-like cells | 322/325 = 99,08% | 4/325 = 1,23% | 156/325 = 48,00% | 63/325 = 19,38% |
| Exact headers | 9/9 | 1/9 | 5/9 | 4/9 |
| Empty-cell accuracy | 131/135 = 97,04% | 109/135 = 80,74% | 132/135 = 97,78% | 113/135 = 83,70% |
| Hallucinations | 4 | 26 | 3 | 22 |
| Omissions | 4 | 642 | 356 | 478 |
| Monolithic transcription complete | not the hybrid contract | no | no | no |
| Three-group repeatability | simple stable; one wide repeat invalid | 1/3 identical | 2/3 identical | 1/3 identical |
| All 15 experiment input tokens | 242 194 | 225 712 | 50 979 | 337 775 |
| Provider output tokens | 44 065 | 23 057 | 18 993 visible + 106 776 thoughts | 85 955 including 61 675 thinking |
| Strongest provenance | Level 4 candidate-bound, complete | Level 4 individual; uniform L2 | Level 4 individual; uniform L2 | Level 4 individual; uniform L2 |

Token totals отражают разные 15-call job mixes и provider accounting; они не являются cost benchmark без нормализации.

## 14. Business-summary comparison

Free explanations сравнивались с:

- previous direct OpenAI business extraction: 55 typed facts, 386/393 exact page relocations, 234/234 numeric page relocations, no Level 4 source binding;
- latest Gate 2 recovery evidence, где typed outputs подтверждены для `cash_movement`, `fee_commission`, `withholding_tax`;
- broader whole-document Gate 2 evidence по `trade_operation`, `income`, `position_snapshot` и связанным source units;
- known document section/table inventory.

Результат:

- все explanations упомянули cash, trades, portfolio/positions, issuer income, fees/tax и document evidence sections;
- currency/rate content также было замечено;
- prose покрывает document structure шире, чем отдельный typed fact output;
- prose не даёт validator-backed fact envelopes и не сохраняет source-value refs;
- OpenAI/Claude добавили unsupported visual claim на page 6;
- Claude дал больше numeric/causal statements, но это увеличивает unsupported-interpretation risk, а не доказанную accuracy;
- без human-reviewed business ground truth precision/recall prose не заявляются.

Убедительный пересказ подтверждает comprehension, но не authoritative business extraction.

## 15. Hypothesis matrix

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H1: comprehension good, JSON main problem | partially rejected | comprehension good, но monolithic plain также не завершён; targeted overall далеко от hybrid |
| H2: general understanding good, precise tables weak | supported for OpenAI/Claude; partial for Gemini | summaries strong; OpenAI/Claude cells weak; Gemini strong only on accepted subset |
| H3: output size main problem, not schema | strongly supported for Gemini/Claude, partial overall | monolithic token limits сохранились; targeted Gemini значительно лучше, но grid failures остались |
| H4: strict schema main problem | rejected | ни один monolithic plain artifact не complete |
| H5: hybrid materially stronger | supported | 99,04/99,08%, 9/9 and complete Level 4 vs incomplete direct arms |

## 16. Root-cause conclusion

Разделение причин:

1. **Document comprehension:** в целом хорошее у всех трёх providers.
2. **Table discovery:** сильное у Gemini; семантически сильное, но format-invalid у Claude; over-segmented у OpenAI.
3. **Table transcription:** provider- и table-class-dependent; wide/continuation cases остаются слабыми.
4. **Business interpretation:** покрытие сильное, но unsupported claims и отсутствие business ground truth сохраняются.
5. **Structured serialization:** plain text уменьшает schema surface, но не устраняет row-width, prefix и terminal-format failures.
6. **Source-value provenance:** direct post-hoc binding частичная и ambiguous; hybrid binding complete by construction.

Предыдущий bottleneck был комбинацией output size, monolithic serialization и table-grid reconstruction. Strict JSON была дополнительным фактором, не корнем всей проблемы.

## 17. Recommended production role

Plain direct PDF может служить:

- document explanation / human-review aid;
- table inventory challenge signal;
- monolithic recall audit на уровне sections/identities, но не cells;
- targeted candidate/challenge path для simple tables;
- independent comparison against hybrid results.

Plain direct PDF пока не может служить:

- authoritative monolithic table extractor;
- complete direct table-by-table primary;
- automatic financial source-fact materializer;
- replacement for candidate-bound hybrid provenance.

Intermediate normalization допустима только как rejected-by-default candidate artifact:

```text
native whole PDF
-> targeted table request
-> strict line parser
-> exact structure/cell validation
-> exact source-word/source-value binding
-> hybrid comparison or human review
```

Без последующих validation/binding steps plain text не является normalization truth.

## 18. Next implementation decision

Production rollout: **не выполнять**.

Если продолжать research, минимальный следующий slice:

1. Gemini-only targeted challenge на allowlist simple table classes.
2. Explicit unsupported terminal для wide/continuation/grouped failures.
3. Candidate-bound relocation до принятия artifact; ambiguity остаётся blocker.
4. Новый delimiter/escaping protocol исследовать отдельным experiment version, не ремонтировать текущие responses.
5. Получить actual human sign-off на девять reference cases.
6. После sign-off повторить только approved targeted corpus и сравнить с hybrid по тем же hard thresholds.

До этого adaptive hybrid остаётся необходимым authoritative candidate path.

## 19. Evidence and reproducibility

Research-only code:

```text
services/broker-reports-gate1-proof/scripts/direct_pdf_plain_text_experiment_contracts.py
services/broker-reports-gate1-proof/scripts/direct_pdf_experiment_transports.py
services/broker-reports-gate1-proof/scripts/local_direct_pdf_plain_text_experiment.py
services/broker-reports-gate1-proof/tests/test_broker_reports_direct_pdf_plain_text_experiment.py
```

Safe aggregate:

```text
ignored private safe experiment evidence (path withheld)
```

Private ignored evidence:

```text
ignored private journal, experiment and pre-fix evidence (paths withheld)
```

Safe report содержит только aggregate metrics, hashes, safe table keys и failure classes. Raw customer values отсутствуют.

## 20. Final statuses

Proven as terminal research assessments:

- `BROKER_REPORTS_DIRECT_PDF_PLAIN_TEXT_OPENAI_ARM_COMPLETED`
- `BROKER_REPORTS_DIRECT_PDF_PLAIN_TEXT_GEMINI_ARM_COMPLETED`
- `BROKER_REPORTS_DIRECT_PDF_PLAIN_TEXT_CLAUDE_ARM_COMPLETED`
- `BROKER_REPORTS_DIRECT_PDF_DOCUMENT_COMPREHENSION_ASSESSED`
- `BROKER_REPORTS_DIRECT_PDF_TABLE_INVENTORY_ASSESSED`
- `BROKER_REPORTS_DIRECT_PDF_MONOLITHIC_TRANSCRIPTION_ASSESSED`
- `BROKER_REPORTS_DIRECT_PDF_TARGETED_TRANSCRIPTION_ASSESSED`
- `BROKER_REPORTS_DIRECT_PDF_SCHEMA_VS_OUTPUT_LIMIT_DIAGNOSED`
- `BROKER_REPORTS_DIRECT_PDF_PLAIN_TEXT_VS_HYBRID_COMPARED`
- `BROKER_REPORTS_DIRECT_PDF_PLAIN_TEXT_TARGET_ROLE_READY`

Not proven:

- human-signed authoritative cell accuracy;
- complete direct table extraction;
- uniform Level 4 direct provenance;
- production rollout readiness.

Terminal verdict:

```text
DOCUMENT COMPREHENSION:
GOOD, NOT COMPLETE EXTRACTION PROOF

TABLE INVENTORY:
GEMINI STRONG; CLAUDE SEMANTICALLY STRONG BUT FORMAT-INVALID; OPENAI OVER-SEGMENTED

MONOLITHIC PLAIN TABLE TRANSCRIPTION:
REJECTED FOR ALL PROVIDERS

TARGETED PLAIN TABLE TRANSCRIPTION:
PROMISING AS GEMINI CHALLENGE PATH, NOT COMPLETE PRIMARY

ADAPTIVE HYBRID:
STILL REQUIRED FOR AUTHORITATIVE LEVEL 4 CANDIDATE FACTS
```
