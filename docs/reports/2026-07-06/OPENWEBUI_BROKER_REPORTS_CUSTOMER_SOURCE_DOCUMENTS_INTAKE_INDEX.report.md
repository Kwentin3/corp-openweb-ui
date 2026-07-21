# OpenWebUI Broker Reports Customer Source Documents Intake Index Report

Status: CUSTOMER_SOURCE_DOCUMENTS_SAFE_INDEX_READY
Date: 2026-07-06
Scope: Stage 2 Broker Reports / XLS NDFL document intake and classification

## 1. Safety Boundary

- Source documents were not copied into the repository.
- Source documents were not committed.
- The local source folder path is intentionally not printed in this report.
- Raw filenames and relative paths are not printed; safe artifacts use keyed hashes.
- Full local paths are stored only in the ignored private local registry.
- No tax calculation, declaration generation, XLS/XLSX generation or OpenWebUI upload was performed.
- No mass OCR was performed.
- No full financial operation rows were exported.

## 2. Outputs

- Safe registry: `docs/stage2/domain/BROKER_REPORTS_CUSTOMER_SOURCE_DOCUMENTS_INDEX.v0.safe.json`
- Private registry and working script: retained only in the ignored private
  evidence root; no local path is published.

## 3. Corpus Summary

- Files indexed: 63
- Container formats: {'csv': 2, 'pdf': 31, 'txt': 4, 'xlsx': 2, 'zip': 24}
- Readability: {'yes': 63}
- Taxonomy classes: {'calculation_template': 2, 'dividends_report': 7, 'fees_report': 2, 'operations_table': 8, 'source_broker_report': 7, 'tax_base_calculation': 5, 'unknown_or_needs_review': 32}

## 4. Document Registry Matrix

