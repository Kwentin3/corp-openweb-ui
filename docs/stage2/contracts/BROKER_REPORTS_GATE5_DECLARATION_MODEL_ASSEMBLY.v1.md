# Broker Reports Gate 5 Declaration Model Assembly v1

Status: `CURRENT SUPPORTING CONTRACT`

Goal: `G5.45`

This contract owns the consumer-first audit and controlled assembly proof for
the bounded Russian-source broker/securities 3-NDFL profile for tax period
2025. It does not activate filing, replace the Full Definition, or claim that
the frozen real taxpayer case is complete.

## Supported consumer boundary

The audited consumer is the official 3-NDFL XML target. Its values are traced
backward through the immutable consumer projection Definition, released
declaration values, one semantic owner, and a methodology-derived or direct
fact binding. The controlled forward path is:

```text
source/user/reference facts
-> existing typed contracts
-> existing methodology and Tax Model owners
-> resolved declaration package
-> released declaration values
-> representation-only projection
-> official-XSD-valid XML
```

The proof fixture is explicitly `CONTROL_EVIDENCE`; it is never a real
taxpayer declaration.

## Active Category composition addendum

Issue #295 adds the inactive
`ActiveCategoryDeclarationAssemblyRuntimeFactory.create` coordinator. It
starts from the Issue #293 factory route, not from a prebuilt operation or
Category Tax Model, and then delegates to the existing income-group,
settlement/component, Full Definition, Scope, Package, release and
consumer-first projection owners. Scope and Package use their additive
current-Fact entrypoints; historical Gate 3 and SQL-backed Gate 4 are trapped,
not fallbacks.

The allowed terminals are:

```text
ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN
BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
```

Any bridge blocker or demand is retained before release. In particular,
`partial_acquisition_commission_allocation` remains
`LEGAL_INTERPRETATION_REQUIRED` and produces neither released values nor an
XML receipt. The clean control uses no acquisition commission, keeps the
operation subject distinct from the taxpayer scope, emits 44 released leaves
and 49 target occurrences, and remains synthetic, unpersisted,
non-downloadable and shadow-only.

## Consumer-first inventory

The controlled target emits 49 value occurrences. Exactly 44 consume the 44
released semantic leaves, four come from the hash-pinned official projection
Definition, and one is target-instance mechanics. No released semantic leaf is
unconsumed.

| Target meaning | Mapping IDs | Semantic producer and origin | Missing behavior |
| --- | --- | --- | --- |
| file identity and official constants | `file-id`, `program-version`, `format-version`, `document-knd`, `tax-period-code` | filing-context owner for the file ID; projection Definition authority for four official constants | invalid target mechanics or Definition fails closed |
| filing and period reference | `document-date`, `reporting-year`, `tax-authority-code`, `correction-number` | filing-context direct facts; Full Definition tax-period reference | required released value absence fails closed |
| taxpayer and signer | `declarant-category`, `taxpayer-status`, `taxpayer-last-name`, `taxpayer-first-name`, `taxpayer-middle-name`, `taxpayer-inn-text`, `signer-capacity` | filing-context direct facts except `taxpayer-status`, which is produced only by `Gate5ResidencyEvidenceRuntimeFactory.create` under `taxpayer-residency-article-207-v1` | missing residency evidence produces `MISSING_EVIDENCE`; no status or XML is invented |
| budget disposition | `budget-kbk`, `budget-oktmo`, `budget-payable`, `budget-refundable` | budget reference bindings plus `Gate5DeclarationBudgetOutcomeRuntimeFactory.create` | projector does not derive amount kind or synthesize zero |
| income-group tax result | `income-group-code`, `total-income`, `non-taxable-income`, `taxable-income`, `tax-deductions`, `accepted-expenses`, `tax-base`, `calculated-tax`, `withheld-at-source`, `material-benefit-withheld`, `trade-fee-credit`, `fixed-advance-credit`, `foreign-tax-credit`, `patent-credit`, `tax-payable`, `tax-refundable`, `simplified-returned-or-credited` | income-group Tax Base and tax-settlement owners plus exact direct settlement facts | missing result or settlement input prevents release |
| Russian-source income | `source-income-kind`, `source-oktmo`, `source-income`, `source-tax-withheld`, `source-organization-name`, `source-organization-inn`, `source-organization-kpp` | `Gate5DeclarationIncomeSourcesRuntimeFactory.create` over exact source facts | unsupported or incomplete source accounting fails closed |
| financial-investment result | `securities-operation-kind`, `securities-gross-income`, `securities-related-expenses`, `securities-allowable-expenses`, `securities-loss-treatment` | `Gate5TaxPeriodCategoryAggregationRuntimeFactory.create` and existing securities methodology | missing acquisition/expense evidence stays an evidence or methodology blocker |

