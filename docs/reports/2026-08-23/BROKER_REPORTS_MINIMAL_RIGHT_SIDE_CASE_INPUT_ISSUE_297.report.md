# Broker Reports Issue #297: minimal right-side case input investigation

Status: `CONTROLLED RESEARCH / INACTIVE`

Terminal: `BOUNDED_DECLARATION_INPUT_BLOCKERS_PROVEN`

Date: 2026-08-23

## Dependency and starting point

- PR #296 reviewed head: `9c87e498aa54b266eee108b014960c7e40fe333c`.
- PR #296 merge commit and exact starting `main`:
  `6cb5bd477538745b5649deac1e71f6ca49d1c634`.
- The reviewed head is an ancestor of that `main`.
- Issue #295 was closed after the normal merge.
- Issue #297 started from one clean canonical worktree at that exact `main`.

The user-level `domain-boundary-change` skill was applied. Its canonical file
remains outside this repository. SHA-256:
`25c3ee26a6c238b682298f3d6462fcf6b40ae39bddf359d8f26870187a35b497`.
The generic skill text is not duplicated here.

## Outcome

The current contracts do not form a safe positive case-input boundary for the
Issue #295 route. Adding one envelope would hide, rather than solve, missing
owner contracts.

The decisive findings are:

1. `broker_reports_gate5_user_case_fact_v0`, produced by
   `Gate5HumanGapClosureRuntimeFactory.create`, has no authenticated user,
   case, taxpayer or tax-period binding. A genuine fact produced for user/case
   A was accepted by the same owner during replay for different user/case B.
2. The Human Adapter supports only five coarse keys and cannot represent the
   structured identity, filing, signer, completeness, settlement and budget
   facts required by the accepted assembly.
3. `Gate5ExternalEvidenceRuntimeFactory.create` is intentionally closed to one
   2025 resident securities rate-schedule fact. It cannot issue KBK, OKTMO,
   destination-authority or source-party reference facts.
4. `right_side_inputs` is a synthetic proof dictionary, not a set of
   owner-produced facts. The right-side assembler creates
   `synthetic_proof_evidence` provenance from caller values. Valid-looking
   family dictionaries from another run can therefore be transplanted before
   the owner boundaries.
5. Once real owner-produced Operation, Category, Tax Base, Scope, Package,
   release and projection artifacts exist, the merged Issue #295 adjacency
   checks reject cross-run hybrids correctly.

Therefore the smallest truthful result is a classified blocker proof. No new
runtime authority, packet DTO, registry, questionnaire, connector or generic
receipt engine was added.

## Official-source reality check

Primary sources were checked directly on 2026-08-23.

