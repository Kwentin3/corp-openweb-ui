# Broker Reports Human Fact Scope — Issue #299

Date: 2026-08-23

Terminal: `AUTHENTICATED_HUMAN_FACT_BOUNDARY_PROVEN`

## Dependency and start point

- Reviewed PR #298 head: `1cb90929950872aa34936aa3be2cb08e273e72ca`.
- Before merge it was open, non-draft, mergeable, and its required
  `broker-reports-ci` check was green on that exact head.
- PR #298 was merged through the normal GitHub merge path.
- Resulting `origin/main` merge commit and exact Issue #299 starting main:
  `89260b9b26c0b82400428380cd855b5ea16894fd`.
- `git merge-base --is-ancestor
  1cb90929950872aa34936aa3be2cb08e273e72ca origin/main` returned success.
- Issue #297 was closed with this merge evidence before Issue #299 code work.

## Baseline defect and attribution

The public Human Adapter owner was exercised before the change with a real
owner-produced v0 fact. `validate_user_case_facts` accepted it because the v0
shape had no user, case, taxpayer, tax-period, request, or owner-store binding.
The observed result was `accepted_by_validator: True`; the expected result for
foreign replay was rejection. The defect therefore belonged to the Human
Adapter publication/validation boundary, not to Declaration Preparation,
residency, source evidence, external evidence, or a downstream assembler.

## Minimal owner-local change

`Gate5HumanGapClosureRuntimeFactory.create` remains the sole owner of request
meaning, answer normalization, typed Human fact publication, and validation.
It now:

1. builds v1 requests with an immutable user/case/taxpayer/period scope;
2. publishes the exact owner-built request as a private artifact in the
   existing `ArtifactStorePort`;
3. resolves that request before normalizing an authenticated answer;
4. publishes the resulting exact v1 typed fact through the same store;
5. resolves both fact and request under the consuming authenticated context;
6. rejects foreign, changed, stale, missing, duplicate, conflicting, or v0
   evidence before Declaration Preparation consumes it.

`ArtifactResolver.resolve_case` is the only new shared seam. It reuses the
existing store's user/case/workspace/lifecycle checks while intentionally
allowing a later normalization run in the same case. It does not interpret a
Human fact. `Gate5DeclarationPreparationRuntimeFactory.create` remains a
consumer/composition owner and does not rebuild or repair requests or facts.
No second fact owner, identity authority, registry, workflow, receipt engine,
provider call, or LLM path was added.

The current contract is
`BROKER_REPORTS_GATE5_HUMAN_FACT_SCOPE.v1.md`. The preparation contract's v0
Human fact route is marked historical. V0 remains historical-readable evidence
only and is rejected on the v1 boundary; no silent migration occurs.

## Scope and replay decision

The immutable semantic scope is:

```text
authenticated_user_ref + case_id + taxpayer_scope_ref + tax_period
```

It is also bound to the exact current originating request. Thus the effective
lifetime is one authenticated case, taxpayer slot, tax period, and request
version. A new execution run may replay the fact. A superseding owner request
for the same key invalidates the old request/fact relation.

`normalization_run_id` is not semantic fact scope. `workspace_model_id` is not
serialized as fact meaning either, but remains an ArtifactStore ACL boundary;
cross-workspace access fails. This allows legitimate same-case reruns without
turning a workspace choice into taxpayer meaning.

The bounded product composition asks the Human owner for an opaque case-local
taxpayer slot. It differs from `user_id`, `case_id`, and any operation subject.
The Human owner recomputes this slot and rejects any caller-supplied mismatch;
the string is therefore not caller-authoritative. It is only a scope handle
and does not prove taxpayer identity. The Human fact
may confirm a fixture circumstance or election, but does not become tax,
source, legal, residency-status, or external-authority evidence.

## A/B adjacency and negative matrix

All positive requests and facts below are genuine outputs persisted by the
existing owners. Resealed attacks recomputed every caller-accessible canonical
hash/ref and then invoked the actual owner validator.

| Experiment | Expected | Actual |
| --- | --- | --- |
| Context/scope A -> exact request A -> fixture answer A -> fact A -> validator A | accept deterministically | accepted; repeated normalization produced byte-equal fact |
| Context/scope B -> exact request B -> fixture answer B -> fact B -> validator B | accept deterministically | accepted |
| Fact A under foreign authenticated user B | reject | `gate5_user_case_fact_owner_binding_invalid` |
| Fact A under foreign case B | reject | `gate5_human_fact_scope_invalid` |
| Fact A under foreign workspace B | reject | `gate5_user_case_fact_owner_binding_invalid` |
| Fact A under foreign taxpayer slot B | reject | `gate5_human_fact_scope_invalid` |
| Fact A under foreign tax period 2024 | reject | `gate5_user_case_fact_owner_binding_invalid` |
| Fact A under later run B, all semantic scope unchanged | accept | accepted |
| Changed request A, fully resealed by caller | reject | `gate5_gap_request_owner_binding_invalid` |
| Old request A after owner publishes a changed request for the same key/scope | reject | `gate5_gap_request_stale` |
| Answer attempts to replace request fact key | reject | `gate5_gap_answer_invalid` |
| Genuine fact A rewritten to genuine request/scope B and fully resealed | reject | `gate5_user_case_fact_owner_binding_invalid` because no matching owner fact artifact exists |
| Equal duplicate facts for one key | reject | `gate5_user_case_fact_duplicate` |
| Conflicting true/false facts for one key, either order | reject | `gate5_user_case_fact_duplicate` |
| Missing scope binding | reject | `gate5_user_case_facts_invalid` |
| Legacy v0 fact | reject | `gate5_user_case_facts_invalid` |
| Direct residency/tax-status code supplied as a Human answer | reject | `gate5_gap_answer_kind_invalid` |
| Additional-document answer | route to normalization, publish no Human fact | `NORMALIZATION_REQUIRED`, fact `null` |
| External-authority answer supplied by Human | reject | `gate5_gap_answer_not_user_fact` |
| Runtime provider/LLM path | zero | metric `provider_calls: 0`; import guard green |