| document_id | container | ext | size_bytes | modified_time_msk | sha256_prefix | class | source | methodology | knowledge | relevance | technical_summary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| brdoc_001_b874d956e33a | csv | .csv | 212844 | 2026-04-27T17:47:10.077573+03:00 | b874d956e33ad438 | operations_table | yes | no | after_review | source_fact | encoding=utf_8; delimiter=','; rows=1342; columns=4; table=yes |
| brdoc_002_1c6582477921 | pdf | .pdf | 329193 | 2026-04-27T17:47:13.946143+03:00 | 1c6582477921cc51 | operations_table | yes | no | after_review | source_fact | pages=33; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_003_be6168a763cd | csv | .csv | 198734 | 2026-04-27T17:47:13.581098+03:00 | be6168a763cd41ba | operations_table | yes | no | after_review | source_fact | encoding=utf_8; delimiter=','; rows=1255; columns=4; table=yes |
| brdoc_004_66a3087cb242 | pdf | .pdf | 307535 | 2026-04-27T17:47:13.762613+03:00 | 66a3087cb242ace4 | operations_table | yes | no | after_review | source_fact | pages=32; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_005_f68f7ac26a26 | pdf | .pdf | 352035 | 2026-04-22T18:15:50.218192+03:00 | f68f7ac26a268379 | operations_table | yes | no | after_review | source_fact | pages=39; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_006_7cfd297786cc | pdf | .pdf | 479750 | 2026-04-22T17:15:52.826458+03:00 | 7cfd297786cc91cb | source_broker_report | yes | no | after_review | source_fact | pages=65; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_007_bdc1038fdd93 | pdf | .pdf | 440661 | 2026-04-22T17:16:05.713799+03:00 | bdc1038fdd9334c1 | dividends_report | yes | no | after_review | source_fact | pages=60; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_008_4790d8487926 | xlsx | .xlsx | 912502 | 2026-04-22T18:36:36.612067+03:00 | 4790d8487926c698 | calculation_template | no | conditional | after_review | methodology | sheets=20; formulas=yes; hidden=0; role=calculation_template_or_output_artifact |
| brdoc_009_0a261afe6f0e | xlsx | .xlsx | 808421 | 2026-04-22T18:14:34.542687+03:00 | 0a261afe6f0ee388 | calculation_template | no | conditional | after_review | methodology | sheets=20; formulas=yes; hidden=0; role=calculation_template_or_output_artifact |
| brdoc_010_665b45748e01 | pdf | .pdf | 177994 | 2026-04-28T19:04:27.938376+03:00 | 665b45748e01591b | fees_report | yes | no | after_review | source_fact | pages=14; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_011_6f36b1030270 | pdf | .pdf | 385629 | 2026-04-28T19:04:39.716307+03:00 | 6f36b10302703071 | dividends_report | yes | no | after_review | source_fact | pages=49; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_012_7564b3bc1353 | zip | .zip | 83655 | 2026-03-27T16:48:39.672310+03:00 | 7564b3bc135313b4 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_013_c1721c84d107 | zip | .zip | 91862 | 2026-03-27T16:48:21.785416+03:00 | c1721c84d1079075 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_014_701797dcb627 | zip | .zip | 84307 | 2026-03-27T16:48:29.590948+03:00 | 701797dcb6276866 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_015_3a1b9214292c | zip | .zip | 89662 | 2026-03-27T16:48:34.870610+03:00 | 3a1b9214292c6027 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_016_573d9c44da70 | zip | .zip | 83531 | 2026-03-27T16:48:26.194937+03:00 | 573d9c44da701f3d | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_017_8390e02699f1 | zip | .zip | 83915 | 2026-03-27T16:46:55.058611+03:00 | 8390e02699f12084 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_018_68c0f4c2e764 | zip | .zip | 87316 | 2026-03-27T16:47:01.658710+03:00 | 68c0f4c2e764bcd3 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_019_e20f86bce4cb | zip | .zip | 84508 | 2026-03-27T16:46:50.696042+03:00 | e20f86bce4cbea59 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_020_acc1c591d660 | zip | .zip | 83953 | 2026-03-27T16:46:46.215530+03:00 | acc1c591d6606972 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_021_3d59bcf9fda4 | zip | .zip | 84129 | 2026-03-27T16:46:41.950521+03:00 | 3d59bcf9fda4ce77 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_022_996b292d1408 | zip | .zip | 85280 | 2026-03-27T16:46:34.707235+03:00 | 996b292d1408dfc7 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_023_e16dae9c454b | zip | .zip | 86394 | 2026-03-27T16:46:29.366433+03:00 | e16dae9c454be3f4 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_024_eac67250999e | zip | .zip | 84350 | 2026-03-27T16:46:23.602175+03:00 | eac67250999edfa4 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_025_0f617e48b33f | zip | .zip | 84997 | 2026-03-27T17:58:08.445319+03:00 | 0f617e48b33fdce1 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_026_60865da0b67a | zip | .zip | 86712 | 2026-03-27T17:59:07.292251+03:00 | 60865da0b67a0cbb | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_027_73b9943d9a8a | zip | .zip | 85565 | 2026-03-27T17:57:57.832624+03:00 | 73b9943d9a8a6a96 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_028_703a6fd74179 | zip | .zip | 84556 | 2026-03-27T17:58:03.495650+03:00 | 703a6fd741795caa | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_029_355edae532a6 | zip | .zip | 86232 | 2026-03-27T17:58:24.735866+03:00 | 355edae532a612d8 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_030_e2ff5374db45 | zip | .zip | 86986 | 2026-03-27T17:58:15.461270+03:00 | e2ff5374db45d52a | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_031_7f469bb3e17d | zip | .zip | 83933 | 2026-03-27T17:58:30.895293+03:00 | 7f469bb3e17dda2d | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_032_e0ac2210dba5 | zip | .zip | 84118 | 2026-03-27T17:58:39.209577+03:00 | e0ac2210dba5165f | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_033_3b540b094d7a | zip | .zip | 85152 | 2026-03-27T17:58:42.642055+03:00 | 3b540b094d7a13ac | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_034_0d1652d9303e | zip | .zip | 84113 | 2026-03-27T17:58:47.996792+03:00 | 0d1652d9303ec153 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_035_9419913a504a | zip | .zip | 90406 | 2026-03-27T18:40:03.222990+03:00 | 9419913a504a8610 | unknown_or_needs_review | conditional | conditional | after_review | none | members=3; exts={'.p7s': 1, '.pdf': 1, '.xml': 1}; unpack=conditional |
| brdoc_036_f1995ee6a6fa | pdf | .pdf | 1125818 | 2026-03-03T14:54:35.864669+03:00 | f1995ee6a6fad51d | unknown_or_needs_review | conditional | conditional | after_review | none | pages=6; text_layer=no; raster=no; tables=unknown; ocr=no |
| brdoc_037_8c0fea99b1db | pdf | .pdf | 1008713 | 2026-02-04T09:22:06.667666+03:00 | 8c0fea99b1dbc928 | fees_report | yes | no | after_review | source_fact | pages=18; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_038_d603a3988ee0 | pdf | .pdf | 939322 | 2026-02-04T09:21:21.082899+03:00 | d603a3988ee0661c | source_broker_report | yes | no | after_review | source_fact | pages=14; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_039_ca35351f1c5f | pdf | .pdf | 895433 | 2026-02-04T09:23:30.350531+03:00 | ca35351f1c5fe0fd | dividends_report | yes | no | after_review | source_fact | pages=17; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_040_ce1cdfa4d4eb | pdf | .pdf | 564401 | 2026-02-04T09:19:17.855814+03:00 | ce1cdfa4d4eb09ec | operations_table | yes | no | after_review | source_fact | pages=6; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_041_39227188fb1c | pdf | .pdf | 95979 | 2026-04-09T16:38:15.827784+03:00 | 39227188fb1c8e45 | unknown_or_needs_review | conditional | conditional | after_review | none | pages=28; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_042_51ccbbd65039 | pdf | .pdf | 145527 | 2026-04-09T16:39:24.092971+03:00 | 51ccbbd650392772 | unknown_or_needs_review | conditional | conditional | after_review | none | pages=33; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_043_4d8ee8777b23 | pdf | .pdf | 117610 | 2026-04-09T16:43:35.388237+03:00 | 4d8ee8777b238820 | unknown_or_needs_review | conditional | conditional | after_review | none | pages=33; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_044_74e5de8408a8 | pdf | .pdf | 745927 | 2026-01-30T15:44:41.890510+03:00 | 74e5de8408a87508 | operations_table | yes | no | after_review | source_fact | pages=18; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_045_0c44a95cc671 | pdf | .pdf | 805548 | 2026-02-02T12:26:06.613078+03:00 | 0c44a95cc67129d0 | dividends_report | yes | no | after_review | source_fact | pages=19; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_046_0c44a95cc671 | pdf | .pdf | 805548 | 2026-02-02T12:26:06.613078+03:00 | 0c44a95cc67129d0 | dividends_report | yes | no | after_review | source_fact | pages=19; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_047_6137e019ea76 | pdf | .pdf | 475565 | 2026-02-09T17:14:28.988789+03:00 | 6137e019ea76c86f | dividends_report | yes | no | after_review | source_fact | pages=12; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_048_62db60cb2b17 | pdf | .pdf | 588617 | 2026-02-09T17:12:20.662308+03:00 | 62db60cb2b1719d5 | operations_table | yes | no | after_review | source_fact | pages=16; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_049_6137e019ea76 | pdf | .pdf | 475565 | 2026-01-30T15:47:40.138226+03:00 | 6137e019ea76c86f | dividends_report | yes | no | after_review | source_fact | pages=12; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_050_00eefe9ce421 | pdf | .pdf | 424711 | 2026-02-03T16:53:28.803727+03:00 | 00eefe9ce4213181 | tax_base_calculation | conditional | conditional | after_review | review_output | pages=2; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_051_d33849e406b9 | pdf | .pdf | 350046 | 2026-02-03T16:54:02.451449+03:00 | d33849e406b9015c | tax_base_calculation | conditional | conditional | after_review | review_output | pages=1; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_052_41b5a29f3de2 | pdf | .pdf | 362484 | 2026-02-03T16:54:40.783525+03:00 | 41b5a29f3de2a206 | tax_base_calculation | conditional | conditional | after_review | review_output | pages=2; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_053_9ad0d7e43346 | pdf | .pdf | 422267 | 2026-02-03T16:57:26.971319+03:00 | 9ad0d7e43346e301 | tax_base_calculation | conditional | conditional | after_review | review_output | pages=3; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_054_79af73d5be78 | pdf | .pdf | 176458 | 2026-03-18T12:25:25.249432+03:00 | 79af73d5be78df44 | source_broker_report | yes | no | after_review | source_fact | pages=6; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_055_21c85fa3ff06 | txt | .html | 51109 | 2026-02-11T12:37:11.237421+03:00 | 21c85fa3ff06b9ca | source_broker_report | yes | no | after_review | source_fact | encoding=utf_8; rows=316; table=conditional |
| brdoc_056_1fb1c0744eb0 | txt | .html | 49219 | 2026-02-11T12:35:40.738579+03:00 | 1fb1c0744eb0b84b | source_broker_report | yes | no | after_review | source_fact | encoding=utf_8; rows=330; table=conditional |
| brdoc_057_8b29ff7a464f | txt | .html | 57949 | 2026-02-11T12:28:39.572095+03:00 | 8b29ff7a464f8e72 | source_broker_report | yes | no | after_review | source_fact | encoding=utf_8; rows=397; table=conditional |
| brdoc_058_cee60e388015 | txt | .html | 60755 | 2026-02-11T12:20:17.031653+03:00 | cee60e38801516af | source_broker_report | yes | no | after_review | source_fact | encoding=utf_8; rows=543; table=conditional |
| brdoc_059_b9bca7e6e44d | pdf | .pdf | 41214 | 2026-03-03T14:55:05.114488+03:00 | b9bca7e6e44dbf12 | tax_base_calculation | conditional | conditional | after_review | review_output | pages=6; text_layer=yes; raster=no; tables=unknown; ocr=no |
| brdoc_060_e69ef2fa1cb2 | pdf | .pdf | 864564 | 2026-04-09T17:14:35.860706+03:00 | e69ef2fa1cb27a1f | unknown_or_needs_review | conditional | conditional | after_review | none | pages=1; text_layer=no; raster=yes; tables=unknown; ocr=yes |
| brdoc_061_aeaff2e070aa | pdf | .pdf | 185528 | 2026-03-23T14:47:38.829496+03:00 | aeaff2e070aa580e | unknown_or_needs_review | conditional | conditional | after_review | none | pages=1; text_layer=no; raster=yes; tables=unknown; ocr=yes |
| brdoc_062_161065e246ac | pdf | .pdf | 185360 | 2026-03-23T14:47:43.025643+03:00 | 161065e246ac2e1c | unknown_or_needs_review | conditional | conditional | after_review | none | pages=1; text_layer=no; raster=yes; tables=unknown; ocr=yes |
| brdoc_063_510b999b1914 | pdf | .pdf | 190439 | 2026-03-23T14:47:40.350134+03:00 | 510b999b19145116 | unknown_or_needs_review | conditional | conditional | after_review | none | pages=1; text_layer=no; raster=yes; tables=unknown; ocr=yes |

