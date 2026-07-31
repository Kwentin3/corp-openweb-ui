# Broker Reports Code Comment Policy v1

Status: normative comment policy

Effective date: 2026-07-31

## Authority priority

```text
architecture/domain context
-> sidecar owner metadata

versioned boundary rules
-> contracts

behavior verification
-> tests

local non-obvious code invariant
-> source comment, only when required
```

Owner/domain explanations belong in
`BROKER_REPORTS_OWNER_CONTEXT.v1.json`. Versioned boundary rules belong in
contracts and behavioral claims belong in executable tests. These authorities
must not be duplicated into hash-pinned production Python merely for
discoverability.

## Source comments allowed only when

- the explanation is necessary beside the algorithm;
- it explains a non-obvious local invariant;
- it does not duplicate owner metadata;
- it does not duplicate an ADR;
- it contains no changing list of financial types;
- it preserves source hashes and generated-bundle parity;
- a test or stable contract marker protects it.

An allowed local invariant comment should state the prevented authority bypass
or failure and point to its governing contract/test when that is not obvious.

## Source comments forbidden when

- their sole purpose is to describe a domain;
- they enumerate owners or consumers;
- they describe runtime status;
- they repeat routes from Route Status;
- they change hash-pinned source without changing behavior;
- their content can be represented in owner metadata;
- they narrate obvious code, temporary agent reasoning, or a GOAL number
  without a stable authority.

Historical containment is architecture context and therefore belongs in the
sidecar unless a genuinely local algorithmic invariant independently meets
every allowed-comment condition.

## Verification

`test_broker_reports_kt1_architecture_stabilization.py` verifies sidecar
coverage and consistency, executable containment, sole authorities, and the
absence of a new owner module. It deliberately does not require architecture
boundary comments in production source.
