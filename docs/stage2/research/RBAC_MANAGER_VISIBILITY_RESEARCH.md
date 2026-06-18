# RBAC Manager Visibility Research

## 1. Question

Can OpenWebUI support manager visibility into work chats by group/workspace without exposing all
personal chats?

## 2. Research status

Status: researched from official OpenWebUI docs on 2026-06-18.

Result type: native RBAC/sharing capabilities confirmed; manager-supervision requirement remains
unproven in deployed runtime.

## 3. Findings

- OpenWebUI RBAC has Roles, Permissions and Groups. Permissions are additive: groups add
  capabilities, they do not create deny rules.
- Groups can grant feature access and shared access to resources. Current docs explicitly recommend
  separating permission groups from sharing groups.
- Chat sharing supports access control for users/groups. Public sharing can be disabled for
  non-admins; group sharing exists.
- These capabilities support shared workspaces/resources and controlled collaboration.
- The docs do not prove a native "manager sees all subordinate work chats" model. Sharing a
  chat/resource with a group is different from automatic supervisory read access to all chats
  created by team members.

## 4. Privacy boundary

Recommended interpretation for PRD-1:

- Work artifacts that belong to a declared work scenario can be shared/exported/reviewed by policy.
- Personal/private chats remain outside manager visibility unless the customer explicitly approves a
  broader policy.
- Users must know which chats/scenarios are work-visible.
- Do not silently turn every employee chat into manager-readable data.

Manager Visibility is a policy/security-controlled capability. It is not just a permission toggle,
and it must not be implemented as "manager sees everything".

## 5. Decision options

1. Native sharing-only model.
   - Use groups and access control for shared work chats/resources.
   - Lowest implementation risk.
   - Does not satisfy automatic manager oversight.

2. Work-scenario account/resource model.
   - Users run broker/STT/search workflows in named shared scenarios.
   - Manager sees outputs because resources are shared by design.
   - Requires process discipline and acceptance tests.

3. Custom visibility/export/audit slice.
   - Build or configure explicit review/export mechanism.
   - Higher privacy and upgrade risk.
   - Only justified if customer requires supervisory access beyond native sharing.

## 6. Recommended next step

Before implementation, run a test matrix in deployed or staging OpenWebUI:

- create `Team-A` sharing group;
- create `Manager-A` user;
- create normal user chat;
- share chat to `Team-A`;
- verify what manager can and cannot see;
- verify whether group membership alone exposes existing chats.

Required runtime proof actors:

- Admin;
- Manager/РО;
- employee inside group;
- employee outside group.

Proof must record whether working chats, personal/draft chats and shared chats are visible for each
actor.

## 7. Sources

- https://docs.openwebui.com/features/authentication-access/rbac/
- https://docs.openwebui.com/features/authentication-access/rbac/permissions/
- https://docs.openwebui.com/features/authentication-access/rbac/groups/
- https://docs.openwebui.com/features/chat-conversations/chat-features/chatshare/

## 8. Status

Research complete. Implementation decision blocked by customer policy and runtime proof.
