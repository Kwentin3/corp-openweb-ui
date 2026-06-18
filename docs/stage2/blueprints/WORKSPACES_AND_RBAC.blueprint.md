# Workspaces And RBAC Blueprint

## 1. Purpose

Собрать Stage 2 вокруг рабочих пространств, групп, prompts/templates, shared knowledge and access
rules.

## 2. PRD-1 requirements covered

- Рабочие пространства под задачи.
- Группы пользователей и доступы.
- Общие prompts/templates/knowledge.
- AI-methodologist/admin ownership.
- Пользователь видит только разрешенные сценарии.

## 3. Current known context

PRD-0 не включал corporate RBAC. PRD-1 требует managed workspaces, но OpenWebUI может не иметь
единой product-сущности "business workspace"; сценарий нужно собирать из native mechanisms.

## 4. Target user workflow

Пользователь входит в портал, видит разрешенные рабочие сценарии, выбирает сценарий, использует
approved prompt/template and knowledge, создает индивидуальный рабочий чат внутри общего сценария.

## 5. Native OpenWebUI first path

- Groups/RBAC.
- Workspace Models.
- Workspace Prompts.
- Workspace Knowledge.
- Model access control.
- Admin UI configuration.

## 6. Integration / custom implementation path

Custom work допустим только если native модель не позволяет собрать согласованные workspace/access
boundaries. Возможные варианты: policy-only, export/audit procedure, minimal admin helper, minimal
UI/backend customization.

## 7. Data and security notes

Workspace не является файловым хранилищем. Общие документы допустимы как
instructions/templates/methodics/examples/approved prompts. Sensitive data rules inherit from
SECURITY_DATA_POLICY.

## 8. Dependencies

- OpenWebUI capability research.
- Customer group/role list.
- Manager visibility policy.
- Provider/model catalog.

## 9. Risks and constraints

- Additive/union permission model may not support deny rules.
- Рабочие и личные чаты могут смешаться без policy.
- AI-methodologist process may be unclear.

## 10. Open questions

- Какие группы финальные?
- Кто owner prompts/templates?
- Нужны ли approval/versioning rules for prompts?
- Какие workspaces стартуют в Base/Practical Stage 2?

## 11. Research links

- [OPENWEBUI_CAPABILITY_RESEARCH](../research/OPENWEBUI_CAPABILITY_RESEARCH.md)
- [RBAC_MANAGER_VISIBILITY_RESEARCH](../research/RBAC_MANAGER_VISIBILITY_RESEARCH.md)

## 12. Acceptance signals

- Минимум 3 сценария имеют owner, access group, prompts/templates, knowledge and user guidance.
- Тестовый пользователь видит только разрешенные сценарии.
- Admin/AI-methodologist process documented.

## 13. Implementation readiness

Needs research and customer group matrix before implementation planning.
