---
name: corporate-template-authoring
description: Подготовка корпоративного DOCX-шаблона из приложенного документа, согласование полей и публикация инструкции и отдельного оригинала для коллег.
---

# Prepare a corporate DOCX template

Use this workflow when the user asks to prepare, clean up, mark or publish a
reusable corporate Word template. Use the existing OfficeCLI tools and native
Skills/Knowledge/Files. Keep the binary DOCX outside the Skill.

Use the OfficeCLI API operations actually available in this chat and their
installed skill/help; command examples do not imply access to a local CLI or
filesystem. Before an available Terminal is used for a named unsupported
operation or copy repair, confirm transfer/access to the exact native source
and the supported route back to a published native File. Keep the original
unchanged. Do not use Terminal to bypass publication approval or native ACL.

## Inspect and agree

1. Identify the actual native source File ID from the current chat. Inspect the
   original with OfficeCLI before editing. Read the installed DOCX guide once;
   get command help when needed. Discover the whole document and appendices,
   tables, headers/footers, existing Word form fields and repeated values.
2. Follow native inspection pagination to recover every field. Distinguish
   constants, required inputs, optional inputs, repetitions and internal markers.
   A marker is not automatically a business input. Do not guess missing facts.
3. Propose the field groups and preparation changes in ordinary language. Keep
   the document's purpose and fixed clauses. Obtain agreement before preparing
   the publication copy; obtain explicit publication approval before sharing it.

## Prepare a copy

4. Retain usable Word form fields rather than introducing visible placeholders.
   Inspect actual paths and metadata before using them. Preserve defaults,
   field instructions and bookmarks; give only unnamed fields unique names if
   useful. Record repeated occurrences under one agreed business input.
5. Use `apply_office_batch` with the explicit source `file_id`, at most 64
   operations per call. For a continuation, use the previous `result_file_id`.
   Do not rebuild the document or overwrite its source.
6. A form field's displayed result may have a different run style from its
   separator. Preserve that style. For formatting-sensitive text use verified
   exact absolute XPath operations on the cached text node, after inspecting
   native raw XML and command help. Avoid broad text replacement and relative
   following-sibling XPath. Escape XML text when necessary.
7. Inspect the prepared result and render all its pages. Check field coverage,
   fixed text, tables, signatures, headers/footers and images. A successful batch
   or validation result alone does not prove preservation. Report any unresolved
   difference; do not publish an unverified copy.

## Publish agreed instructions and the separate original

8. Write one concise, text-only template Skill. Include its purpose and concrete
   selection phrases, required/optional input groups, the actual field/occurrence
   map, fixed-content rules, fill procedure and final checks. For formatting-sensitive
   cached fields, record verified exact text-node paths against the original File
   ID and SHA-256 so filling does not require reading the entire raw XML again.
   Require checks supported by the installed tools; report an unavailable external
   Word check as a limitation and return the produced copy with its actual status.
   When verified legacy fields reset to their defaults on update, document the
   tested finalization for the filled copy (for example, locking only those
   fields with native `w:fldLock`). Keep the reusable original unchanged and
   preserve page-number fields. Describe all
   remaining unknowns honestly. Do not include binary/base64 or private test data.
9. Create the private Skill with native `create_skill`, keeping only `SKILL.md`.
   Once the user approves sharing, call
   `publish_template(skill_id=<returned id>, file_id=<verified prepared result>)`.
   The configured native Knowledge library owns access to the original. The
   publication Tool adds its authoritative original reference and shares the
   instructions with that library's read audience.
10. Accept publication only when the Tool returns `status=published` and saved
    native IDs. Report `blocked` or `partial` honestly and inspect current native
    state before another publication; do not blindly retry or delete user data.
    Return the Skill name and the original-file link with the actual result.

The consumer workflow is owned by the existing `artifact-workflow` Skill;
the published template Skill supplies its template-specific instructions and
original File binding. Do not duplicate the consumer orchestration here.
