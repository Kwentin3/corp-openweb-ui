# OfficeCLI author workflow integration

Goal: deliver the installed author's methodology and capabilities through native OpenWebUI, with task-level product acceptance. A particular spreadsheet is a regression input, not the definition of this goal.

## Authoritative baseline

Runtime: OfficeCLI 1.0.152; OpenWebUI 0.9.6. Sources are version-bound:

- [MCP description and help strategy](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/src/officecli/McpServer.cs): inspect, modify, schema/content/visual delivery checks.
- [Skill discovery implementation](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/src/officecli/Core/SkillInstaller.cs): push a minimal trigger; pull the catalog, one specific guide and bundled references. The authors explicitly found informational skill hints were ignored; their trigger requires FIRST loading before mutation.
- [Umbrella guide](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/SKILL.md): prefer L1 read, then L2 DOM, then L3 raw; use help rather than guessing.
- Format guides: [Word](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/skills/officecli-docx/SKILL.md), [Excel](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/skills/officecli-xlsx/SKILL.md), [PowerPoint](https://github.com/iOfficeAI/OfficeCLI/blob/v1.0.152/skills/officecli-pptx/SKILL.md). These guides, including their limits and delivery gates, remain owned by OfficeCLI; no handwritten replacement guide is introduced.

## Observed delivery gaps

The installed native catalog has ten skills. Our loader accepted only word/excel/pptx, required a name and could not fetch references. Our Filter allowed creation without loading a skill and made broader guidance optional. The root command help and document-root properties were unreachable. Textual inspection omitted issues/stats for all formats and outline/text for presentations; raw inspection and screenshots were unreachable.

The earlier real workbook run independently proved picture removal, but its claim about removing external links was false. This proves a missing requirement verification, not that schema validation detects external references. No automatic conversion of unknown values to zero belongs in this integration.

## Ownership map

| Meaning | Existing owner | Contract to consumer |
|---|---|---|
| Skill selection rules, guide body, references | Installed OfficeCLI | Existing skill load endpoint delegates catalog/name/path verbatim |
| Command/property catalog | Installed OfficeCLI | Existing safe help endpoint delegates documented tokens |
| Document interpretation and screenshot pixels | Installed OfficeCLI | Existing inspect tools plus one read-only native PNG render operation |
| Session, file access, tool-result image context | OpenWebUI | Forwarded session and authorized native file download; binary PNG response consumed by native tool middleware |
| Tool attachment and routing instructions | Existing Filter | Minimal guide-first trigger and native adapter usage, no parallel document methodology |

The render adapter limits one render at a time and one page/slide per call. XLSX screenshots cover its active sheet only, which is explicitly disclosed. These transport/resource limits do not redefine the authors' delivery rules.

The installed catalog is 6,319 characters; default guides are Word 42,289, Excel 34,926, PowerPoint 44,086. These are fetched once per artifact, not injected into every request. The native specialized morph-ppt manifest exposes reference/decision-rules.md; its original 5,994-character body was successfully fetched from the pinned binary. Full guide availability has a real context cost; truncation or a handwritten replacement would hide required methodology again.

Replaying the pinned OpenWebUI OpenAPI converter on the candidate preserved the optional catalog invocation, skill reference path, raw/validate command enums and render format/file ID. It produced 14 operations including health (20,509 characters of converted schema). The permanent Filter instruction is 5,483 characters. Binary image handling was verified in the pinned native tool source: image/png becomes a data image, then an input_image in function_call_output; no custom image injection or core overlay is needed. Ordinary-chat image acceptance still has to prove this path end to end.

## Product acceptance tasks

| Task | Observable acceptance |
|---|---|
| Edit a multi-sheet XLSX with pictures away from its first sheet | Load Excel guide once; discover real picture paths; remove all pictures; independently verify values/formulas/order and no media parts |
| Create a small XLSX calculation | Load guide, use formulas; inspect issues/result values; do not call an active-sheet screenshot an all-sheet visual audit |
| Edit a DOCX with text and an image | Load appropriate guide; identify real nodes; preserve unrelated content; inspect final content/issues and actual rendered page |
| Create/edit a PPTX with visible text and shapes | Load guide; use exact help; get a screenshot as image context; detect/fix visible overflow or overlap; verify requested text and final attachment |
| Discover a specialist task (e.g. fillable Word form) | Discover the installed catalog; select word-form; fetch any manifest reference needed without stacking generic guides |
| Attempt a requirement that cannot be established | Disclose the unmet requirement and evidence limit; do not declare success from validation, filename or a partial query; do not invent replacement values |

## Evidence status

Candidate only; no release or ordinary-chat acceptance of this candidate yet. Adapter/Filter tests: 214 passed. Final isolated installed-package qualification with real OfficeCLI 1.0.152 passed in 43.328 seconds on image sha256:47199660d2ee62a9e3ed5d8502c856f86425618854b0fba9e71a520e1c9c2d70, network disabled, read-only root and 128 MiB temporary storage, with a 1 GiB memory cap: official catalog and Word/Excel/PowerPoint/word-form guides, native object discovery and raw parts, issues/validation, genuine PNGs in all three formats and XLSX picture removal with independent ZIP/cell/formula comparison. This proves components, not provider behavior or the native image delivery to a model. Existing production remains the previously accepted #535/#536 release while this candidate is tested.
