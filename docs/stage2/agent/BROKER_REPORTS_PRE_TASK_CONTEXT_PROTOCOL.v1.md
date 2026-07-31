# Broker Reports Pre-Task Context Protocol v1

Status: mandatory agent protocol

Effective date: 2026-07-31

## Required context pass

Before changing Broker Reports code, contracts, tests, release scripts, or
architecture documents, the agent must:

1. Identify the domain being changed.
2. Read `BROKER_REPORTS_DOMAIN_MAP.v1.md`.
3. Read `BROKER_REPORTS_SOLE_OWNER_MATRIX.v1.md`.
4. Read `BROKER_REPORTS_GATE2_ROUTE_STATUS.v1.md`.
5. Read the relevant ADR.
6. Read the input contract.
7. Read the output contract.
8. Read the boundary comment in the owner module.
9. Read producer tests.
10. Read consumer tests.
11. Check the adjacent historical route.
12. Verify current runtime status from imports, guards, and consumers.
13. Check whether the change creates a new owner.
14. Check whether product reachability changes.

Repository truth is mandatory. Reports and prior agent memory may identify
where to look, but cannot establish current reachability or ownership.

## Context header required before code

The working plan or PR body must contain this completed header before code
changes:

```text
Domain being changed:
Sole owner:
Input contract:
Output contract:
Allowed responsibility:
Forbidden responsibility:
Active consumers:
Historical routes nearby:
Product behavior expected to change:
Runtime behavior expected to change:
OpenWebUI impact:
```

The header is limited to current facts and the proposed slice. Do not create a
separate bootstrap report.

## Required PR disclosure

The PR must state:

- context documents actually read;
- boundary comments checked;
- contracts changed or confirmed unchanged;
- producer and consumer tests checked;
- historical routes found;
- whether a new owner was introduced;
- whether product, runtime, provider, OpenWebUI core, valve, admission, or live
  reachability changed.

## Fail-closed rules

Stop implementation and obtain a new architecture decision if:

- two modules claim the same maintained write responsibility;
- the proposed consumer is not listed by the owner boundary;
- a historical/proof route would gain product reachability;
- a provider would receive a field forbidden by the domain map;
- the change needs a new Pipe, valve, factory, canonical materializer, store
  bypass, or production admission not explicitly authorized;
- the relevant live state cannot be distinguished from repository state.

Documentation-only clarification may continue while runtime work is stopped,
provided it does not claim unverified activation or parity.