## 5. Case Groups

### case_group_001

- probable_broker_or_role: `BCS`
- probable_tax_years: `unknown`
- account_marker_hash: `unknown`
- document_ids: `brdoc_013_c1721c84d107, brdoc_023_e16dae9c454b, brdoc_025_0f617e48b33f, brdoc_037_8c0fea99b1db, brdoc_038_d603a3988ee0, brdoc_039_ca35351f1c5f, brdoc_040_ce1cdfa4d4eb, brdoc_050_00eefe9ce421, brdoc_051_d33849e406b9, brdoc_052_41b5a29f3de2, brdoc_053_9ad0d7e43346`
- document_class_counts: `{'dividends_report': 1, 'fees_report': 1, 'operations_table': 1, 'source_broker_report': 1, 'tax_base_calculation': 4, 'unknown_or_needs_review': 3}`
- probable_currencies: `unknown`
- probable_countries: `Cyprus, Russia`
- readiness: `needs_review`
- missing_or_blocking_items: `currency/rate source or methodology, withholding/foreign tax source if in scope, customer-approved methodology`

### case_group_002

- probable_broker_or_role: `Interactive Brokers / IBKR`
- probable_tax_years: `unknown`
- account_marker_hash: `unknown`
- document_ids: `brdoc_001_b874d956e33a, brdoc_002_1c6582477921, brdoc_003_be6168a763cd, brdoc_004_66a3087cb242, brdoc_005_f68f7ac26a26, brdoc_006_7cfd297786cc, brdoc_008_4790d8487926, brdoc_009_0a261afe6f0e, brdoc_044_74e5de8408a8, brdoc_047_6137e019ea76, brdoc_049_6137e019ea76, brdoc_054_79af73d5be78, brdoc_055_21c85fa3ff06, brdoc_056_1fb1c0744eb0, brdoc_057_8b29ff7a464f, brdoc_058_cee60e388015`
- document_class_counts: `{'calculation_template': 2, 'dividends_report': 2, 'operations_table': 6, 'source_broker_report': 6}`
- probable_currencies: `unknown`
- probable_countries: `Russia, US`
- readiness: `needs_review`
- missing_or_blocking_items: `currency/rate source or methodology, fees/commissions source if in scope, withholding/foreign tax source if in scope, customer-approved methodology`

