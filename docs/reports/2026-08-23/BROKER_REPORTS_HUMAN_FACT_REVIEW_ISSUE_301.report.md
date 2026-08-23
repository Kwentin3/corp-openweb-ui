# Broker Reports Human Fact Boundary Review — Issue #301

Date: 2026-08-23

Reviewed PR #300 head: `6f7bb87f7fda16ca800bcc956c422da5638689fb`

Terminal: `HUMAN_FACT_TAXPAYER_SCOPE_BLOCKER_PROVEN`

## Result

Three independently reproduced defects are closed through the existing Human
owner and store seams:

- every genuine fact in an unresolved same-request conflict now fails closed;
- explicit owner publication, not time/ref order, owns current request;
- filing is a closed initial/correction election and destination remains an
  External Authority gap.

The taxpayer investigation disproved the claimed positive boundary. No trusted
one-taxpayer-per-case invariant or authenticated case-to-taxpayer binding owner
exists in the repository. The case hash was removed and the product composition
fails closed rather than inventing the relation.

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
