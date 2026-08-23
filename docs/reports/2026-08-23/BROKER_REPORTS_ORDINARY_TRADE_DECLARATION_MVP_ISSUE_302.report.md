# Broker Reports Issue #302: ordinary trade to FNS XML MVP

Status: `ORDINARY_TRADE_FNS_XML_MVP_PRODUCED`

Exact base `main`: `d88684d78655180658a51ba0e3c341be020077cb`

## Result

The existing ordinary-trade production root now has one optional, fail-closed
declaration composition. With all current owners configured it reads persisted
Canonical-derived Fact v2, selects the only supported disposal itself, reuses
the existing Operation/Category/Tax Base/right-side/Scope/Package/release/XML
owners, validates against the official XSD, and persists private XML plus a
lineage receipt. Without the complete owner set the production root stops on
the exact `ordinary_trade_declaration_authority_owners_required` blocker and
does not create XML.

No new calculator, assembler, receipt framework, registry, SQL projection,
Gate 3 path or LLM runtime was added. The active route remains
`OrdinaryTradeProductionRuntimeFactory.create`.

## Official 2025 authority

The selected form is 3-NDFL KND 1151020, electronic format 5.20, XSD
`NO_NDFL3_1_033_00_05_20_01.xsd`, under FNS Order ED-7-11/913@ of
20 October 2025. The FNS order page states that the form applies beginning
with declarations for tax period 2025; the FNS forms page independently lists
the same order for period 2025.

Primary sources and captured checksums:

| Official source | SHA-256 |
| --- | --- |
| [FNS order page](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/) | page locator |
| form PDF `16589324_1.pdf` | `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` |
| procedure DOCX `16589324_2.docx` | `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` |
| format DOCX `16589324_3.docx` | `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` |
| official XSD | `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |

Live downloaded procedure, format and XSD bytes exactly matched the existing
repository pins. The unchanged operation and income-group rules are now
published as the audited current versions `2026.2-audited` and
`2026.3-audited`; source-consumption and declaration-input resources bind those
exact versions and all four current byte sets are hash-pinned. No new legal
rule was inferred in this issue.

## Supported-case matrix

| Dimension | Supported | Rejected/blocked |
| --- | --- | --- |
| period/form | 2025 / KND 1151020 / format 5.20 | any other period/form |
| taxpayer | authenticated individual resident, self-signer | missing/foreign taxpayer, representative |
| operation | one purchase + one disposal, organized market, outside IIS | multiple disposals, IIS, derivatives, dividends, coupons |
| amounts | RUB, positive result, complete current Fact v2 roles | FX, malformed/missing roles, loss carry-forward |
| commission | disposal-local charges, each consumed once | acquisition commission remains `LEGAL_INTERPRETATION_REQUIRED` |
| filing scope | explicit authenticated zero/choice facts | omitted facts or caller defaults |
| authority | current inspection/source/budget/applicability publication | missing, stale, foreign or malformed publication |
| output | private deterministic XML + receipt, XSD and semantic validation | partial XML or FNS transport |

## Owner and adjacency proof

| Stage | Single owner and retained binding |
| --- | --- |
| Canonical -> Fact v2 | current ordinary projection and Gate 4 Fact owner; no PDF reread |
| case -> taxpayer | authenticated provider adapter; persisted binding is current across execution runs but exact for user/case/taxpayer |
| Fact -> Operation | deterministic source consumer retains disposal/acquisition/commission fact IDs |
| Operation -> Category | Category member binds exact operation model SHA-256 and separate taxpayer scope |
| Category -> Tax Base | Tax Base retains exact Category input binding |
| Tax Base/right facts -> Scope/Package | existing component owners plus Scope and Package snapshots |
| Package -> release -> projection | semantic and projection owners replay exact predecessor artifacts |
| projection -> persisted XML | production adapter persists only owner-produced bytes and receipt |

The new adapter owns only call order, validation of the two injected provider
contracts, active persistence and technical accounting. It does not repeat the
six right-side assembly functions or any tax/XML calculation.

## Visual and semantic comparison

The representative path was inspected side by side:

| Current source | Operation/Category | Tax Base/XML |
| --- | --- | --- |
| purchase `100.00`, quantity 10 | FIFO consumed 4 -> acquisition cost `40.00` | accepted expenses `43.00` |
| disposal `60.00`, quantity 4 | gross `60.00` | tax base `17.00` |
| two disposal-row charges `1.00 + 2.00` | direct expense `3.00`, counted once | 13% whole-ruble tax `2`; payable `2` |

The checked-in review XML is
`BROKER_REPORTS_ISSUE_302_MVP_DECLARATION.safe.xml`. It is a UTF-8 visual copy
of the byte-stable `windows-1251` wire artifact. Both represent the same XML
tree; the review copy independently passes the pinned official XSD and explicit
gross/expense/base reconciliation assertions.

## Adversarial matrix

| Experiment using genuine owner outputs | Result |
| --- | --- |
| identical current owners, repeat execution | identical wire XML bytes/SHA-256 |
| disposal proceeds `60 -> 64` through Canonical owner | Fact-set and XML hashes change; old output is not current |
| case A facts + case B taxpayer/user/external owner | context/binding rejection before XML |
| authenticated user or external owner publishes successor | old result rejected by `validate_current_declaration` |
| live B receipt with genuine XML A and recalculated outer receipt hash | `ordinary_trade_declaration_mvp_stale_or_misbound` |
| duplicate/multiple disposal scope | `ordinary_trade_declaration_disposal_binding_required`; no disposal is guessed or dropped |
| missing/malformed inspection, IIS status, authority or identity | exact typed owner blocker; no XML |
| caller tries to provide disposal/taxpayer/methodology/Package | no such production parameters exist |
| acquisition commission | existing legal blocker survives and prevents release |
| XSD-valid fixture with semantic totals | independent reconciliation passes |
| XSD-valid but semantically inconsistent XML | existing semantic owner/receipt validation rejects it |
| Human Adapter attempts source, taxpayer, external or legal closure | outside accepted provider contracts; rejected |

Existing Issue #295 cross-run tests continue to prove every adjacency through
Fact -> Operation -> Category -> Tax Base -> Scope/Package -> release/projection,
including recomputed external stage hashes. Existing Issue #301 tests continue
to prove every request returned from one publication is current.

## SQL, LLM and scope stop

SQL was experimentally unnecessary: the active consumer already resolves
persisted Canonical projections into current Fact v2 and all downstream owners
consume those typed artifacts. Adding SQL would create no required consumer
contract for this vertical slice.

Calculation and declaration assembly make zero model/LLM calls. The injected
identity/user/external providers supply current owner facts only; they do not
calculate tax or assemble declaration fields.

Submission to FNS, real identities, additional income families, foreign
currency, multiple operations, IIS, losses and partial acquisition commission
remain explicitly outside this MVP and fail closed.

## Verification

- `174 passed`: authenticated binding, MVP, active composition, bridge,
  Operation, Category, official projection and ordinary production owners;
- `83 passed`: Human Fact Scope, architecture, bundle parity and cross-gate
  regressions;
- `13 passed`: MVP artifact, production-root, identity/authority, successor,
  cross-run hybrid, XSD and semantic fixture checks;
- `708 passed`: exact local reproduction of the repository focused CI suite;
- Ruff, Python compilation and `git diff --check`: passed.

The historical G5.35 end-to-end route remains outside this activation and
retains its pre-existing missing-Gate2-Canonical baseline (`6 failed`,
`3 errors`). It was neither used nor repaired for this MVP.

Exact-head CI and PR identifiers are appended after publication.