Each emitted occurrence records its exact target path and value hash, resolved
projection source, semantic path and hash, origin kind, one owner, and the
authority/evidence or calculation/input hashes. `origin_count >= 1` and
`methodology_or_direct_binding_known = true` are mandatory.

## Minimality and one-owner correction

Three values retained useful component/audit meaning but had no target
consumer: signer identity, budget disposition kind, and source-party kind.
They remain in their sealed component or evidence envelope and are no longer
released as declaration values. Payable/refundable meanings are now produced
by the budget owner; the projector no longer interprets `kind + amount` or
creates an implicit zero. Residency is classified once by the residency owner
and only that derived result is injected into downstream methodology/filing
inputs.

## Release, completeness and projection

Completeness decides whether the supplied scope is terminal; it does not
calculate tax. Declaration-value release requires the sealed package and owns
the 44-leaf evidence-accounting manifest. Projection accepts only the thin
released input plus target mechanics. It may only `MAP`, `FORMAT`, `ENCODE`,
`REPEAT`, `PLACE`, `SERIALIZE`, and `VALIDATE`; it has no interpretation
authority and does not read audit metadata.

The G5.45 consumer-first audit route is opt-in and proof-only. The historical
legacy product route remains unchanged because product activation or authority
cutover was not authorized. Byte parity with that route is a control, not an
authorization to publish.

## Conditional scope

For the controlled Russian-source case, the Russian-source obligation is
`RESOLVED`, the foreign-source obligation is
`NOT_ACTIVATED_FOR_SUPPLIED_CASE`, no foreign mapping is emitted, and no
unrelated domain activates. A separately proven foreign-source component
activates only the foreign-source obligation and leaves the Russian obligation
not activated. This does not claim a complete foreign-income projection or
close treaty methodology.

## Fail-closed classifications

- `MODEL_GAP`: a required consumer value has no representation, producer,
  input path, or projection mapping. The supported controlled profile has zero.
- `MISSING_EVIDENCE`: the model exists but the supplied case lacks its required
  evidence. Missing residency is the mandatory adversarial example.
- `SOURCE_EVIDENCE_INSUFFICIENT`: normalized source observations do not support
  the calculation.
- `METHODOLOGY_UNRESOLVED`: facts can be represented but a reviewed executable
  rule remains absent.

## Proof terminals and scope stop

The controlled proof terminals are:

```text
DECLARATION_CONSUMER_MODEL_PROVEN
DECLARATION_SEMANTIC_MODEL_COMPLETE
END_TO_END_DECLARATION_ASSEMBLY_PROVEN
DECLARATION_VALUE_TRACEABILITY_PROVEN
CROSS_DOMAIN_DECLARATION_CONSISTENCY_PROVEN
```

The following legal-methodology gaps remain external and fail closed:

```text
ambiguous_security_disposal_source_classification
partial_acquisition_commission_allocation
non_rub_intermediate_precision_and_rounding
treaty_specific_foreign_tax_credit_limit
```

No product activation, real-case declaration release, commit, push, or PR is
authorized by this contract.
