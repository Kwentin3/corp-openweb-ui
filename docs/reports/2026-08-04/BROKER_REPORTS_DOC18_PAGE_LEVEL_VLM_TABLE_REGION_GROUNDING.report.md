# DOC18 — Page-level VLM table region grounding

## Outcome

`DOC18_EXPERIMENT=COMPLETED`  
`PAGE_LEVEL_VLM_TABLE_GROUNDING=INCONCLUSIVE`  
`BEST_CHEAP_GROUNDER=models/gemini-3.5-flash-lite`  
`BEST_REFERENCE_GROUNDER=claude-opus-5`  
`MULTI_PROVIDER_GROUNDING=NOT_CONFIRMED`  
`NEXT_STEP=KEEP_DETERMINISTIC_CROPPER_RESEARCH`

DOC18 is a frozen research experiment only. No product route, runtime activation, table normalization, DOC6 contract, or Gate 2 behavior changed.

## Frozen experiment

- 12 complete page images from 3 public official issuers; 21 visual tables and 2 no-table controls.
- Four multi-table pages, borderless layouts, titles/captions, attached notes, and boundary-adjacent tables were sealed before the first provider call.
- One fixed Russian provider-neutral prompt and one minimal `tables[].bbox` schema were used.
- The model saw only `page.png`, the fixed prompt, and the schema. It saw no candidate regions, parser text, fragment IDs, prior boxes, gold, other models, or financial dictionary.
- Exactly 48 one-attempt calls were accounted; retries, fallback, best-of, repair, and manual box correction were zero.
- Runtime work was bounded to validation, normalized coordinate projection, page clipping, and exact zero-padding crop rendering through the existing factory.

## Results

| Model | Valid JSON | Recall | Precision | Usable crops | Multi-page exact | No-table FP | Promising |
|---|---:|---:|---:|---:|---:|---:|---:|
| `claude-haiku-4-5-20251001` | 100.0% | 38.1% | 42.1% | 0.0% | 0.0% | 0 | NO |
| `claude-opus-5` | 100.0% | 85.7% | 85.7% | 0.0% | 0.0% | 0 | NO |
| `models/gemini-3.5-flash-lite` | 91.7% | 66.7% | 70.0% | 0.0% | 0.0% | 0 | NO |
| `gpt-5.4-mini-2026-03-17` | 100.0% | 61.9% | 61.9% | 0.0% | 0.0% | 0 | NO |

`PROMISING` requires 100% structured validity, at least 95% recall and precision, at least 90% borderless recall, at least 80% exact multi-table pages, at least 90% usable crops, and zero no-table false positives.

## DOC17 comparison boundary

Six DOC18 pages have exact stored DOC17 v4 terminal results. DOC17 was neither changed nor rerun. The other six stress/control pages have no stored DOC17 terminal crop, so full-corpus same-page superiority is `INCONCLUSIVE`; DOC18 therefore does not claim the experiment-level PASS condition even if a model clears the standalone grounding thresholds. This is a proof boundary, not a replacement rule.

## Scope stop

Mistral and Qwen were not called. No fail-closed VLM crop pipeline was designed or activated in DOC18. The next step above is only a recommendation from the frozen result.
