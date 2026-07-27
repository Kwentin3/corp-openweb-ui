# Broker Reports Gate 2 Financial Candidate Compiler v1

Status: Goal 3 contract for Candidate Records By Construction.

## Boundary

`Gate2FinancialCandidateCompilerFactory.create` is the only entrypoint from one
validated Evidence Bundle to zero or more fully materializable Typed Options.
The compiler consumes the exact Semantic Pack projected through the Registry.
It does not infer a financial type or ask a provider to create bindings.

The compiler may use only:

- Pack role IDs, value types, cardinalities, and source-family compatibility;
- code-owned source association identities;
- technical `column_meaning` selectors supplied by the source projection;
- the terminal selector segment of a code-owned deterministic-reference ID;
- structural ambiguity and canonical Typed Option validation.

Source literals and visible labels are retained in the private Evidence Bundle
but are not read by the compiler.

## Deterministic construction

Compilation is performed independently for each authoritative
`association_ref` and each compatible Pack type. This permits distinct complete
source records to produce distinct option IDs without mixing their values.

For each required role:

1. candidates are restricted to the exact Pack `value_type`;
2. one candidate is selected directly when it is unique;
3. when several candidates exist, the compiler compares the role ID with only
   the code-owned technical selector, using one generic identifier-token rule;
4. a unique positive structural match is required;
5. a tie, missing candidate, or reused required ref blocks that Typed Option.

Optional bindings never rescue a required binding. Ambiguous optional values
remain unbound. Every proposed complete binding must pass the canonical Typed
Option factory, including its Pack/Registry check, structural receipt,
decision-validator proof, and real materializer proof.

## Ambiguity

Candidates with the same association, value type, role feasibility, and no
unique technical selector are structurally equivalent. The compiler emits no
Typed Option for that binding. It does not select by order, literal equality,
visible wording, expected outcome, or post-response repair.

Consequently, the sealed `adjacent_equal` case keeps its Evidence Bundle and
unclassified retention path, while its typed-option set is empty.

## Output

`broker_reports_gate2_financial_candidate_compilation_v1` records:

- the exact Bundle and Semantic Pack identities;
- sorted, unique, materializable Typed Options;
- deterministic blocked-binding records;
- one integrity hash over the private compilation payload.

Its safe summary contains counts and hashes only. Provider calls are zero.

## Prohibitions

- no source-literal or visible-label inspection;
- no financial dictionary, regex, or concrete type-ID predicate;
- no benchmark expected-answer lookup;
- no model-generated role or source ref;
- no repair, fallback, or canonical validator/materializer bypass.
