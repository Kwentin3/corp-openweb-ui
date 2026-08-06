# Broker Reports DOC25 Brief

`CanonicalArtifactV1` and four format adapters are implemented behind shadow
flags using existing factories and ArtifactStore. Focused/regression checks are
green (`58 + 9`), and no provider/cropper rerun occurred.

Cutover is not ready: chunking, cross-run versions, atomic activation/rollback,
actual-corpus shadow, current DOC24 product regression and consumer migration
remain open. Legacy stays authoritative; no cleanup or Gate 3 work started.
