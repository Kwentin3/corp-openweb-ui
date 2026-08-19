# G5.39AC — Confirmatory Proof of the Consumer-First Declaration Boundary

Verified: 2026-08-12
Mode: confirmatory research and refactor-impact audit only
Terminal result: `THREE_CONTRACT_RUNTIME_BOUNDARY_CONFIRMED`

The answer to the final question is **YES for the frozen supplied case**. A
strict G5.39AB Declaration Semantics instance, released only after independent
audit/calculation and completeness checks, produced the same 49 target values,
the same target paths, the same 1,112 XML bytes and an XSD-valid document. This
is not authorization to refactor production.

Safe machine-readable evidence:

- [frozen receipt and experiment results](./BROKER_REPORTS_GATE5_CONSUMER_FIRST_BOUNDARY_G5_39AC.receipt.safe.json);
- [exact 49-mapping, impact and prerequisite-test matrix](./BROKER_REPORTS_GATE5_CONSUMER_FIRST_BOUNDARY_G5_39AC.matrix.safe.json);
- [redacted frozen candidate instance](./BROKER_REPORTS_GATE5_CONSUMER_FIRST_BOUNDARY_G5_39AC.candidate.safe.json).

## 1. Hypothesis statement

The tested claim was deliberately narrow: immediately before the current
Projection Definition, the already-complete supplied case needs only:

1. Declaration Semantics containing declared values;
2. separate Calculation Evidence that can replay derived values;
3. a separate Completeness Receipt that releases the values only after all 25
   trusted obligations are terminal.

The Resolved Package may remain the sealed audit authority, but its component
graph, hashes, methodology snapshots and obligation rows need not be the
projector's value contract.

The experiment reused the current factories and current projection engine. It
did not invent tax reasoning, read source documents, use Gate 4, edit a Tax
Model, change the trusted Definition, or modify a production mapping.

## 2. Frozen baseline receipt

The dirty canonical checkout was not modified. A detached temporary worktree at
the exact current `HEAD` received a byte-exact overlay of the current service,
including untracked files required by the present proof chain.

| Authority/artifact | Frozen identity |
| --- | --- |
| repository | `HEAD 02659a9b0bdfb2f19171d2a070a660af85119d59`, tree `0a696522eb37eca13bb9224a41f7227823c8ce8c` |
| Resolved Package | declared hash `8ada423c...c2c461`; canonical bytes `147888`; bytes hash `8d870aaa...00f9fb` |
| current Semantic Input | declared hash `aa8bb903...40283`; canonical bytes `11124`; bytes hash `2dd39d35...ded660` |
| Projection Definition | `ru_3ndfl_2025_full_target_supplied_case`, `2026-08-11.0-proof`, `48109cc6...c7b26` |
| trusted Definition | `ru_3ndfl_2025_root_declaration`, `2026-08-10.1`, `8d2a4ad1...bf19d` |
| official XSD | `178427` bytes, `08312832...1e4484` |
| current XML | `1112` bytes, `07d2a96d...a8ef2a`, XSD valid |
| completeness receipt | receipt hash `f8dffdbd...33288`; zero blockers |
| current mappings | `49` occurrences / `49` unique IDs |

The focused current-path test passed: `1 passed in 2.48s`.

The first isolated checkout run failed on a managed-resource hash because Git
had converted current dirty bytes to CRLF. Replacing the service overlay with
byte-identical canonical-tree files removed that transport artifact; no code or
authority was repaired.

Two fresh SQLite runs generated different Package and current Semantic Input
hashes while producing identical XML. The differences are run-local artifact,
supplemental-fact and derived binding identifiers propagated through the sealed
hash graph. Therefore these Package/Semantic Input hashes are identities of the
single frozen run, not a global determinism claim. This does not weaken the
experiment: the exact frozen Package was the sole extraction authority, while
the strict value candidate itself reproduced the same stable hash
`105e8883...962b6` in a separate replay.

## 3. Exact projection dependency map

The production resource contains 49 mappings at
[`gate5_full_target_xml_projection.ru_3ndfl_2025.v0.json`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_target_xml_projection.ru_3ndfl_2025.v0.json).
Every mapping was traced through the current `_source_root` view to the exact
Semantic Input field and Package/component origin.

| Class | Count | Finding |
| --- | ---: | --- |
| `VALUE_DEPENDENCY` | 44 | each maps to an AB candidate value |
| `TARGET_MECHANICS` | 5 | four Definition constants plus electronic file ID |
| unclassified | 0 | none |

Four repeat selectors consume the budget, income-group, Russian-source and
securities collections. They also map exactly to the four candidate arrays.

Two current couplings are not value mappings:

