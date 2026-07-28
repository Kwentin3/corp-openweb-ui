# Broker Reports Atomic Stage Release v1

Status: `MAINTAINED_RELEASE_CONTRACT`

## Scope

This contract releases the accepted Broker Reports candidate to the single
qualified stage OpenWebUI instance. It reuses the pinned server-authoritative
private-intake image and aligns the three maintained Broker Reports Functions,
the declared already-existing managed Prompt rows and the static loader while
OpenWebUI is stopped. The protected private-intake Action, image and runtime
dependencies are immutable release inputs and must pass their exact contracted
readback before and after the release transaction. Before mutation, declared
Prompt rows must exist and the current loader must be a valid guarded file;
they are allowed to differ from the candidate being applied.

The release does not deploy a new OpenWebUI image when the accepted pinned image
already satisfies the runtime dependency and private-intake contracts.

## Atomic boundary

The release unit contains:

- three Function records:
  `broker_reports_gate1_pipe`,
  `broker_reports_gate2_source_fact_pipe`, and
  `broker_reports_gate2_domain_source_fact_pipe`;
- every managed Prompt row declared by the exact release manifest;
- the pinned static loader file.

Before mutation, the release driver requires a clean repository at the declared
40-character Git revision, exact pinned image/Action/runtime parity, the exact
declared Prompt ID set, a readable current loader with a SHA-256 identity, and
zero non-terminal Broker Reports workloads or owned workload temp entries. It
does not require current Prompt content or loader bytes to equal the candidate.

The schema-v3 driver then:

1. stages only the manifest, three bundles, loader and remote release program
   in a restricted temporary directory;
2. records all release-mutated fields of the declared Function and managed
   Prompt rows exactly, plus loader bytes, in a mode-0600 private rollback
   artifact;
3. stops OpenWebUI;
4. replaces the loader under an exact before-hash guard;
5. updates all Function and declared Prompt rows in one `BEGIN IMMEDIATE`
   SQLite transaction;
6. starts OpenWebUI and waits for internal health, the auth API and external
   ingress;
7. verifies the contracted candidate projection: Function code hashes and
   selected state/release/valve fields, Prompt command/version/active/content
   hash plus declared metadata keys, and loader hash;
8. removes the staging directory.

No request can observe a partially committed Function/Prompt set or loader
transition because OpenWebUI is stopped while the separate guarded loader
replacement and SQLite transaction run. The Function/Prompt row set commits in
one database transaction.

Automatic failure restoration is not universal today. Once the driver sets its
`modified` marker, a failure restores all snapshotted release-mutated
Function/Prompt fields and the previous loader before restarting. There is an
explicit uncovered window if atomic loader replacement succeeds but
`_replace_loader` raises before the caller sets `modified=true`; that branch can
restart without restoring the previous loader. This release contour must not
be described as fail-safe for every post-write failure until that window is
fixed and tested.

## Rollback proof

Terminal release uses `--apply --prove-rollback`. After the first candidate
start and readback, the tool restores all snapshotted release-mutated fields of
the declared Function and Prompt rows plus the loader, proves those snapshots
and health, then reapplies and re-verifies the candidate. The private rollback
artifact remains available by release identity; only its SHA-256 identity may
enter the safe receipt.

The rollback artifact contains snapshots of all release-mutated Function
fields, snapshots of the Prompt fields mutated by the release (`command`,
`version_id`, `is_active`, `content`, `meta`, and `updated_at`) and the loader
bytes. It is private release evidence and must never enter Git. It must not
contain customer sources, ArtifactStore payloads, credentials, a database
backup or environment filesystem paths.

## Managed semantic asset scope gap

This release contour currently owns Functions, already-existing managed Prompt
rows and the loader only. It does not create, publish, activate, retire or
restore OpenWebUI Skill or Tool records, and it does not publish a Financial
Semantic Pack family. Direct Prompt-row replacement also does not create native
OpenWebUI Prompt history.

Candidate readback is also a contracted safe projection, not equality over
every mutated row field. It does not independently compare Function
`updated_at` or undeclared `meta`/`valves`, nor Prompt `updated_at` or
undeclared `meta` keys after candidate application. Rollback rehearsal does
compare the exact stored snapshots of all fields that this release mutates.

The Managed Semantic Decision Context program must extend this existing
manifest/snapshot/readback/rollback contour for the complete managed financial
asset family and close the documented failure/readback gaps. It must not create
a parallel release engine or GUI framework. Until Skill, Tool, Pack and catalog
publication plus rollback are implemented and proven, the repository-managed
financial asset family remains non-active.

## Release valves

The Goal 5-qualified semantic numeric-table route is enabled as one boundary:

- `pdf_table_intake_enabled=true`;
- `pdf_dual_vlm_enabled=true`;
- `pdf_semantic_visual_table_downstream_enabled=true`;
- `allow_standalone_semantic_visual_projections=true` in Gate 2 domain;
- migration policy and accepted profile identities are pinned in valves;
- OpenAI invocation, all shadow visual paths and their allowlists remain disabled.

Provider/model identities and bounded page, crop, candidate, token and output
limits prevent expansion beyond the accepted numeric profile. Provider
consensus cannot publish a semantic table. Legacy geometric promotion continues
to require its review receipt and seal and is not selected by the new default.

All three Functions receive the same persisted workload-authority configuration.
Gate 1 heavy concurrency remains one and Gate 2 local concurrency remains at
most two.

## Required readback

Terminal verification currently proves:

- exact Function content hashes, active/global/type state, release Git revision
  and manifest hash, and the declared release-valve projection;
- exact protected Action and loader content hashes;
- exact managed-Prompt command, selected version, active state, content hash and
  declared metadata-key projection;
- exact pinned image tag, image ID, image source revision and private-intake
  contract label;
- required runtime dependency version;
- zero non-terminal workloads, owned workload temp entries and release staging
  directories;
- matching rollback artifact identity;
- exact rollback-rehearsal equality for the snapshotted release-mutated
  Function/Prompt fields and previous loader identity;
- safe private-intake smoke with zero Knowledge, RAG and vector deltas;
- unchanged repository sink counters across the release transaction.

It does not prove full-row candidate equality for undeclared metadata/valves or
`updated_at`, and it does not close the pre-`modified` loader failure window
described above.

Customer-bearing data, raw provider responses, credentials, Function owner IDs,
private paths and rollback content are forbidden in Git and safe receipts.
