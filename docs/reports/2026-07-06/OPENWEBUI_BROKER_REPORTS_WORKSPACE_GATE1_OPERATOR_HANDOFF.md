# OpenWebUI Broker Reports Workspace Gate 1 Operator Handoff

Status: OPERATOR_ACTION_REQUIRED

Scope: minimal live proof for Broker Reports Workspace + Gate 1 Action stub

Use only synthetic files from:

```text
docs/stage2/testdata/broker_reports_gate1_stub/
```

Do not use customer documents.

## Checklist

1. Open the target OpenWebUI admin/runtime session.
2. Create or verify a restricted Workspace Model named `Broker Reports / XLS NDFL Draft Scenario`.
3. Restrict the model to the approved Broker Reports proof group and verify an outside user cannot see it.
4. Install the proof-only Action from `services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_normalizer_action.py`.
5. Create a new synthetic client chat and upload:
   - `synthetic_gate1_text_pdf_or_txt.txt`
   - `synthetic_gate1_operations.csv`
6. Call the installed Action with the uploaded files attached.
7. Confirm the Action result appears in the same chat and contains `Select case_group_synthetic_001`.
8. Record only these safe facts in the follow-up note:
   - OpenWebUI version;
   - model visible to inside user: yes/no;
   - model visible to outside user: yes/no;
   - Action saw `body["files"]`: yes/no;
   - Action could read uploaded bytes: yes/no;
   - same-chat report appeared: yes/no.

Do not copy filenames from real customer files, account numbers, document text,
tokens, admin credentials or raw local paths into the note.
