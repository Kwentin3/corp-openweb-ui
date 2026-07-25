# Broker Reports — Gate 2 ambiguity discipline, Goal 11B

Дата: 2026-07-25

Статус: `COMPLETED`

## Outcome

Первый Haiku stage preflight остановился fail closed до provider call:

`economy_workload_qualification_candidate_forbidden`

Причина: Haiku был зарегистрирован в общей economy model matrix и provider
profile, но не в candidate matrix workload `gate2_financial_evidence`.

Исправлена только code-owned workload policy:

- `claude-haiku-4-5-20251001` стал единственным target candidate для
  financial evidence;
- terminal Nano удалён из financial qualification candidates, что
  структурно запрещает повтор;
- Gemini 3.1/3.5 остаются diagnostic candidates;
- production admissions остаются пустыми;
- fallback в qualification остаётся `0`.

## Policy identities

- model policy version/hash unchanged:
  `1.4.0` /
  `e71bbb7c95774058bc2324343a2de2adef2f3307d8b30f8e92d8cbf514bd09c9`;
- workload policy hash:
  `3d3531d060dacf189c9c82701b5d0a71e93d102cbce8c64aa7093677071373de`;
- qualification policy hash:
  `901c32f1afe865a835d849285862e8077bbe5f62b7690f63737accbe143a6ebe`;
- repository Action source SHA-256:
  `f178b142403e52897d2caf74ad75576162331efa85b0da85d472d8301ad24932`.

The qualification-only Action repository snapshot is updated. It is not
delivered to stage in this Goal.

## Preflight blocker accounting

The blocked preflight proved:

- exact Haiku ID is present in published stage inventory;
- then-current live qualification Action matched the then-current repository
  policy;
- local Q0/Q1 and provider dry-build were not bypassed;
- provider calls: `0`;
- customer calls: `0`;
- stage mutations: `0`.

The blocked preflight is not a model attempt and consumes no qualification
attempt.

## Contracts changed

- financial-evidence workload candidate ordering/authorization;
- qualification-only Action repository snapshot;
- authorization/provider-selection tests;
- generated bundle policy hashes.

## Contracts unchanged

- global economy model declarations and prices;
- benchmark/scope/context/prompt/provider projection;
- Registry/validator/materializer/artifacts;
- source/domain/checksum workload candidates;
- production admissions and routing;
- Nano terminal evidence.

## Verification

- focused policy/action/harness/bundle tests:
  `64 passed, 5 warnings in 10.87s`;
- full Broker Reports suite:
  `1522 passed, 20 skipped, 5 warnings in 115.98s`;
- Ruff: passed;
- bundles rebuilt twice deterministically;
- provider/customer calls: `0/0`;
- production/stage mutations: `0/0`.

Deterministic bundle SHA-256:

- Gate 1:
  `19406e0300f821328d6625877e5d0c393803231472a7a6b92a294223ed1012b2`;
- Gate 2 source:
  `507bf34b4467de5d500055853c36d544a8e0b278b55c294eadaf44d92f6a6bb2`;
- Gate 2 domain:
  `05c56b1599910b33dfe17473727a7ea6f950a61b8bb73438a57469175a4da621`.

The warnings are unchanged SWIG deprecation warnings.

## Repository boundary

- base:
  `c23c4f5e7a4ca92eb8b0aaaccfeac313e3b2ab94`;
- branch:
  `codex/broker-reports-gate2-ambiguity-goal11b-haiku-workload-policy`;
- PR: pending creation;
- production admission: false.

## Acceptance

- `HAIKU_FINANCIAL_AUTHORIZATION: CODE_OWNED`
- `TERMINAL_NANO_REAUTHORIZATION: STRUCTURALLY_FORBIDDEN`
- `PRODUCTION_ADMISSIONS: EMPTY`
- `PROVIDER_CALLS: ZERO`

Следующий шаг после merge: отдельная stage Action delivery с rollback/readback
proof. Только после её merge разрешён новый Haiku qualification preflight.
