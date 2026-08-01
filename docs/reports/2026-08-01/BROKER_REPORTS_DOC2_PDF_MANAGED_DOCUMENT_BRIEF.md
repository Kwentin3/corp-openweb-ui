# Broker Reports DOC2 PDF Managed Document Brief

Status: `PASSED`

Date: 2026-08-01

DOC2 adds one inactive PDF-to-Managed-Document-v1 owner before the old
page-unit loss point. It builds one ordered block stream from parser block/word
order, inserts validated tables at their first owned word, preserves invalid
table regions as `UNKNOWN`, and records page-level visuals with explicit known
losses. Table text cannot also become paragraph text.

Proof summary:

```text
real PDFs = 5 total, 4 readable/valid PARTIAL, 1 encrypted BLOCKED
source observations = 1207 total, 0 unresolved, 0 unaccounted loss
represented = 353, known loss = 853, blocked at source = 1
validated TABLE blocks = 6, explicit table mappings = 112
PDF-only checklists = 4, artifact-only checklists = 4
full parity = 4/4, critical = 0, noncritical = 0
replay = 38 files, 0 mismatches
full suite = 2349 passed, 5 historical skips, 0 failures/errors
generated bundle diff = 0, provider calls = 0, live changes = 0
```

Delivery:

- base: `88e2b4931aee613ef64a187ba475ce3a367e4ca8`;
- implementation: `a147adc8ad0f99f3f53bf7a4be09b4acdf4d6f2e`;
- implementation PR: `#249`;
- implementation merge: `0c986919296de16f42ec322400c85e5eee9914f1`;
- evidence merge: reported in the terminal response due to self-reference.

Private PDF bytes, values, pointers, filenames, and full checklists remain
outside Git. DOC1 schema is unchanged. DOC3, DOC4, LLM-friendly rendering,
real model qualification, and product activation are not started.