- [`validate_semantic_input`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_declaration_semantic_input.py#L248)
  makes the projector validate audit/source bindings;
- [`_coverage_proof`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_full_target_xml_projection.py#L673)
  makes it inspect domain and obligation states.

Both only authorize projection. Neither supplies a declared target value. The
experiment moved both checks to the pre-projection release step.

The full row-by-row chain, including target path, current source path, exact
Semantic Input field, candidate path, research source path and component owner,
is in the matrix artifact. No expected taxonomy or hand-authored value was
injected.

## 4. Candidate Declaration Semantics instance

The frozen candidate has exactly these eight roots:

```text
tax_period
filing
taxpayer
signer
budget_dispositions[]
income_group_results[]
russian_source_income[]
financial_investment_results[]
```

It is 2,507 canonical UTF-8 JSON bytes with hash
`105e8883bc138b3a72ef0f1563b0ca32fadd72ccdc419729a535c1847db962b6`.
There is one row in each collection. Optional
`signer.representation_authority` is absent because the supplied signer is not
a representative.

The safe candidate artifact records every conceptual field's type and value
hash. It contains no raw taxpayer or financial values. The exact private
instance existed only in the isolated process and was not persisted to Git.

The candidate deliberately excludes Package/component IDs and hashes, scope
and case identity, obligation rows, methodology/derivation snapshots, target
locators, KND, format/program versions and electronic file ID. It is a research
contract, not a production DTO.

## 5. Calculation Evidence proof

All candidate fields were copied either from a direct declared fact or an
already-completed methodology result in the validated frozen Package. The
compiler performed no new tax reasoning. A binding registry accounts for every
one of the 44 value mappings.

Four representative derived values were then replayed independently from
separate Package evidence:

| Declared value | Independent replay | Result |
| --- | --- | --- |
| Appendix 8 `allowable_expenses` | sum eligible operation expense components, verify operation total, category total and candidate value | equal |
| Section 2 `tax_base` | category income + other income - non-taxable - deductions - accepted expenses | equal |
| Section 2 `calculated_tax` | frozen rate band + marginal formula + declared rounding | equal |
| Section 1 disposition amount | sum settlement payable/refundable results and bind the budget allocation | equal |

The exact value, methodology, input-snapshot and formula-trace hashes are in the
receipt. `russian_source_income[].withheld_tax` was checked against its direct
source-entry provenance and candidate hash; no fake calculation object was
created.

This proves the representative replay boundary required by AC. A future
production refactor still needs a test that registers/replays every projected
derived value, recorded as `REFACTOR_PREREQUISITE_TEST_GAP_CALCULATION_RECEIPTS`.

## 6. Completeness Receipt proof

The release check read the trusted Definition and sealed receipt, not the
candidate values. It established:

```text
25 obligation refs
25 unique refs
11 RESOLVED
14 NOT_ACTIVATED_FOR_SUPPLIED_CASE
0 NOT_APPLICABLE
0 blockers
all dispositions terminal
real-world taxpayer tax completeness not asserted
```

The different count from AB's older `8 projected / 17 non-projected` wording is
not an obligation loss. AC counts terminal obligation dispositions by resolved
domain state in the freshly replayed current Semantic Input; projection coverage
still contains all 25 rows and the current Projection Definition still reports
8 projected obligations. Both views are retained in their owning receipts.

## 7. Release-gate experiment

Current ownership is:

```text
Resolved Package
  -> rich current Semantic Input
  -> projector validates audit seal + completeness
  -> maps values -> serializes -> validates XSD
```

The isolated experiment was:

```text
Resolved Package (sealed audit authority)
  -> Calculation Evidence + Completeness Receipt
  -> release gate
  -> strict Declaration Semantics
  -> separate target-mechanics policy
  -> unchanged tree projector + serializer + XSD validator
```

The release gate passed Package status, completeness status, zero blockers, 25
unique terminal obligations and 49 value/mechanics bindings before handing off
values. The projector received Declaration Semantics and an explicit target
mechanics side input. It did not receive Package bytes, component snapshots,
source/component hashes, methodology traces, scope receipts or obligation
states.

The target-mechanics side input owns electronic file ID and expands
`budget_dispositions[].{kind, amount}` to the XML row's payable/refundable
attributes. This is representation shaping, not a missing declaration value.

## 8. Target equivalence report

The research copy changed only source paths. The target tree, node ordering,
mapping IDs, target paths, transforms, enum/code tables, constants, serializer,
XSD bytes and conformance validator were unchanged.

| Check | Result |
| --- | --- |
| official XSD | pass |
| target paths | 49/49 equal |
| rendered target-value hashes | 49/49 equal |
| XML bytes | exactly equal |
| XML SHA-256 | `07d2a96d89776d71877bdd1f30ce142a4c6b6f905e09d3e8bcfe238195a8ef2a` |

An additional mechanics probe changed only the electronic file ID. Its XML
remained XSD-valid; 48/49 target-value hashes stayed equal and the sole changed
mapping was `file-id`. This falsifies the idea that electronic file identity is
part of Declaration Semantics while making the byte difference explicit.

## 9. Negative tests

Removing `financial_investment_results[].allowable_expenses` from the released
candidate failed with
`gate5_full_target_projection_source_value_missing` at
`$item.allowable_expenses`. No XML was emitted and no Package fallback was
available.

After a successful release, removing Calculation Evidence and Completeness
metadata from the envelope given to the projection step did not alter the XML:
the output remained byte-identical with hash `07d2a96d...a8ef2a`. That metadata
was not in the projector's value input.

## 10. Current-vs-Candidate architecture delta

No current owner is shown to be semantically wrong. The delta is ownership at
one boundary:

- keep the Resolved Package as the sealed audit envelope;
- expose its already-computed declared values as the strict value view;
- keep calculation replay in separate evidence receipts;
- perform completeness/evidence release before projection;
- change the projector consumer contract, not its tax or XML behavior.

The existing E2E factory sequence at
[`gate5_end_to_end_full_target_xml.py`](../../../services/broker-reports-gate1-proof/broker_reports_gate1/gate5_end_to_end_full_target_xml.py#L534)
already provides the single orchestration seam: Package at line 534, current
Semantic Input at line 544 and projection at line 547. No cross-module rewrite
was needed for this proof.

## 11. Refactor impact map

The safe matrix records owner-by-owner semantic, audit, evidence, replay,
migration, compatibility, performance and operational risk.

The conservative classifications are:

- `KEEP_AS_IS`: Resolved Package; trusted Definition/scope; existing Tax Models
  and typed declaration components; tree projector, serializer and XSD
  validator behavior;
- `KEEP_CHANGE_CONSUMER`: projection runtime/resource source paths and E2E
  wiring;
- `EXTRACT_BOUNDARY`: Calculation Evidence surface and Completeness release
  gate, reusing existing evidence rather than recalculating;
- `MOVE_RESPONSIBILITY`: audit/completeness checks out of projector input and
  into the release boundary;
- `DEPRECATE_LATER`: rich current Semantic Input fields only after consumer and
  persisted-artifact inventory plus parity migration;
- `DO_NOT_TOUCH`: Gate 4, product activation, PDF, databases, user isolation
  and unrelated dirty-tree state.

The highest risk is not projection code volume; it is audit and compatibility
drift if rich fields are removed before all consumers and persisted artifacts
are known.

## 12. Refactor prerequisite test map

Existing tests already protect Package sealing, completeness blockers,
component formulas, current Semantic Input validation, 49 mappings, 25 coverage
rows, official pins, missing-value failure, E2E hash chain, persistence and user
isolation.

No production test was edited. Before any refactor, new tests are required for:

- the exact eight-root candidate and audit-leak rejection;
- the independent release gate and evidence binding registry;
- current/minimal 49-mapping and byte parity;
- file-ID and budget-row target mechanics;
- refund, balanced, multi-allocation and empty-allocation cases;
- audit/completeness omission after release;
- calculation receipts for every projected derived field;
- stable value-view hashing despite run-local audit identifiers;
- persisted/external current Semantic Input consumer inventory.

Each is recorded with a `REFACTOR_PREREQUISITE_TEST_GAP_*` ID in the matrix.

## 13. KISS recommendation

If a separately authorized GOAL chooses to design a refactor, the smallest
credible change is three test-first slices:

1. evolve the existing Semantic Input factory owner in place to expose the
   strict Declaration Semantics value view and separate evidence bindings;
2. extract one release-gate owner from existing Package/Definition validation;
3. point the existing projector factory at released values plus a small explicit
   target-mechanics policy, versioning only source paths in the projection
   resource.

Do not introduce a second production model, reader, methodology engine,
compatibility framework or Package replacement. Do not remove the rich current
contract until consumer/persistence inventory and dual-path parity are complete.

## 14. Current knowledge

`PROVEN`:

- the frozen supplied case exists and the current E2E factory route passes;
- the exact AB candidate contains all declared values consumed by the 44 value
  mappings;
- Calculation Evidence and Completeness Receipt can remain independent;
- the released candidate produces 49/49 equal values and byte-identical,
  XSD-valid XML;
- missing values fail closed and audit omission after release is inert.

`FALSIFIED`:

- the projector needs the Resolved Package graph to serialize this case;
- audit hashes and obligation rows are declared-value inputs;
- electronic file ID is declaration business semantics;
- fresh-run Package/current Semantic Input hashes are globally stable when
  run-local evidence identities differ.

`UNKNOWN`:

- refund/balanced/multi-allocation target mechanics;
- sufficiency for inactive domains and all real 3-NDFL cases;
- persisted/external migration blast radius;
- production performance and operational behavior after a future change.

## Scope stop

G5.39AC stops here. No production code, tests, trusted Definition, Projection
Definition, Tax Model, persisted artifact, Gate 4/5 contract or product path was
changed. Experimental code was inline and was not retained. `G5.40` remains
unauthorized. The next allowed boundary is only a separately authorized,
careful minimal-refactor design discussion.

The temporary worktree directory and overlay patch were removed. Git no longer
registers the linked worktree and `git worktree list` exits cleanly with only the
primary tree. A shell-visible, ACL-inaccessible directory entry remains at
`.git/worktrees/codex-g539ac-worktree`; Windows denied its final removal. I did
not weaken ACLs or force-delete inaccessible metadata. No experimental code is
reachable there and product files are unaffected.