### case_group_003

- probable_broker_or_role: `Otkritie`
- probable_tax_years: `unknown`
- account_marker_hash: `unknown`
- document_ids: `brdoc_007_bdc1038fdd93, brdoc_011_6f36b1030270, brdoc_034_0d1652d9303e`
- document_class_counts: `{'dividends_report': 2, 'unknown_or_needs_review': 1}`
- probable_currencies: `unknown`
- probable_countries: `unknown`
- readiness: `needs_review`
- missing_or_blocking_items: `currency/rate source or methodology, fees/commissions source if in scope, withholding/foreign tax source if in scope, customer-approved methodology`

### case_group_004

- probable_broker_or_role: `Sber`
- probable_tax_years: `unknown`
- account_marker_hash: `unknown`
- document_ids: `brdoc_018_68c0f4c2e764, brdoc_019_e20f86bce4cb, brdoc_030_e2ff5374db45, brdoc_059_b9bca7e6e44d`
- document_class_counts: `{'tax_base_calculation': 1, 'unknown_or_needs_review': 3}`
- probable_currencies: `unknown`
- probable_countries: `Russia`
- readiness: `partial`
- missing_or_blocking_items: `none listed by intake heuristics`

### case_group_005

- probable_broker_or_role: `VTB`
- probable_tax_years: `unknown`
- account_marker_hash: `unknown`
- document_ids: `brdoc_015_3a1b9214292c, brdoc_045_0c44a95cc671, brdoc_046_0c44a95cc671, brdoc_048_62db60cb2b17`
- document_class_counts: `{'dividends_report': 2, 'operations_table': 1, 'unknown_or_needs_review': 1}`
- probable_currencies: `unknown`
- probable_countries: `Russia`
- readiness: `needs_review`
- missing_or_blocking_items: `currency/rate source or methodology, fees/commissions source if in scope, withholding/foreign tax source if in scope, customer-approved methodology`