The same owner publication/normalization proof covers all five facts currently
emitted by the Human Adapter:

- `taxpayer_identity_confirmed`;
- `filing_instance_identity`;
- `signer_and_representation`;
- `budget_disposition`;
- `residency_evidence`.

No structured variant was invented because this issue authorizes no newly
activated typed downstream consumer. Residency remains raw presence/absence
evidence and is interpreted by its existing residency owner.

## Manual synthetic visual receipt

Only synthetic, non-private fixture data was inspected. The compact view below
is audit evidence in this report, not a new runtime receipt contract.

| Persona | Declared fixture | Request | Published fact | Scope | Validation / next owner |
| --- | --- | --- | --- | --- | --- |
| A | confirmation `true`, taxpayer `taxpayer_case_3c47700e2f04d689bd14ddb7a999f3da`, period 2025 | `g5request_3b5ecc9ac67e4c45aeb29fccba285fee`; `art_8244bd8342b87974d26e9f90d31bc27c` | `art_b3dc50cc33c6e32bbf23ebd730504971` | user `synthetic-user-a`; case `synthetic-case-a`; scope hash `ef5f23d460022d57a37196b915c01bdb6b2c733c58d5b8aaae7feec2e905b75b` | accepted; `Gate5DeclarationPreparationRuntimeFactory.create` |
| B | confirmation `true`, taxpayer `taxpayer_case_0020fcc1ce4403170d17b22babb3de86`, period 2025 | `g5request_d9fad2bf01c5c53ba64ee6926c24031c`; `art_1a6d2bdbaa5b70a11acdbc571c4cc56f` | `art_64d15ecf07acc8314634f36240fc6dda` | user `synthetic-user-b`; case `synthetic-case-b`; scope hash `11392817ed68cce088e6dc8bc2e4b2d772f7c34ecbf478352e09a9964243cb4d` | accepted; `Gate5DeclarationPreparationRuntimeFactory.create` |

The request identity embedded in each fact matched the displayed owner request,
the normalized value matched the declared fixture, and both owner validations
matched the expected outcomes. No discrepancy was observed. This proves only
contract mechanics, not real-human UX, consent, legal adequacy, or production
readiness.

## Uncomfortable questions

1. **Lifetime?** Case + taxpayer slot + tax period + current originating
   request version; not one execution run.
2. **Over-bound to run/workspace?** No. Run is excluded and cross-run replay is
   positive-tested. Workspace is ACL only and foreign workspace fails closed.
3. **Can user, taxpayer, signer, representative differ?** Yes. Authentication
   owns user context; the Human owner holds only an independent taxpayer scope
   handle; signer/representation remains an explicit Human election. This
   contract does not claim structured entity identity or equivalence.
4. **Is confirmation text treated as structured identity?** No. Existing coarse
   confirmation remains a boolean fact. It is not promoted into name, tax ID,
   signer, representative, or taxpayer identity data.
5. **Can a foreign valid artifact pass after resealing?** No. Caller hashes
   prove bytes only; acceptance additionally requires exact request and fact
   artifacts resolvable from the owner store under the consumer context.
6. **Is synthetic agent-as-human evidence real user evidence?** No. It is
   labelled synthetic and proves only mechanics.
7. **Did Human acquire tax/source/external authority?** No. Direct conclusions
   fail; documents route to normalization; external and methodology gaps remain
   with their owners.
8. **Can v0 sneak through?** No. V1 has a closed schema and v0 is rejected.
9. **Did composition acquire business meaning?** No. It passes trusted context,
   period, and an opaque Human-owner taxpayer slot; request/fact meaning and
   validation remain in the Human owner.
10. **Smallest safe next issue?** Independently review this inactive v1 seam,
    then identify one already authorized typed consumer before replacing any
    coarse confirmation with a minimal structured identity/representation
    fact. Do not activate Declaration/XML or build a generic identity system.

## Verification and scope stop

Local focused evidence before PR publication:

```text
combined Human/preparation/consumer/architecture/bundle/current-pipeline/
ordinary-trade affected regression selection
=> 213 passed, 5 dependency deprecation warnings in 97.30s

rebuild all three maintained Function bundles and compare SHA-256 before/after
=> bundle_determinism=PASS

python -m ruff check --no-cache --select E9,F63,F7,F82 <changed Python files>
=> All checks passed
```

The maintained Function bundles were rebuilt from their canonical sources.
The new Human scope and preparation suites were added to the existing required
Broker Reports CI job so the exact-head receipt exercises the new boundary.
Declaration assembly, XML, settlement, source-party, external-authority, UI,
and provider paths remain outside this issue.
