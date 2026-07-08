# Broker Reports Gate 1 Stub Synthetic Test Data

Status: SYNTHETIC_TESTDATA_FOR_GATE1_STUB

This folder contains only synthetic files for the Broker Reports Gate 1
Workspace Runtime Proof / Stub Proof.

Safety rules:

- no customer documents;
- no real names;
- no real account numbers;
- no real tax calculation;
- no source-fact extraction fixture;
- no OCR fixture.

The `.xlsx` case is represented in the proof Action tests through synthetic
OpenWebUI file metadata, not by a binary workbook fixture. Parser-quality proof
for real workbook bytes is intentionally deferred.
