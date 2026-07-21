# Broker Reports customer test debt v1

Status: authoritative release-isolation contract

Debt id: `SBER_BROKER_PDF_POSITIVE_HOLDOUT`

## Frozen implementation

- Profile id: `supported_broker_pdf_neutral_table_profile_v1`.
- Reconstruction version: `broker_pdf_ruled_grid_reconstruction_v1`.
- Validator version: `broker_pdf_neutral_table_validator_v1`.
- Profile source revision: `b2d4592`.
- Freeze baseline repository revision: `cf158fd38e3fc0a1f195b885ba94cb0094f95537`.
- Frozen bundle SHA-256 values: Gate 1 `08d6e9d7d3e9f8669365e4bfa6c99327ccd8496e09e5c2c04eef74fa0e39dabd`, Gate 2 source fact `b20fb77775d4e82d6f56130a4af81675a7405b4abf912803de4f04e5d001356e`, Gate 2 domain `3daec92cd22731d4e37de6aa8cc8237dc50425a249e6edb17ec0e916f54539cd`.

The profile rules are frozen while this debt is open. Unrelated blocker work
must not tune its selection, reconstruction or validation rules.

## Required customer input

One genuine, previously unseen PDF from the same intended PJSC Sberbank broker
report template family, supplied with acceptable provenance and authorization
for private validation. Copies of the tuning source, screenshots, crops,
synthetic/redrawn documents, other broker layouts and materially different Sber
document families do not satisfy the debt.

## Release isolation

The maintained runtime valve is
`broker_pdf_neutral_table_profile_v1_enabled`. Its default is `false`. It may be
enabled explicitly only for private actual-corpus proof, deterministic test
fixtures and the future positive-holdout procedure while this debt is open.
The core normalizer enforces those scopes through
`broker_reports_gate1.customer_debt_policy`; a true flag without an exact
maintained `proof_scope` terminates with
`sber_broker_profile_proof_scope_denied`.

Current statuses are distinct:

- Actual-corpus implementation: `IMPLEMENTED_ON_ACTUAL_CORPUS`.
- Template-family generalization: `AWAITING_CUSTOMER_POSITIVE_HOLDOUT`.
- Release activation: `RELEASE_GATED`.
- Customer acceptance: `NOT_RUN`.

Other accepted Broker Reports capabilities may be delivered independently and
must not claim that this profile has passed generalization or customer
acceptance.

## Future acceptance procedure

1. Preserve the frozen rules and record the received source provenance.
2. Run the maintained private path twice with the release valve explicitly
   enabled.
3. Prove byte- and structure-equivalent canonical output across both runs.
4. Compare source pages to canonical tables for headers, rows, columns, totals,
   annotations and continuations.
5. Reconcile source ownership and Gate 2 package accounting; require zero
   contradiction, zero silent loss and zero provider calls.
6. Rebuild affected bundles from unchanged profile sources, run regression and
   safe stage smoke, and prove exact repository/live SHA-256 equality.
7. Enable production release only after the proof is accepted and this debt is
   closed by a new versioned record.

The unavailable holdout is external customer acceptance debt. It is neither a
failed implementation nor permission to weaken the profile.