### case_group_006

- probable_broker_or_role: `unknown`
- probable_tax_years: `unknown`
- account_marker_hash: `unknown`
- document_ids: `brdoc_010_665b45748e01, brdoc_012_7564b3bc1353, brdoc_014_701797dcb627, brdoc_016_573d9c44da70, brdoc_017_8390e02699f1, brdoc_020_acc1c591d660, brdoc_021_3d59bcf9fda4, brdoc_022_996b292d1408, brdoc_024_eac67250999e, brdoc_026_60865da0b67a, brdoc_027_73b9943d9a8a, brdoc_028_703a6fd74179, brdoc_029_355edae532a6, brdoc_031_7f469bb3e17d, brdoc_032_e0ac2210dba5, brdoc_033_3b540b094d7a, brdoc_035_9419913a504a, brdoc_036_f1995ee6a6fa, brdoc_041_39227188fb1c, brdoc_042_51ccbbd65039, brdoc_043_4d8ee8777b23, brdoc_060_e69ef2fa1cb2, brdoc_061_aeaff2e070aa, brdoc_062_161065e246ac, brdoc_063_510b999b1914`
- document_class_counts: `{'fees_report': 1, 'unknown_or_needs_review': 24}`
- probable_currencies: `unknown`
- probable_countries: `unknown`
- readiness: `needs_review`
- missing_or_blocking_items: `currency/rate source or methodology, withholding/foreign tax source if in scope, customer-approved methodology`

## 6. Proof Workflow Readiness

- The package is indexed and can be referenced by `document_id` without exposing filenames.
- Source-evidence candidates still require customer/sample approval before knowledge loading or source-fact extraction.
- ZIP archives require an explicit unpack/review step before contained documents can become source evidence.
- Methodology remains required before any tax-base treatment, currency conversion, withholding treatment or declaration candidate assertion.
- This report is an intake artifact only; it does not claim tax correctness or filing readiness.

## 7. Status

```text
CUSTOMER_SOURCE_DOCUMENTS_SAFE_INDEX_READY
CUSTOMER_DOCUMENTS_NOT_COMMITTED
PRIVATE_PATHS_LOCAL_ONLY
SOURCE_FACT_EXTRACTION_NOT_STARTED
CUSTOMER_METHODOLOGY_REQUIRED
READY_FOR_SAFE_PROOF_WORKFLOW_REFERENCING
```
