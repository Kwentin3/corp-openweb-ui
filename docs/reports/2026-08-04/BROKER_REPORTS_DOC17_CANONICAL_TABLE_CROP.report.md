# DOC17 — Canonical Table Crop Quality Contract

## Verdict

`DOC17_RESULT = BLOCKED`

`CANONICAL_TABLE_CROP = NOT_READY`

The existing DOC15 corpus improved from 12 clean, 7 clipped, and 5 contaminated crops to 24 structurally and visually clean crops. That result is deterministic, uses one factory-routed canonical `table_region`, contains no table-specific runtime identities, and made no provider calls.

The independent terminal v4 holdout failed: only 2 of 12 frozen visual regions passed. The resolver nevertheless returned `CROP_CLEAN` for all 12, producing 10 false-clean outcomes. The contract therefore cannot be admitted.

## Previous path and root causes

DOC15 rendered the existing candidate bbox with a fixed 12-point margin. That path could not distinguish attached title/header/note geometry from page furniture and could not correct media-to-crop-box coordinate offsets.

The 12 DOC16 defects were traced individually. The repeated causes were coordinate-space mismatch on four StoneX cases; title/header/note geometry outside the candidate; detached page footer or prose retained by fixed padding; and candidate boundaries crossing neighboring content. The private root-cause ledger contains one proven row per defective table.

## Implemented authority

`PdfTableRasterFactory.create` remains the sole construction boundary. It resolves one `table_region`, then uses the same contract for image crop, future source-text scope, provenance, and diagnostics. The runtime uses observable geometry only: page/crop-box transforms, vertical components, repeated numeric alignment, bounded header/body/note continuation, rules, prose barriers, and page furniture. No PDF hash, issuer, table ID, page number, or per-document margin is present in the policy.

Policy versions are `pdf_table_candidate_raster_policy_v4` and `canonical_table_region_policy_v3`. Ambiguity remains fail-closed through `CROP_AMBIGUOUS` or `CROP_BLOCKED`.

## DOC15 result

- Baseline reproduced exactly: 24 tables; clean 12, clipped 7, contaminated 5.
- After: clean 24, clipped 0, contaminated 0, false-clean 0.
- All 24 outputs were opened in the contact sheet and compared with the source-page context used by the frozen audit.
- Deterministic replay matched bbox, pixel dimensions, PNG byte size, PNG SHA-256, manifest hash, and status for all 24.
- Provider calls: 0.

## Blind holdout history

Every failed holdout stayed failed and was not relabelled after a diagnostic replay. v1 scored 5/12, v2 0/12, and v3 7/12. General policy corrections made after v3 produced 12/12 only on a diagnostic replay, so that replay was not admission evidence.

The terminal v4 gold was sealed before resolver execution with SHA-256 `59665823263b69d8faddb5cb5f82059578c2d4d319bd8d1cd91c52149d345eeb`. It contains four tables each from new official PDFs published by Aramco, CNH Industrial, and Kuehne+Nagel.

v4 result: 2 clean, 10 failed, 10 false-clean, 0 provider calls. Repeated failures include detached standard notes, a valid body tail rejected as prose, omitted titles, and retained page furniture. Two page-number exclusion checks also expose a conservative gold selector limitation, but removing those two checks cannot turn 2/12 into a pass.

No policy code was changed after viewing v4.

## Tests and boundaries

Focused canonical/intake/bundle/actual-corpus tests: 50 passed.

Full suite: 2824 passed, 5 skipped, 5 failed. The five failures are the pre-existing DOC8–DOC11.1 frozen-hash bindings for two user-modified experiment files. DOC17 did not edit those files. Because the requested acceptance requires the full relevant suite to pass, this is reported as `NOT_PASSED`, not waived.

No dependency manifest changed. VLM prompt, structured-output schema, provider routing, parser semantics, DOC6, Gate 2, and activation state were unchanged.

## Performance

On DOC15, mean crop time increased from 0.0469 s to 0.1612 s per candidate (3.44×); total artifact bytes decreased from 3,506,136 to 3,298,903. The measured Python peak increased from 11,725,652 to 28,373,135 bytes. Crop-path full-page render count remained zero.

The terminal v4 holdout averaged 0.1704 s per candidate. These costs are measured but not accepted because the quality gate failed.

## Stop boundary

The mechanism remains research-only and inactive. Image-only normalization is not rerun. The next authorized step, if desired, is a new general crop-policy research goal that begins from the v4 failure classes and uses a fresh blind holdout.

```text
DOC17_RESULT=BLOCKED
CANONICAL_TABLE_CROP=NOT_READY
DOC15_CROP_CLEAN=24
HOLDOUT_CROP_CLEAN=2
NEXT_STEP=FURTHER_CROP_RESEARCH_REQUIRED
```
