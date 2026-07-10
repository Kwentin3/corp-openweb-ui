# OpenWebUI Broker Reports Workspace Gate 1 Operator Handoff

Status: CUSTOMER_APPROVED_UPLOAD_ALLOWED_ONLY_VIA_PROCESS_FALSE_PRIVATE_INTAKE

Scope: Broker Reports Workspace + Gate 1 Pipe source-intake proof

Use only synthetic files from:

```text
docs/stage2/testdata/broker_reports_gate1_stub/
```

Do not use customer documents.

Do not use normal OpenWebUI bulk chat upload for Broker Reports customer
packages. The 2026-07-08 synthetic no-RAG smoke showed that `file_context=false`
on the Workspace Model did not stop default OpenWebUI upload
extraction/vectorization on the target route. The approved customer-test route is
the project-owned `process=false` private intake path.

## Checklist

1. Open the target OpenWebUI admin/runtime session.
2. Create or verify the restricted Broker Reports Workspace Model bound to `broker_reports_gate1_pipe`.
3. Restrict the model to the approved Broker Reports proof group and verify an outside user cannot see it.
4. Ensure `file_upload=true`, `file_context=false`, and Knowledge attachments are empty for the synthetic proof.
5. Use the project-owned `process=false` private intake wrapper before any customer package upload.
6. Confirm vector DB delta is zero. If it is not zero, stop the customer package run.
7. Confirm the Gate 1 Pipe receives opaque refs and returns a compact safe report.
8. Record only these safe facts in the follow-up note:
   - OpenWebUI version;
   - model visible to inside user: yes/no;
   - model visible to outside user: yes/no;
   - Pipe saw opaque file refs: yes/no;
   - Pipe could read uploaded bytes: yes/no;
   - same-chat report appeared: yes/no.
   - Knowledge delta: zero/non-zero;
   - vector DB delta: zero/non-zero;
   - uploaded file data extraction observed: yes/no;
   - explicit retention policy: yes/no.

Do not copy filenames from real customer files, account numbers, document text,
tokens, admin credentials or raw local paths into the note.
