# OfficeCLI operation guidance follow-up

Goal: deliver the OfficeCLI authors' workflow through native OpenWebUI, rather than define success as repairing one workbook.

## Observed product behavior after PR #537

PR #537 was merged as 684a637fac3e856aea3e1b6d6dd93b38af573460 after successful CI run 36342828770. Production uses OfficeCLI 1.0.152 and Filter 1.3.0-author-workflow. Its installed package matches source 839cb2cba390ff4478215457097c74b5e15b26b5 (the exact source identity is recorded in the release receipt).

Ordinary authenticated chats with gpt-6-luna exercised synthetic DOCX, XLSX and PPTX documents through the registered tools. The initial DOCX edit skipped loading a skill and visual inspection. A repeat loaded the Word guide once, inspected the result and received one native input_image. Both produced the requested content. Therefore the omission is an observed inconsistent agent decision; the evidence does not establish a missing Filter delivery or stale module cache. The native update route refreshes its loaded module, and the repeated frontend request did not prepopulate tools.

The PPTX task loaded its guide, corrected an overflowing title, inspected issues and received an actual rendered slide as input_image. The XLSX task loaded the Excel guide, created formulas, identified and removed an unwanted empty sheet, and received two rendered previews. Independent downloads verified DOCX text and paragraph styles with zero pictures/media; the PPTX title lies inside slide bounds and the other text shape is unchanged; the XLSX contains only the requested sheet and three live formulas with cached results 2000, 4500 and 6500.

Viewing the actual XLSX image exposed clipped headers. The inherited Filter banned unrequested column widths/styling, directly contradicting the installed Excel skill's required explicit widths and readable labels. Remove that adapter-level restriction for new work; explicit user formatting-preservation constraints still take precedence.

Several final answers invented attachment:// or sandbox:/ download links despite native file attachments being present. Tool responses supplied an opaque result_file_id but no download route. Authenticated browser retrieval from the actual native /api/v1/files/{id}/content route succeeded.

A further multi-sheet XLSX chat loaded the catalog/Excel guide, discovered and removed all 37 pictures, and checked final DOM content. An independent download confirmed zero picture/media parts and unchanged cell values/formulas/number formats/sheet order. Its final reply nevertheless captioned an earlier preview and mislabeled it as a source render. The installed middleware contains a non-stateful image fallback that appends a user-role request to analyze tool-result images; this is a plausible contextual contributor, not proof of the exact provider branch for that run. The PNG also displays the adapter's temporary source.xlsx basename. Scope and provenance therefore need explicit adapter guidance: previews verify the original task and their identity comes from the render call's file_id. No core image-protocol changes are introduced.

An ordinary unsupported-requirement chat discovered the official catalog, loaded Excel guidance, consulted help and honestly declined to fabricate an XLSM/VBA deliverable. It created no substitute attachment. This proves disclosure for that available-adapter boundary, not universal OfficeCLI limitation handling.

## Narrow adaptations

- Every create/apply/compose tool description starts with the upstream imperative FIRST load_officecli_skill, unless already loaded for that artifact, and retains the author's content/visual delivery checks. This follows [SkillInstaller.BuildSkillTriggerSummary](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/src/officecli/Core/SkillInstaller.cs), rather than adding hidden skill state or mutation gates.
- Remove the misleading description that apply is a final operation: required inspection follows the published result.
- Mutation responses provide download_url derived from their actual result_file_id using the same native route as authorized file downloads. Native attachment identities and access control remain unchanged.
- Remove the inherited prohibition on column widths that contradicted the official Excel guide. User-specified preservation still takes priority.
- Render descriptions and the Filter explain image provenance and continued ownership of the original task after image analysis.
- The existing Filter explains this adapter's nonresident execution and how to use the returned final download_url. It does not replace the official skills, add a lifecycle manager, or expose local paths as links.

## Candidate validation

Final adapter/Filter tests: 222 passed; Ruff critical checks and git diff --check passed. Final installed-package qualification passed in 44.212 seconds on image sha256:254ba1f0491bb05c3efab9a60c47c5097247087afa25ee978c1f76b8973f0dfb under disabled network/read-only root/1 GiB memory cap. It covered official catalog/guides, native objects/raw parts, issues/validation, PNG rendering for all three formats, and multi-sheet XLSX picture removal with an actual result download_url and preserved source bytes/cells/formulas/order. Replaying the pinned native OpenAPI converter preserved all seven mutation triggers across 14 operations (including health; 21,993 schema characters). The permanent instruction is 6,319 characters; full official guides remain lazy. Product findings above describe #537, not proof of this follow-up's release. Fresh ordinary-chat acceptance remains necessary after deployment, including honest disclosure of an unsupported requirement.

The original customer files and unrelated workspace changes were not modified. Public evidence uses synthetic documents and excludes private chat contents.