| Source | Result | Durable evidence |
| --- | --- | --- |
| [FNS Order ED-7-11/913@](https://www.nalog.gov.ru/rn77/about_fts/docs/16589324/) | HTTP 200; title identifies the order dated 2025-10-20; the page publishes the form, filling procedure, electronic format and XSD for tax period 2025 | order page plus repository-held official attachments |
| [Form PDF](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_1.pdf) | official form bytes | SHA-256 `d751043f63af1f0095a14228a65a3831acf47fcd82c397e2eb38b0f9f8dc9565` |
| [Filling procedure DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_2.docx) | official procedure bytes | SHA-256 `7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc` |
| [Electronic format DOCX](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/16589324_3.docx) | official format bytes | SHA-256 `f5215c237a8af73dd7a251cee94a2e09aacd8540173fcde2904b4c311129e3c2` |
| [Official XSD 5.20.01](https://www.nalog.gov.ru/html/sites/www.new.nalog.ru/files/about_fts/docs/xsd/NO_NDFL3_1_033_00_05_20_01.xsd) | repository copy decoded to 178427 bytes | SHA-256 `083128322833dbafb29be0bf919e33b7b362956244b422d34dd554c99a1e4484` |
| [FNS declaration submission guidance](https://www.nalog.gov.ru/rn77/fl/pay_taxes/income/pay_taxes/) | describes interactive filling/submission through the authenticated personal account and submission through an EDI operator; it does not document a public case-data API for this product | acquisition boundary only; no connector authority proven |
| [FNS forms and formats](https://www.nalog.gov.ru/rn77/taxation/taxes/ndfl/form_ndfl/) | identifies the 2025 form, procedure and electronic format | normative form/format evidence, not taxpayer-specific case evidence |
| [FNS KBK page](https://www.nalog.gov.ru/rn77/taxation/kbk/) | publishes budget classification material | reference-data source, not a case-time typed fact in the repository |
| [FNS inspection-requisite service](https://service.nalog.ru/addrno.do) | interactive service exposes inspection code, OKTMO and payment requisites | no authorized machine interface or repository owner proven |

The FNS XSD marks such fields as `КодНО`, `КБК` and `ОКТМО` structurally
required in their respective target nodes. That does not establish who knows
the taxpayer's destination inspection or applicable budget allocation. XSD
cardinality is representation evidence, not case-fact provenance.

No real FNS account was accessed, no credentials were requested, and no FNS,
CBR or exchange connector was built. For this RUB-only control no CBR FX fact
is applicable. No public, authorized interface for importing the required
taxpayer-specific FNS case packet was proven.

## Meaning-to-owner boundary map

```text
authenticated user/case/run/workspace identity
-> ArtifactAccessContext / authentication system
-> trusted context passed to Scope and source owners
-> declaration composition

human factual answer
-> Gate5HumanGapClosureRuntimeFactory.create
-> broker_reports_gate5_user_case_fact_v0
-> declaration preparation (not the active Issue #295 right-side assembler)

presence/absence intervals
-> Gate5ResidencyEvidenceRuntimeFactory.create
-> broker_reports_gate5_residency_evidence_v0
-> reviewed residency methodology

resident/non-resident classification
-> Gate5ResidencyEvidenceRuntimeFactory.create plus trusted methodology
-> broker_reports_gate5_residency_classification_v0
-> operation, income-group and filing consumers

broker transaction facts
-> Gate4OrdinaryTradeCandidateRuntimeFactory.create
-> Gate4FinancialCaseFactV2
-> deterministic securities Tax Models

source-party observation
-> source/metadata owner (missing active public composition for this route)
-> missing typed source-party case fact
-> taxable-income-source component

official reference observation
-> exact external-reference owner
-> only the closed rate-schedule fact exists today
-> no current KBK/OKTMO/destination-authority consumer seam

reviewed tax interpretation
-> Gate5TrustedMethodologyAuthorityFactory.create and typed behavior owners
-> version/hash-bound methodology output
-> Tax Model and declaration component owners

case applicability/completeness
-> Gate5DeclarationScopeResolutionRuntimeFactory.create and component owners
-> scope receipt and exact completeness bindings
-> resolved Package
```

The current `Gate5DeclarationRightSideAssemblyRuntimeFactory.create` remains a
call-order/component assembler for synthetic proofs. It is not promoted into
a user, source, external-reference or methodology owner.

## Requirement, source and owner matrix

`M` means mandatory for this bounded control, `C` conditional, and `N/A` not
applicable to this profile.

| Required meaning / current field family | Class | M/C/N/A | Sole intended owner and public contract | Effective scope and evidence | Current result / missing behavior |
| --- | --- | --- | --- | --- | --- |
| authenticated user, case, run and workspace | system/auth | M | `ArtifactAccessContext` | exact authenticated user/case/run/workspace | available and enforced by source/Scope owners |
| taxpayer identity distinct from operation subject | user/case | M | Human Adapter plus existing taxpayer binding validator | exact user/case/taxpayer/2025; authenticated fact | taxpayer binding exists for Operation/Category/Scope, but Human Adapter fact does not carry it |
| taxpayer name and INN | user/case or explicit source metadata | M | Human Adapter for confirmed identity; metadata adapter only for faithful source observation; filing owner validates final component | exact taxpayer/case/2025 and source refs | only a Boolean `taxpayer_identity_confirmed` Human fact exists; structured identity has no public producer seam |
| tax period and declaration intent | user/case plus trusted definition | M | Scope owner and authenticated intent | exact case and 2025 definition | Scope supports 2025, but Human facts themselves are not period-bound |
| physical-presence/absence intervals and reasons | user/case | M | `Gate5ResidencyEvidenceRuntimeFactory.create` | exact 2025 window, literal answer support, authenticated provenance | available as typed evidence |
| taxpayer period status | methodology | M | residency classifier under the trusted Article 207 rule | exact evidence hash and published methodology | available; direct caller/user status is rejected |
| filing instance, initial/correction state | user/case | M | Human Adapter for election/fact; filing component validates final structure | exact case/taxpayer/2025 | current Human fact is only text; no structured owner output for all fields |
| declaration date and electronic instance ref | technical filing context | M | system filing-context creator, then filing component | execution/date and exact case | synthetic caller values only; XSD need is not proof of user origin |
| destination tax-authority code | external/system filing context | M | authoritative inspection/reference owner, then filing component | taxpayer destination and effective period | no typed repository owner; FNS interactive lookup is not a proven connector API |
| signer identity, capacity and representation authority | user/case + auth | M | Human Adapter and authenticated context; filing component validates | exact user/case/taxpayer/2025 | coarse code fact exists; structured representation evidence seam is missing |
| disposal/purchase/charge amounts and lineage | broker/source | M | current ordinary Fact v2 owner | exact Canonical/source facts and case | available and bound |
| operation kind, market/IIS status, exemption/loss and expense prerequisites | mixed source, external reference, user fact and methodology | M for the proof values | existing source, Human, external and methodology owners by meaning | exact operation/taxpayer/period and provenance | #295 still uses `proof_assumption`/caller-resolved values; no single safe non-broker composition exists |
| category membership and whole-category completeness | user/case completeness plus Category owner | M | taxpayer binding and Category aggregation owner | exact sorted member hashes, taxpayer and period | category adjacency is protected; upstream completeness producer is still synthetic |
| other income, other allowable expenses, non-taxable income and deductions, including explicit zero | user/case and/or additional source evidence | M | income-group Tax Base validates `user_verified_fact`; Human/source owner must produce it | exact taxpayer/case/group/2025 and input binding | validator exists; Human Adapter cannot produce these structured facts |
| whole-income-group completeness | user/case completeness | M | income-group Tax Base owner validates exact input binding | exact Category/group values/taxpayer/2025 | stale binding is rejected, but current positive provenance is caller-supplied |
| withheld-at-source amount | broker/source | M for explicit zero or amount | Gate 4 source fact owner, then settlement owner | exact source/case/group/2025 | active control Fact roles do not supply it; settlement accepts synthetic values only |
| other settlement credits and their applicability | user/case, external facts or methodology depending on credit | C; explicit zero required by current control | respective evidence owner, then settlement owner | exact taxpayer/group/2025 plus completeness | no real provenance seam; current settlement validator accepts only synthetic proof provenance |
| all applicable income-group settlement completeness | user/case/Scope completeness | M | settlement and Scope owners | exact scope and Tax Base hashes | exact downstream binding exists; positive input producer is synthetic |
| source party name, INN and KPP | broker/source evidence | M for the selected Russian source occurrence | active source/metadata owner, then income-source owner | exact source occurrence/case/2025 | active Fact v2 roles are only amount, asset, currency, date, quantity and unit price; no active source-party seam |
| Russian-source and income-kind classification | methodology over authoritative/source facts | M | reviewed methodology, then income-source owner | exact source party/operation/period | caller literal today; user answer is not authority |
| source-party OKTMO | authoritative external reference | M in current target occurrence | missing exact reference owner, then income-source owner | exact entity/effective period/source bytes | current external owner cannot express it |
| KBK | authoritative external reference/methodology applicability | M in current budget occurrence | missing exact reference owner, then budget owner | exact tax kind/status/period and official bytes | FNS publishes classifications; no typed accepted fact or consumer seam |
| budget OKTMO | external/system filing context | M in current budget occurrence | missing destination/reference owner, then budget owner | exact taxpayer destination/case/period | interactive FNS lookup exists; no proven machine owner |
| payment/refund/reduction disposition | authenticated user election plus calculated settlement | M | Human Adapter for election, budget owner for derived amount | exact taxpayer/case/2025 and settlement hash | current Human fact is a coarse code; structured allocation evidence seam is missing |
| securities/digital/investment-partnership applicability and completeness | Scope plus typed legal classification | M for securities; other families inactive, not asserted absent | Scope and financial-investment component owners | exact scope and occurrence evidence | current caller supplies activated/not-activated lists and synthetic completeness |
| resident securities rate schedule | authoritative reference published into reviewed methodology | not a separate case fact in the current runtime | existing external evidence proof and trusted methodology authority | RU/resident/group 02/2025 | supported as one closed external fact; runtime applies published methodology, not a live lookup |
| foreign income, treaty and CBR FX | external/source/methodology | N/A | existing boundaries if later activated | foreign/currency-specific | intentionally not activated; no hidden zero |
| target mechanics / electronic file ID | system technical context | M for projection | filing component plus target projection | exact declaration instance | derived mechanically after semantic release |

## Experiment matrix

All experiments used isolated temporary stores. PowerShell set
`PYTHONPATH=.;tests` before Python execution. The synthetic source contained no
private customer values.

### Baseline and independent missing-family controls

| Experiment | Result | Terminal / owner classification |
| --- | --- | --- |
| unchanged Issue #295 synthetic control | accepted | `ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN`; XSD valid; 44 released values; 49 target occurrences |
| missing residency evidence | rejected before release | `USER_CASE_FACT_MISSING` |
| missing filing identity | rejected before release | `USER_CASE_FACT_MISSING` |
| missing source party | rejected before release | `SOURCE_EVIDENCE_INSUFFICIENT` |
| missing settlement | rejected before release | `USER_CASE_FACT_MISSING` |
| missing budget | rejected before release | `USER_CASE_FACT_MISSING` |
| missing income-group completeness | rejected before release | `USER_CASE_FACT_MISSING` |
| stale income-group input binding (existing executable test) | rejected before release | `INTERNAL_CONTRACT_OR_PIPELINE_DEFECT` |
| unknown operation methodology version | rejected | `gate5_trusted_methodology_not_published`; not converted to a user request |
| KBK requirement passed to current External Evidence owner | rejected at its public contract | `gate5_external_evidence_requirement_invalid`; not converted to methodology or broker evidence |

### Cross-run and mix-and-match

| Inputs | Real owner-produced? | Resealed? | Result | Meaning |
| --- | --- | --- | --- | --- |
| Human Adapter `taxpayer_identity_confirmed` from user/case A replayed under different user/case B | yes | request/fact was valid as produced | **accepted** | blocking defect in the proposed positive boundary: user fact has no user/case/taxpayer/period binding |
| settlement family A into synthetic right-side control B | no; caller dictionary | downstream receipt produced normally | **accepted** | raw synthetic input is not an evidence boundary |
| taxable-income-source family A into B | no; caller dictionary | downstream receipt produced normally | **accepted** | caller source refs are restamped as synthetic evidence |
| budget family A into B | no; caller dictionary | downstream receipt produced normally | **accepted** | no external/user owner artifact is checked |
| filing family A into B with same taxpayer ref but changed name/evidence ref | no; caller dictionary | downstream receipt produced normally | **accepted** | component validation cannot establish pre-component origin |
| genuine Category A + run B | yes | all available outer accounting and receipt hashes | rejected | `operation_to_category` adjacency |
| genuine Tax Base A + run B | yes | all available outer accounting and receipt hashes | rejected | `category_to_income_group_tax_base` adjacency |
| genuine Package/release/projection tail A + Scope B | yes | all available outer accounting and receipt hashes | rejected | `scope_to_package` adjacency |
| genuine released tail A + Package B (existing test) | yes | resealed | rejected | semantic release owner |
| genuine projection tail A + release B (existing test) | yes | resealed | rejected | projection-input owner |
| genuine Operation A + live Fact B (existing test) | yes | cannot complete reseal | rejected | exact source Fact owner binding |

A genuine 2024/2025 right-side packet mix cannot be executed because no such
owner-produced packet exists. This is not treated as a pass. The genuine Human
fact attack is stronger: even different authenticated user and case identities
are absent from the fact and the owner accepts reuse. A period change is also
not detectable from that artifact itself.

## Full adjacency audit

| Edge | Single owner | Proof status |
| --- | --- | --- |
| authenticated context -> source/Scope | Artifact access and Scope owners | protected |
| human request -> typed user fact | Human Adapter | fact integrity protected; execution identity binding missing |
| typed user fact -> active right-side component input | none | **missing seam** |
| source party observation -> income-source input | no active route owner | **missing seam** |
| external KBK/OKTMO/destination fact -> filing/budget input | no applicable external owner | **missing seam** |
| Fact v2 -> Operation | source-fact consumer / Operation owner | protected |
| Operation -> Category | Category aggregate | protected |
| Category -> income-group Tax Base | Tax Base owner | protected |
| Tax Base -> settlement component | settlement owner | protected once a real settlement fact exists |
| Scope -> filing/settlement/source/budget/financial components | each component owner | exact scope snapshot protected; pre-component fact origin missing |
| Scope and components -> Package | Scope/Package owners | protected |
| Package -> released semantics | semantic release owner | protected |
| released semantics -> projection/XSD | projection owner | protected |

The defect is before component creation, not in the merged downstream receipt
chain. Stage hashes continue to prove byte integrity; owner bindings prove
adjacency only after an owner has actually produced the artifact.

## Visual and semantic inspection

For the fully supplied synthetic control:

- Fact v2 exposed only `amount`, `asset`, `currency`, `date`, `quantity` and
  `unit_price` roles. It did not expose source-party identity.
- Operation gross income was RUB 60.00; related/allowable expenses were RUB
  43.00 (RUB 40.00 acquisition cost plus RUB 3.00 transaction expense).
- Category retained the same 60.00 / 43.00 values.
- Income-group total and taxable income were RUB 60.00; Tax Base was RUB 17.00.
- Package status was `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE`.
- Release emitted 44 semantic values and projection emitted 49 occurrences;
  official XSD validation was true.

This is not a real fully supplied case. Operation eligibility still contains
`proof_assumption` provenance and the right-side families contain synthetic
provenance. `DECLARATION_COMPLETE_FOR_SUPPLIED_CASE` means only completeness of
the supplied synthetic set; it does not establish real taxpayer completeness.

For a blocked control, deleting source-party evidence stopped before release
as `SOURCE_EVIDENCE_INSUFFICIENT`. Deleting residency, filing, settlement,
budget or income-group completeness stopped as `USER_CASE_FACT_MISSING`. No
released inventory, target tree or XSD receipt was produced.

The official XSD inspection was kept separate. Required target attributes
were not reclassified as user facts merely because XSD says `use="required"`.

## Minimal missing contracts

The full missing set cannot be safely collapsed into one packet. The smallest
owner-local work, in dependency order, is:

1. Human Adapter: add exact authenticated user/case/taxpayer/tax-period binding
   to every produced user fact and add only the structured fact variants
   actually demanded by filing identity, signer/election and explicit
   completeness controls. Foreign, missing, stale and misbound facts must fail
   closed at this owner.
2. Active source boundary: expose an exact source-party observation only if
   the current qualified source really contains it. Income-source jurisdiction
   remains reviewed methodology, never metadata or caller inference.
3. External-reference boundary: add separate, closed KBK,
   destination-authority and OKTMO requirements only when official bytes,
   entity/effective-period binding and the consuming component contract are
   known. Do not generalize the existing one-fact external evidence proof.
4. Settlement/component owners: accept real source/user/external provenance
   variants with exact scope bindings. Preserve missing versus explicit zero.
5. Composition: only after 1-4, replace synthetic `right_side_inputs` with the
   existing owner artifacts. Composition may order calls and report gaps; it
   must not mint provenance or normalize business meaning.

Implementing only a new envelope now would create a second owner for identity,
source classification, reference data and completeness. That change is
rejected.

## Uncomfortable questions

1. **Which inputs come from which class?** Broker facts supply the trade,
   acquisition and charge observations. Authenticated users supply identity,
   factual presence, signer/elections and explicit completeness. FNS supplies
   normative form/methodology evidence and official reference publications;
   taxpayer-specific personal-account data is only an unproven acquisition
   possibility. Inspection/KBK/OKTMO reference facts need explicit external
   owners. Methodology supplies tax classifications/calculations. The system
   supplies authenticated context and target mechanics.
2. **Was an XSD-required field mistaken for a real-world legal fact?** The
   current synthetic fixture effectively did this for destination code, KBK
   and OKTMO. The investigation separates structural requirement from value
   origin and does not accept the fixture as evidence.
3. **Is supposed FNS data availability assumed?** Yes, if described as a
   machine-importable case packet. Official pages prove interactive account
   and submission services, not an authorized public API for this product.
4. **Does one fact have competing owners?** The positive fixture makes the
   caller look like owner of source party, external references, settlement and
   completeness while component owners validate only the resulting shape.
   No second owner was added; the fixture remains synthetic.
5. **Did a synthetic value become a default or hidden zero?** The baseline
   contains many explicit synthetic zeroes. They are not accepted as real
   evidence or defaults. Missing values continue to block.
6. **Can a foreign packet pass after resealing?** A genuine Human Adapter fact
   from different user/case A passed under B without any reseal because its
   contract omits identity binding. Synthetic family dictionaries also pass,
   but they are not owner artifacts. A positive boundary is therefore denied.
7. **Can valid adjacent artifacts be mixed?** From Fact through projection,
   genuine owner artifacts are now rejected at every tested adjacency. The
   missing adjacency is before right-side component creation.
8. **Did LLM research become runtime authority?** No. No provider call was
   made. Official material remains reviewed source evidence and runtime uses
   hash-pinned deterministic methodology only.
9. **Is a proposed boundary smaller than existing contracts?** No safe new
   envelope was found. Owner-local contract additions are smaller and preserve
   one owner per meaning.
10. **What remains unresolved/non-production?** Authenticated user-fact scope,
    structured filing/signer/completeness facts, active source-party evidence,
    exact KBK/OKTMO/destination reference facts, real settlement provenance and
    all acquisition mechanisms remain unresolved. The route is inactive,
    synthetic, unfiled and not production-ready.

## KISS and scope stop

- No code or runtime contract changed.
- No new authority, envelope, DTO, connector, registry, DB, workflow, graph,
  questionnaire, LLM adapter or Tax Engine was added.
- No Declaration/XML behavior, SQL, Gate 3 route or product activation changed.
- No private customer/FNS data was accessed or committed.
- The merged Issue #295 inactive/shadow route remains unchanged.

The next smallest safe step is the Human Adapter scope-binding contract alone,
with genuine foreign-user, foreign-case, foreign-taxpayer, foreign-period and
stale-request tests. It must stop at typed fact publication; it must not also
build source-party, external-reference or declaration composition changes.
