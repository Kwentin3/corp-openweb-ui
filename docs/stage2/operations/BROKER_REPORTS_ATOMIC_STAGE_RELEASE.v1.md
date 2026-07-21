# Broker Reports Atomic Stage Release v1

Status: `MAINTAINED_RELEASE_CONTRACT`

## Scope

This contract releases the accepted Broker Reports candidate to the single
qualified stage OpenWebUI instance. It reuses the pinned server-authoritative
private-intake image and atomically aligns the three maintained Broker Reports
Functions. The protected private-intake Action, managed prompts, static loader,
image and runtime dependencies are immutable release inputs and must pass exact
readback before and after the Function transaction.

The release does not deploy a new OpenWebUI image when the accepted pinned image
already satisfies the runtime dependency and private-intake contracts.

## Atomic boundary

The three Function records are one release unit:

- `broker_reports_gate1_pipe`;
- `broker_reports_gate2_source_fact_pipe`;
- `broker_reports_gate2_domain_source_fact_pipe`.

Before mutation, the release driver requires a clean repository at the declared
40-character Git revision, exact pinned image/Action/prompt/loader parity, and
zero non-terminal Broker Reports workloads or owned workload temp entries.

The driver then:

1. stages only the manifest, three bundles and the remote release program in a
   restricted temporary directory;
2. records the exact previous Function rows in a mode-0600 private rollback
   artifact;
3. stops OpenWebUI;
4. updates all three Function rows in one `BEGIN IMMEDIATE` SQLite transaction;
5. starts OpenWebUI and waits for internal health, the auth API and external
   ingress;
6. verifies exact content hashes, release metadata and release valves;
7. removes the staging directory.

No request can observe a partially committed Function set: OpenWebUI is stopped
while SQLite commits all three rows together. Any post-write failure stops the
container, restores every previous Function row, starts the previous runtime and
waits for the same health envelope before returning an error.

## Rollback proof

Terminal release uses `--apply --prove-rollback`. After the first candidate
start and readback, the tool restores the exact previous Function rows, proves
their hashes and health, then reapplies and re-verifies the candidate. The
private rollback artifact remains available by release identity; only its
SHA-256 identity may enter the safe receipt.

The rollback artifact contains Function code, metadata and valves only. It must
not contain customer sources, ArtifactStore payloads, credentials, prompt
content, database backups or private paths.

## Release valves

Visual VLM remains default-off:

- `pdf_table_intake_enabled=false`;
- `pdf_dual_vlm_enabled=false`;
- all shadow visual paths disabled and allowlists empty.

Provider/model identities and bounded page, crop, candidate, token and output
limits remain configured so a later explicit release decision can enable only
the already accepted review-assisted contour. Provider consensus cannot publish
a canonical visual table. The review receipt, seal and Gate 2 handoff contracts
remain mandatory, and automatic visual publication remains disabled.

All three Functions receive the same persisted workload-authority configuration.
Gate 1 heavy concurrency remains one and Gate 2 local concurrency remains at
most two.

## Required readback

Terminal verification must prove:

- exact release Git revision and manifest hash in all three Function records;
- exact Function, protected Action, loader and managed-prompt hashes;
- exact pinned image tag, image ID, image source revision and private-intake
  contract label;
- exact provider-policy and model IDs;
- exact release valve projection;
- required runtime dependency version;
- zero non-terminal workloads, owned workload temp entries and release staging
  directories;
- matching rollback artifact identity;
- safe private-intake smoke with zero Knowledge, RAG and vector deltas;
- unchanged repository sink counters across the release transaction.

Customer-bearing data, raw provider responses, credentials, Function owner IDs,
private paths and rollback content are forbidden in Git and safe receipts.
