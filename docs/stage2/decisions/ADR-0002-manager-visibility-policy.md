# ADR-0002 Manager Visibility Policy

Status: Proposed

## 1. Context

PRD-1 includes a requirement to check and configure manager access to work chats.
The intended scope is controlled work-chat visibility inside assigned
groups/workspaces, not silent access to all personal or draft chats.

OpenWebUI groups, RBAC and sharing may support parts of this requirement, but
deployed runtime proof is still needed.

## 2. Problem

Manager Visibility is not just a permission toggle.

If implemented too broadly, it can expose unrelated personal/draft chats and
create a privacy/security issue. If implemented too narrowly, it may not satisfy
the customer need for work supervision.

## 3. Decision needed

Approve a manager visibility policy that defines:

- working chats vs personal/draft chats;
- manager-visible groups/workspaces;
- employee notice;
- admin visibility separately from manager visibility;
- runtime proof matrix.

## 4. Options

Option 1. Native sharing-only model.

- Use groups and access control for shared work chats/resources.
- Lowest implementation risk.
- May not satisfy automatic manager oversight.

Option 2. Explicit work-scenario visibility model.

- Users run approved workflows in named scenarios.
- Manager sees only outputs/chats covered by policy.
- Recommended for Stage 2 if runtime proof supports it.

Option 3. Custom supervisory view.

- Higher privacy and upgrade risk.
- Use only if customer explicitly requires it and native proof fails.

## 5. Recommended option

Use Option 2 as the policy target and prove whether it can be implemented with
native OpenWebUI groups/sharing/admin surfaces.

Working chats:

- created inside approved work scenarios;
- tied to assigned group/workspace;
- covered by employee notice/policy.

Personal/draft chats:

- not part of approved work scenario;
- not visible to manager by default.

## 6. Consequences

- Manager visibility requires customer policy approval.
- Admin visibility remains a separate decision.
- Runtime tests must check both allowed visibility and non-visibility.
- If native model is insufficient, fallback may be export/reporting/policy-only
  rather than a live supervisory UI.

## 7. Runtime proof needed

Create and test:

- Admin.
- Manager/РО.
- Employee inside group.
- Employee outside group.

Verify:

- manager sees approved work chats in assigned group/workspace;
- manager does not see unrelated personal/draft chats without policy;
- employee outside group is not exposed;
- sharing/group behavior is recorded with exact OpenWebUI settings.

## 8. Customer input needed

- Which chats are work chats?
- Which groups/workspaces are manager-visible?
- Should employees see the rule before using the scenario?
- Does manager need live visibility, export, or periodic report?
- Should manager access be audited?
- What is the admin visibility policy?

## 9. Acceptance signals

- Manager visibility matrix approved.
- Test users/groups created.
- Manager sees approved work chats only.
- Unrelated personal/draft chats remain not visible without rule.
- Native limitation or fallback option documented if native proof fails.

## 10. Links

- [MANAGER_VISIBILITY_AND_RETENTION](../blueprints/MANAGER_VISIBILITY_AND_RETENTION.blueprint.md)
- [RBAC_MANAGER_VISIBILITY_RESEARCH](../research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)
- [ACCEPTANCE_MATRIX](../acceptance/ACCEPTANCE_MATRIX.md)
