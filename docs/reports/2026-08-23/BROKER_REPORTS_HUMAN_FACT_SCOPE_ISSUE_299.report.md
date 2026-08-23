# Broker Reports Human Fact Scope — Issue #299, corrected by #301

Date: 2026-08-23

Current terminal: `HUMAN_FACT_TAXPAYER_SCOPE_BLOCKER_PROVEN`

The former `AUTHENTICATED_HUMAN_FACT_BOUNDARY_PROVEN` conclusion is withdrawn.
Independent review #301 showed that the case-derived taxpayer hash did not
prove an independent taxpayer identity or a trusted case-to-taxpayer binding.
PR #300 remains open and Issue #299 must remain open for re-review.

## Dependency and reviewed baseline

- PR #298 reviewed head: `1cb90929950872aa34936aa3be2cb08e273e72ca`.
- PR #298 was merged normally.
- Issue #299 starting `main`: `89260b9b26c0b82400428380cd855b5ea16894fd`.
- PR #300 independently reviewed head: `6f7bb87f7fda16ca800bcc956c422da5638689fb`.
- Remaining-lane review baseline: `5ecbccca17a5ffa5badc4ed812db3595d0bf85bb`.

## #301 baseline experiments

All experiments used real owner-produced artifacts in the existing store.

| Experiment on reviewed head | Actual result | Defect |
| --- | --- | --- |
| genuine yes alone after yes+no exist | accepted | caller can select yes by omission |
| genuine no alone after yes+no exist | accepted | caller can select no by omission |
| A request -> B request -> A content again | final A stale, B current | creation time/ref acted as authority |
| filing `INITIAL, ИФНС 2367` as free text | accepted Human fact | external authority smuggled into allowed fact |
| inspect taxpayer helper inputs | only owner label + `case_id` | obfuscated case, not independent taxpayer binding |

## Corrected owner-local semantics

`Gate5HumanGapClosureRuntimeFactory.create` remains the only Human owner.

1. Request content is still content-addressed, while a minimal immutable
   predecessor-chain publication artifact owns which request is current.
2. `A -> A` is byte-stable; `A -> B -> A` makes final A current without using
   timestamps, insertion order or ref sorting.
3. Any unresolved owner-visible conflicting facts for one exact request
   publication make every candidate fail closed, even when supplied alone.
4. Filing is the closed `INITIAL | CORRECTION` election. Destination/inspection
   remains a separate `EXTERNAL_AUTHORITY` gap.
5. The false case-derived taxpayer helper is removed. Product composition fails
   closed until a trusted upstream binding exists.

No workflow/event engine, registry, generic identity/evidence framework,
receipt engine, semantic text filter, LLM/provider path or second authority was
added.

The remaining review found that the predecessor chain was correct only after a
lane had been selected: mutable `kind` split `DEFERRED <-> REQUIRED`, while two
different `fact_key=None` source gaps could collide. The corrected lane is
exactly `sha256({scope_binding_sha256, semantic_request_key})`. Human owns the
key: `human_fact:<fact_key>` for USER_FACT, a hash of the source owner's stable
`reason_code + asset + currency` grouping for source gaps, and closed fixed
keys for the three other request families. Request state, wording, evidence,
routing, order and timestamps cannot choose or fork identity. `publish_requests`
also verifies every request after publishing the complete plan, so it never
returns an already-stale member.

## Corrected adversarial matrix

| Experiment | Corrected result |
| --- | --- |
| yes alone after yes+no | `gate5_user_case_fact_conflict` |
| no alone after yes+no | `gate5_user_case_fact_conflict` |
| `[yes,no]`, `[no,yes]` | conflict; no order-dependent winner |
| repeat byte-equal answer | same artifact/result; no false new conflict |
| A -> A | current publication reused |
| A -> B -> A | final A accepted; B stale |
| old fact from first A or B after final A | `gate5_gap_request_stale` |
| same semantic publication in later run | accepted/reused |
| budget `DEFERRED -> REQUIRED` | one lane; old deferred request and fact stale; required current |
| budget `REQUIRED -> DEFERRED` in another run | one lane; old required request and fact stale; deferred current |
| two concurrent owner-distinct `fact_key=None` gaps | two lanes; both requests returned current |
| wording/evidence change for one source gap | same lane; old publication stale; other gap remains current |
| foreign user/case/workspace/period | rejected by owner/store binding |
| two synthetic taxpayer refs in one user/case | independently represented; cross-use rejected |
| filing `INITIAL` / `CORRECTION` | accepted closed code |
| filing plus inspection, KBK, OKTMO, residency, source, deduction or settlement text/code | rejected |
| Human answer to destination External Authority request | `gate5_gap_answer_not_user_fact` |
| Declaration Preparation with filing election | readiness only; value not projected/reinterpreted; destination gap remains |
| current product path without trusted taxpayer binding | `ndfl_trusted_taxpayer_scope_binding_required` |

## Taxpayer owner decision

No repository contract proves exactly one taxpayer per case. The existing
operation/category `user_verified_fact` binding relates one operation subject
to a supplied taxpayer ref but does not authenticate that taxpayer ref to the
current user/case. It is not a substitute owner.

The smallest missing upstream contract is an authenticated, owner-produced and
owner-verifiable case-to-taxpayer binding with explicit origin and support for
multiple taxpayer scopes per case. User, taxpayer, signer and representative
remain separate identities. Human may consume this future binding but must not
mint or infer it.

## Scope stop

The corrected conflict, current-request and filing behavior is covered by
adversarial tests. The remaining taxpayer-origin blocker prevents the positive
Issue #299 terminal and production activation. Exact new PR head and required
CI receipt are published in PR #300 and Issue #301 after the commit is pushed.
