# Broker Reports Gate 1 — Positive Holdout Availability Audit

Date: 2026-07-19

Profile: `supported_broker_pdf_neutral_table_profile_v1`

Profile source commit: `b2d4592`

Audit result: `NO_ELIGIBLE_POSITIVE_HOLDOUT_FOUND`

Engineering status: `NOT_CLOSED`

## Purpose and eligibility boundary

This was a second, independent availability audit after implementation and actual-corpus proof. The profile remained frozen. No selection rule, reconstruction rule, validator, fixture, or expected output was changed during the search.

An eligible positive holdout had to be a genuine, previously unseen PDF from the same intended PJSC Sberbank broker-report template/family. It also had to be lawfully public or explicitly accepted for this proof and available as original PDF bytes. The following were rejected by design:

- the tuning document or a copy of it;
- screenshots, crops, or a PDF assembled from images;
- synthetic or redrawn reports;
- a report from another broker or a materially different Sber document family;
- a court exhibit, forum upload, or file containing customer data without a clear public-example provenance.

## Search contours and results

| Contour | Evidence found | Eligible PDF result |
| --- | --- | ---: |
| Accepted source roots and wider local PDF inventory | No second same-family source beyond the tuning material | 0 |
| Official Sber and SberCIB pages | Two explanatory articles reproduce anonymized report fragments as images and confirm the relevant table family | 0 |
| Rendered Sber Sova article and raw page source | Relevant assets are PNG/JPG storage objects; the page contains no PDF reference | 0 |
| Official-domain and general web search | Exact report title, distinctive section-heading combinations, template/form terms, and PDF filters returned articles, regulations, unrelated reports, or references to reports | 0 |
| Public GitHub code search | Exact Sber report title and distinctive heading combinations returned no matching source | 0 |
| Public archive URL inventory probe | No archived `www.sberbank.ru/*broker*.pdf` object was returned by the bounded PDF query | 0 |
| Third-party and litigation references | References prove that Sber broker reports exist, but no lawful sanitized original same-family PDF was established | 0 |

The strongest public template evidence is the Sber Sova article [How to read broker reports and why they are needed](https://sbersova.ru/sections/invest/kak-chitat-otchyoty-brokera-i-dlya-chego-oni-nuzhny). It labels example images as fragments of a PJSC Sberbank broker report and describes the same section family, but provides images rather than original PDF bytes.

The SberCIB article [How to read a broker report for a REPO placement](https://sbercib.ru/publication/kak-chitat-otchet-brokera-esli-kompaniya-razmestila-dengi-v-repo) independently shows several tables from a Sber report, again only as image fragments. A historical public memo [Broker service memo](https://sber-info.ru/wp-content/uploads/2017/11/broker_pamyatka.pdf) states that broker reports are delivered in PDF form, but is not itself a broker report.

No potentially personal third-party report was downloaded or added to the repository. No screenshot was converted to PDF. No candidate was run through the maintained path because no candidate met the byte-level provenance and family criteria.

## Determination

The positive holdout remains `NOT_RUN`, not failed and not passed. The exact unavailable input is one genuine, previously unseen, same-family Sber broker-report PDF with acceptable provenance.

The negative out-of-profile holdout, actual-corpus 14/14 canonicalization, deterministic replay, zero-provider proof, Gate 2 package accounting, and performance proof remain valid. They do not establish same-family generalization by themselves.

Stage deployment and live parity remain intentionally gated. The next valid action is to obtain an eligible PDF without changing the frozen profile, then run the maintained path twice and complete source-to-canonical operator review. Increasing a timeout, widening the profile, or manufacturing a document would not close this evidence gap.
