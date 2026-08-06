# Broker Reports DOC31 XLSX Streaming and Cohort Completion

DOC31 replaced the failing XLSX normalization route with a forward-only OOXML
profile while retaining the existing canonical factories and logical root
contract. The exact target OpenWebUI loader was audited and rejected as
canonical authority: it loads all sheets through pandas/unstructured, emits a
text/HTML approximation and does not retain the structural fields required by
Gate 2.

The old canonical path retained source bytes, constructed worksheet DOMs and
row/cell projections twice, deep-copied them through normalization and storage,
and serialized the whole artifact before writing. Arm A reached 715,272,192
bytes and was OOM-killed. The exact OpenWebUI arm reached 548,409,344 bytes and
then stopped on absent NLTK resources. The fixed 256-row OOXML prototype peaked
at 47,837,184 bytes.

The selected `DIRECT_OOXML_STREAMING` route stores workbook-level shared
strings/styles once, retains formula text separately from cached values, keeps
source coordinates and workbook/sheet metadata, compresses blank styled cells
into runs and records unsupported features explicitly. The exact failed XLSX
completed under the 1 GiB cgroup at 156,504,064 bytes with 3,147 formulas,
39,499 blank-styled cells and 141 components.

The frozen cohort resumed without redoing the earlier eight successes and now
has 16/16 active roots and zero missing chunks. One known duplicate source
instance initially collided with the preceding document scope; the unactivated
run was purged through retention authority and the duplicate was re-run with a
stable per-instance scope. Restart and container recreation both retained
16/16. SQLite Online Backup captured all 304 active component payloads; an
isolated restore validated 16/16 roots, all components and cross-tenant denial.

The next stage stopped correctly. All eight retained PDF canonicals contain one
container but zero logical nodes, so `local_pdf_compact_canonical_proof`
returned `CANONICAL_INCOMPLETE` with no fallback. This is pre-existing PDF
source-accounting debt outside the XLSX repair and the contract forbids redoing
those eight documents. Wave 2 shadow was therefore not started.

Final program status: `PARTIALLY_COMPLETED`. XLSX, cohort, durability
and restore are confirmed. Research migration and Wave 2 remain blocked; no
Wave 2/product cutover occurred, the legacy handoff remains, and Gate 3 was not
started. A separate Wave 2 cutover goal is not authorized until the PDF
canonical source-accounting gap is repaired and re-proved.

Terminal test accounting: focused tests passed; full suite result is
`FAILED_ACCOUNTED` with timeout `False`.
