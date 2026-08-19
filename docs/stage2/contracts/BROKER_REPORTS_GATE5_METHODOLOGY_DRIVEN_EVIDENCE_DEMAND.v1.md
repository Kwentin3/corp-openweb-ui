# Broker Reports Gate 5 Methodology-Driven Evidence Demand v1

Status: `SUPERSEDED SUPPORTING EVIDENCE`

Classification: `HISTORICAL_ONLY — NOT CURRENT ARCHITECTURE AUTHORITY`

Goal: `G5.46`

G5.46 proved that active methodology consumers can produce explicit Evidence
Demand rows and that existing normalized facts must be checked first. Its
former Gate 5 Canonical-reader/provider path is not current authority: G5.48
found that path crossed the Gate 3 source-semantics boundary.

Current routing is owned by
[Existing Pipeline Reconnection v1](./BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION.v1.md).
An Evidence Demand is a request describing required fact meaning, scope,
cardinality and roles. It does not authorize Gate 5 to read Canonical, choose a
chunk/table strategy, call a provider or materialize a source fact.

The historical G5.46 report and safe evidence remain reproducibility evidence;
their `CANONICAL_FACT_RECOVERY_PROVEN` terminal is superseded and must not be
read as a current runtime authorization.
