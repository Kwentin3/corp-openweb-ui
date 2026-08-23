# Broker Reports ordinary-trade declaration MVP contract v1

Status: active, deliberately bounded production path.

## Boundary

`OrdinaryTradeProductionRuntimeFactory.create` is the only activation and
composition root. It may construct `OrdinaryTradeDeclarationMvpRuntime` only
when all three current owners are injected: authenticated case/taxpayer
identity, authenticated user declaration facts, and external-authority case
facts. A partial owner set is invalid. Without the owner set, the established
source-fact-only production behavior remains unchanged and fail-closed.

The adapter coordinates existing owners; it does not calculate tax or assemble
XML. Fact v2, source consumption, Operation, Category, Tax Base, right-side
components, Scope, Package, semantic release, and target projection retain
their existing owners.

## Stable identities and owners

| Meaning | Owner | Consumer proof |
| --- | --- | --- |
| authenticated user/case/taxpayer | injected identity provider -> `AuthenticatedCaseTaxpayerBindingRuntimeFactory.create` | persisted current binding; taxpayer ref is not the operation subject |
| current broker facts | `Gate4OrdinaryTradeCandidateRuntimeFactory.create` | exact case-bound Fact v2 set and disposal fact ID |
| human declaration choices/facts | injected `AuthenticatedDeclarationFactsProvider` | exact user, case, taxpayer and 2025 binding |
| inspection, budget, source party and applicability | injected `DeclarationExternalAuthorityProvider` | exact case/period publication binding |
| legal/methodology version | `Gate5TrustedMethodologyAuthorityFactory.create` | repository resource identity and SHA-256 |
| Fact -> Operation -> Category -> Tax Base | existing source, Tax Model and aggregation owners | owner-produced hashes and input/member bindings |
| Scope -> Package -> release -> projection | existing declaration owners | owner replay plus exact adjacency validation |
| XML/XSD | `Gate5FullTargetXmlProjectionRuntimeFactory.create` | deterministic bytes and official XSD conformance receipt |
| active persistence | `OrdinaryTradeDeclarationMvpRuntime` through the existing ArtifactStore | private XML and MVP receipt artifacts |

Caller supplies only `ArtifactAccessContext` and canonical artifact refs to the
production root. Caller cannot supply a taxpayer ref, disposal fact ID,
methodology version, Scope, Package, released values, projection, or receipt.

## Supported case

- tax period 2025; individual resident; taxpayer signs for self;
- exactly one ordinary organized-market security purchase and one disposal,
  outside IIS, in RUB, with a positive result;
- zero or more disposal-row transaction charges already represented by current
  Fact v2 and consumed exactly once;
- no acquisition commission, derivatives, dividends, coupons, IIS, carried
  loss, foreign currency/source/tax, representative filing, or FNS transport;
- explicit current user facts for filing choice, residency evidence, absence of
  other values in this income group, credits, and refund/credit amount;
- explicit current external-authority facts for inspection, source party,
  organized-market/IIS/exemption applicability, KBK and OKTMO.

Anything outside this matrix stops with a typed blocker. Missing or malformed
identity/user/external owner output never produces XML. Partial acquisition
commission remains `LEGAL_INTERPRETATION_REQUIRED`.

## Persistence and replay

The wire XML is stored as Base64 inside private
`broker_reports_ordinary_trade_declaration_xml_v1`; its SHA-256 is over the
original official `windows-1251` bytes. The paired
`broker_reports_ordinary_trade_declaration_mvp_receipt_v1` binds taxpayer,
current Fact v2 set, current user/external outputs, active assembly receipt,
projection receipt, XML bytes, XSD status and semantic accounting.

`validate_current_declaration` replays all current owners. Recalculating caller
hashes cannot make an old or mixed result current. A provider successor, Fact
successor, foreign case/taxpayer, different run output, or projection mutation
is rejected.

## Prohibitions

No PDF reread, Gate 3, SQL, LLM, declaration-specific calculator, second
assembler, authority registry, workflow framework, inferred external fact,
case-hash taxpayer surrogate, partial XML, or FNS submission is permitted.
