# Broker Reports Human Fact Boundary Review — Issue #301

Date: 2026-08-23

Initial reviewed PR #300 head: `6f7bb87f7fda16ca800bcc956c422da5638689fb`

Remaining-lane review baseline: `5ecbccca17a5ffa5badc4ed812db3595d0bf85bb`

Terminal: `HUMAN_FACT_TAXPAYER_SCOPE_BLOCKER_PROVEN`

## Result

The original three defects and the subsequently reproduced request-lane defect
are closed through the existing Human owner and store seams:

- every genuine fact in an unresolved same-request conflict now fails closed;
- explicit owner publication, not time/ref order, owns current request;
- filing is a closed initial/correction election and destination remains an
  External Authority gap.
- mutable request state no longer splits one meaning or merges two concurrent
  owner-distinct source gaps.

The taxpayer investigation disproved the claimed positive boundary. No trusted
one-taxpayer-per-case invariant or authenticated case-to-taxpayer binding owner
exists in the repository. The case hash was removed and the product composition
fails closed rather than inventing the relation.

## Remaining-lane experiments and correction

All baseline experiments used genuine owner-produced requests and facts. On
`5ecbccca17a5ffa5badc4ed812db3595d0bf85bb`, a budget request changed
`DEFERRED -> REQUIRED` into another lane: the old deferred request still
normalized and its old fact still validated. The reverse transition in another
execution run behaved the same way. Separately, two simultaneously published
internal source requests with `fact_key=None` and otherwise colliding lane
fields caused the first request returned by that same `publish_requests` call
to be stale already.

The minimum owner-owned identity is now:

```text
request_lane_sha256 = sha256({scope_binding_sha256, semantic_request_key})
```

USER_FACT uses `human_fact:<fact_key>`. A source gap uses a digest of the
source-review owner's pre-existing stable grouping meaning:
`reason_code + asset + currency`. Fixed owner keys cover withholding advisory,
filing destination and the income-source methodology decision. Kind, priority,
wording, evidence state, routing, closure type, demands, display subject,
timestamps and ordering do not participate. The caller cannot mint a working
replacement key because current publication resolves owner-produced request
bytes from the store. `publish_requests` performs a final current-tip check for
every returned request.

| Matrix | Correct result |
| --- | --- |
| `DEFERRED -> REQUIRED` | same key/lane; deferred request and fact stale; required current |
| `REQUIRED -> DEFERRED`, later run | same key/lane; required request and fact stale; deferred current |
| multiple concurrent `fact_key=None` | owner-distinct keys/lanes; every returned request current |
| display/evidence change | same meaning supersedes its lane; unrelated concurrent meaning remains current |
| `A -> B -> A` | three publications; final A current; prior A and B stale |

## Minimal adjacency proof

```text
owner request content
-> owner predecessor-chain publication
-> exact publication-bound fact
-> owner-visible conflict scan
-> exact scope/request/fact validation
```

Existing owners remain unchanged: ArtifactStore owns persistence and ACL;
Human owns requests/answers/facts; Residency owns interval interpretation;
External Authority owns destination; Declaration Preparation consumes validated
readiness only. No new general-purpose subsystem was added.

## Verification receipt

Focused test and CI commands/results, exact new head and GitHub run URL are
reported on Issue #301 and PR #300 after publication. This report deliberately
does not self-embed the commit SHA that contains itself.
