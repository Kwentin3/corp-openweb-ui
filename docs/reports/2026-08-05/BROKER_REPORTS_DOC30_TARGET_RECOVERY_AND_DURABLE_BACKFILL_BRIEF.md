# DOC30 Brief

`PARTIALLY_COMPLETED`: SSH and HTTPS recovered, the DOC29 incident is fully
accounted, both Broker and STT stores pass integrity checks, and the correct
recovery decision is `RETAIN`. DOC29 was killed by the host OOM killer and
wrote no canonical state.

The new one-document, checkpointed contour passed both canaries and published
8 of 16 canonical versions. Document 7 (XLSX) then hit the frozen 1 GiB
container memory limit and exited 137. The mandatory OOM stop prevented retry
or continuation; the failed document left no partial persisted state.

Restart durability, target backup/restore, research consumer and Wave 2 shadow
were not started. Wave 2 cutover, primary product cutover and Gate 3 remain
unauthorized pending a new explicit XLSX resource-policy decision.
