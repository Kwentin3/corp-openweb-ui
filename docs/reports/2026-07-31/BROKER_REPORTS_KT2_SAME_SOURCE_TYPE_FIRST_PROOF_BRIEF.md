# Broker Reports KT2 Same-Source Type-First Proof — Brief

Date: 2026-07-31

KT2 is complete at the inactive proof boundary. One existing real Gate 2
package and three same-source real units were bound to privacy-safe structural
copies. The proof projects two opaque Pack-backed Type Cards, seals four exact
compiler-built options, consumes frozen plural responses, restores exact local
mappings, and reuses the existing validator, materializer, ArtifactStore, and
V6 evidence/replay authority.

The three-unit main path produced:

- one typed unit with exactly one plausible type and one exact option;
- one unclassified unit with multiple plausible types;
- one unclassified unit with no plausible type;
- zero unaccounted, unsafe, wrong-singleton, unbound-ref, duplicate-fact, or
  model-generated-value outcomes.

The false-singleton comparator detected its one case and typed none. Four safe
human-readable traces and exact replay are pinned by hashes; six resealed
tamper families fail closed.

Implementation PR #241 merged as
`16fe3d2b2dd68bbb6440ede3a9b7537849de7456` after agent boundary review and
green GitHub CI. Pre-merge full suites passed twice, including once after
`--cache-clear`: `2290 passed, 5 skipped` each time. Post-merge focused tests
passed `213`, and the post-merge full suite again passed `2290` with the same
five existing skips.

Corrective PR #242 fixed only the stale Current State lifecycle assertion and
merged as `24948360095a749e11b1b0bcedbb8ae871a6b7f8`; the complete post-merge
Stage Q was repeated on that exact main with the same green outcomes.

All three Function bundles rebuild with zero diff and omit the KT2 proof.
Fresh read-only live parity passed for 3/3 Functions and 12/12 Prompts. Because
repository and live bundle hashes are exact and unchanged, the proof is absent
from live and no deploy is required.

Evidence PR: #243. This brief becomes terminal only after that PR is merged;
its merge commit will be reported in the terminal response.

```text
KT2_SAME_SOURCE_TYPE_FIRST_PROOF = PASSED
ONE_PRODUCT_SEMANTIC_ROUTE = TRUE
ONE_CANONICAL_MATERIALIZER = TRUE
FALSE_SINGLETON_OBSERVABILITY = PROVEN
TYPE_FIRST_PRODUCT_REACHABILITY = FALSE
PROVIDER_CALLS = 0
LIVE_CHANGES = 0
KT2 = COMPLETE
MODEL_QUALIFICATION = NOT_STARTED
PRODUCT_ACTIVATION = NOT_STARTED
```
