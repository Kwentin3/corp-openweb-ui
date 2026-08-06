# DOC22 brief

Research shadow full-document package подтвердил гипотезу: Google 22/24 materially sufficient, Opus 23/24; parser context спас 40/43 isolated critical cases. Все clipped/contaminated cases достаточны на document level; неоднозначности находятся в clean crops, поэтому приоритет — минимальный document-context contract, не новое crop-правило.

Exact `gpt-5.6-sol` preflight прошёл (235290 input tokens, HTTP 200), но one-shot automated run завершил только 23/48, остальные 25 получили HTTP 429. Все calls учтены, retry/fallback/repair = 0. Наблюдаемое agreement 20/23; verifier пропустил 3/3 direct ambiguities. `AUTOMATED_AUDIT=BLOCKED`.
