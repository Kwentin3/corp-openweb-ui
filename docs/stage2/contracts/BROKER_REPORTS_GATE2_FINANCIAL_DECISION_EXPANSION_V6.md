# Broker Reports Gate 2 Financial Decision Expansion V6

Status: Goal 6 contract for Candidate Records By Construction.

## Boundary

`Gate2FinancialSemanticV6DecisionExpansionFactory.create` is the only boundary
from a minimal provider choice to a validated canonical Gate 2 decision.
Before expansion it revalidates the exact Choice Contract, packet, Candidate
Compilation, Evidence Bundle, source package, Pack, and Registry.

The shared
`Gate2FinancialSemanticV6CanonicalDecisionContractFactory.create` is the only
V6 adapter from Bundle values and Pack role schemas to the existing canonical
four-disposition decision contract.

## Typed expansion

For `typed_input`, the provider supplies only an opaque `typed_option_id`.
Expansion requires exactly one matching code-owned Typed Option and copies:

- its exact type ID;
- its exact required and optional role set;
- its exact prebound source refs;
- the canonical `typed_supported` reason.

The resulting object is validated by the existing canonical decision factory.
An unknown, duplicated, unavailable, or tampered option ID fails closed.

## Unclassified expansion

For `unclassified_financial_input`, the provider supplies only a bounded
reason code. Expansion constructs all retention bindings from the code-owned
Bundle retention set and the generic Pack role compatibility map.

Every Bundle source value must occur exactly once in the validated canonical
unclassified decision. The model cannot add, remove, reorder, or choose
retained source refs.

## Strict input handling

- JSON size is bounded;
- duplicate JSON object keys are rejected;
- variant fields are exact closed sets;
- technical dispositions are rejected;
- free-form reasons are rejected;
- provider-created type IDs, refs, and bindings are impossible.

## No repair

Canonical validation failure, unknown option, or malformed typed output is a
terminal rejection. There is no typed-to-unclassified conversion, fallback,
retry, or post-response repair.
