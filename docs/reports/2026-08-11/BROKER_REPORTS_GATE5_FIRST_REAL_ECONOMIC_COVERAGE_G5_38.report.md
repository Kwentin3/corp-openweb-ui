# G5.38 — First Real Economic Coverage Loop

Date: 2026-08-11

Terminal status: `STRATEGIC_STOP`

## What landed

- The existing PDF intake now rejects malformed regions individually while
  retaining independent valid regions; strict all-or-nothing validation is
  still available and invalid coordinates are never repaired or guessed.
- The financial semantic profile was qualified against one official public PDF:
  13 valid regions, two rejected, four accepted monetary tables, nine left
  unsupported, zero provider retry/merge/repair.
- Gate 3 demonstrated the first real purchase/transaction-charge coverage:
  two complete purchases and two complete transaction charges, paired by exact
  canonical annotation target.
- `Gate5RelatedSecuritiesEventsRuntimeFactory.create` proves only an exact
  whole-quantity purchase/charge/disposal relation. Purchase-only,
  unrelated-charge and ambiguous-group cases fail closed.
- The existing securities-disposal Tax Model consumes the relation without
  creating user-supplied supplemental facts. The previous supplemental path is
  unchanged.
- A controlled synthetic disposal fixture is explicitly marked synthetic and
  is not attributed to the public report or its publisher.

## Verification

Targeted regression: `60 passed`. It covers the new relation, negative cases,
Tax Model integration, G5.35 XML/XSD, G5.36 product adapter, G5.37 coverage,
PDF region rejection, semantic migration and generated bundle parity.

Final deployed bundle SHA-256:
`66ffc63e0a2447a3927b9d06925217291860fd9c2ba7f871a513878fd273f747`.

The final OpenWebUI proof used native authentication, upload, chat and the
stable product pipe. Purchase-only produced no XML. The controlled disposal
turn stopped with `gate5_related_events_purchase_missing`; no allocation, Tax
Model or XML was created. The staging function, valves and model ACL were then
restored successfully.

## Exact blocker

In the one final clean official-PDF inference, all four financial labels were
present but all required role bindings were `missing`. A prior bounded
qualification turn had complete bindings, but its private authenticated user
and case were removed during normal cleanup. Reusing those facts across a new
user/case would violate custody; repeating the same official inference would
be best-of-N. The honest G5.38 result is therefore `STRATEGIC_STOP`.

The next permitted work is only a G5.38 continuation that binds Gate 3 role
labeling deterministically to accepted semantic rows. G5.39 is not authorized.

Official/public references used for the bounded methodology and document
interpretation:

- [Tax Code Article 214.1 official locator](https://pravo.gov.ru/proxy/ips/?docbody=&nd=102067058)
- [FNS-hosted Federal Law No. 281-FZ](https://www.nalog.gov.ru/html/docs/281_fz.rtf)
- [T-Bank broker-report document guide](https://www.tbank.ru/invest/help/educate/tax-issues/self-pay/declaration-documents/)
- [T-Bank broker-report reading guide](https://www.tbank.ru/invest/help/educate/broker-report/about/read-n-get/)
