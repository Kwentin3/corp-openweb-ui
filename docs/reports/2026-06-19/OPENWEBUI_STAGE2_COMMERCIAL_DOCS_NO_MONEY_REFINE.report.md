# OpenWebUI Stage 2 Commercial Docs No-Money Refine Report

## 1. Summary

Applied the repository no-money policy to tracked Stage 2 markdown documentation.

GitHub-tracked markdown now records scope, hours status, evidence and limitations without monetary amounts, payment schedule or financial terms.

Final policy:

```text
GitHub-документация фиксирует состав работ, трудозатраты, статусы,
доказательства и ограничения. Денежные суммы, график оплаты и финансовые
условия фиксируются только в договорах, счетах и актах и не хранятся в
markdown-документации репозитория.
```

## 2. Files Checked

Checked the requested commercial/scope set:

- legacy completed-work commercial audit file;
- legacy scope reconciliation commercial file;
- completed-work audit report file;
- scope reconciliation report file;
- all tracked `docs/commercial/*.md`;
- `docs/stage2/README.md`;
- `docs/stage2/CONTEXT_INDEX.md`;
- root `README.md`.

Also checked and refined tracked PRD, Stage 2 research, Stage 2 proposals, Stage 2 implementation notes and generated reports returned by the tracked monetary-reference grep.

Untracked local draft/buffer files under `docs/out/` and OCR/VL V2 research were not staged into this policy commit.

## 3. Monetary References Removed

Removed or neutralized:

- explicit tranche monetary amounts from commercial audit and scope reconciliation docs;
- references to an external act/invoice amount;
- contract/report wording that described payment values;
- provider price amounts from PRD markdown;
- provider price amounts from Web Search research;
- provider price amounts from STT provider research;
- OCR/VL OCR provider planning estimates that contained monetary values;
- Russian `stoimost` wording that made grep noisy for repository policy checks;
- false-positive `rub` substrings inside Russian words by replacing them with neutral synonyms.

Replacement wording uses:

- `commercial tranche`;
- `limited Stage 2 tranche`;
- `financial terms are recorded outside GitHub`;
- `usage/cost visibility`;
- `external billing docs`;
- `scope boundary`;
- `estimated hours` where hours are already part of the document.

## 4. Scope/Hour References Preserved

Preserved:

- Stage 2 Tranche 1 scope;
- first functional/architectural slice framing;
- done / partial / future / out-of-scope distinctions;
- STT/media transcription evidence;
- Web Search baseline evidence;
- Brave, Yandex Search API and private SearXNG provider-path framing;
- architecture/contracts/gates/backlog evidence;
- PRD links and report links;
- hour estimates where already present.

No new hour estimates were invented.

## 5. Policy Note Added

Policy note added to the relevant commercial/scope docs:

- completed-work commercial audit file;
- scope reconciliation commercial file;
- completed-work audit report file;
- scope reconciliation report file.

The policy text states that repository markdown stores scope, hours, status, evidence and limitations only. Financial terms remain in external contract documents.

## 6. Grep/Check Results

Tracked GitHub markdown check used the repository monetary-reference pattern plus provider-price markers.

Result:

```text
no matches in tracked markdown
```

Broad working-tree `rg docs README.md` still reports only untracked local draft/buffer files. Those files are not part of GitHub-tracked documentation and were not staged for this commit.

## 7. Remaining Intentional Monetary References, If Any

No intentional monetary references remain in tracked GitHub markdown.

Untracked local draft/buffer files may still contain provider price research. They are outside the tracked GitHub documentation set for this refine.

## 8. Final Verdict

Final verdict:

`stage2_github_docs_no_money_policy_applied`
