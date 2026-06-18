# ADR-0002 Manager Visibility Policy

Status: Proposed
Date: 2026-06-18
Domain: Manager visibility / RBAC / privacy

## 1. Context

PRD-1 includes a requirement to check and configure manager access to work chats. The intended scope is controlled work-chat visibility inside assigned groups/workspaces, not silent access to all personal or draft chats.

OpenWebUI groups, RBAC and sharing may support parts of this requirement, but deployed runtime proof is still needed.

## 2. Problem

Manager Visibility is not just a permission toggle.

If implemented too broadly, it can expose unrelated personal/draft chats and create a privacy/security issue. If implemented too narrowly, it may not satisfy the customer need for work supervision.

## 3. Why This Is Not Just a Permission Toggle

- Group membership and sharing do not necessarily mean supervisory access.
- Additive permissions can create accidental overexposure.
- Admin visibility and manager visibility are different policies.
- Employees must know which work scenarios are visible.
- Runtime behavior must be proven with test users, not inferred from docs.

## 4. Working Chats vs Personal/Draft Chats

Working chats:

- created inside approved work scenarios;
- tied to assigned group/workspace;
- covered by employee notice/policy;
- eligible for manager visibility if approved.

Personal/draft chats:

- not part of approved work scenario;
- not visible to manager by default;
- may be visible only if customer explicitly approves a broader policy.

## 5. Visibility Boundaries

- Manager sees only assigned group/workspace chats.
- No hidden access to unrelated personal chats.
- Employee awareness / policy notice required.
- Admin visibility separately defined.

## 6. Actor Matrix Draft

| Actor | Approved work chat in assigned group | Personal/draft chat | Work chat outside assigned group | Admin surfaces |
| ----- | ------------------------------------ | ------------------- | -------------------------------- | -------------- |
| Admin | Allowed by admin policy | Separately defined | Separately defined | Allowed by admin policy |
| Manager/РО | Allowed only if policy/runtime proof passes | Not allowed by default | Not allowed | Not admin |
| Employee inside group | Own chats and explicitly shared group resources | Own personal/draft chats | Not allowed unless shared | Not admin |
| Employee outside group | Not allowed unless shared | Own personal/draft chats | Own group only | Not admin |

## 7. Native OpenWebUI Proof Needed

- Create test users and groups.
- Verify visibility of approved work chats.
- Verify unrelated personal/draft chats are not visible without rule.
- Verify sharing/group behavior.
- Record exact settings, roles, permissions and limitations.

## 8. Fallback Options

- Explicit shared workspace model.
- Export/audit.
- Reporting.
- Policy-only.
- Minimal customization.
- Deferred custom supervisory view.

## 9. Open Questions for Customer

- Which chats are work chats?
- Which groups/workspaces are manager-visible?
- Should employees see the rule before using the scenario?
- Does manager need live visibility, export, or periodic report?
- Should manager access be audited?
- What is the admin visibility policy?

## 10. Acceptance Signals

- Manager visibility matrix approved.
- Test users/groups created.
- Manager sees approved work chats only.
- Unrelated personal/draft chats remain not visible without rule.
- Native limitation or fallback option documented if native proof fails.

## 11. Status

Proposed. Needs customer policy approval and native OpenWebUI runtime proof.
