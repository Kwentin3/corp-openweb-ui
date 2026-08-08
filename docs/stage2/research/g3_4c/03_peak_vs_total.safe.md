# G3.4C peak versus total usage

Status: `LIVE_MEASURED`

Date: 2026-08-07

## Large CSV comparison

| Measure | Old one-shot | Six bounded chunks | Change |
| --- | ---: | ---: | ---: |
| peak input tokens | 215,810 | 44,459 | -171,351 (-79.399008%) |
| total input tokens | 215,810 | 222,962 | +7,152 (+3.314026%) |
| total output tokens | not used for comparison | 6,177 | n/a |
| total provider tokens | not used for comparison | 251,575 | n/a |
| total duration | not used for comparison | 149,124 ms | n/a |

The bounded route materially reduces the per-request peak. It does not reduce
total input: repeated fixed context and per-request framing make total input
slightly larger.

The exact dictionary and instruction occupied 24,156 repeated characters
across the six requests, or 6.834657% of serialized final model-input
characters. This is a character-accounting fact only; no dictionary token
share is claimed because provider usage does not expose token counts by input
component.

## Entire 12-request run

- input tokens: 382,779 total, 48,522 peak, 42,389.5 median;
- output tokens: 6,423 total;
- provider total tokens: 416,396;
- duration: 191,092 ms total;
- fixed dictionary plus instruction: 48,312 repeated characters, 8.245719%
  of serialized final model-input characters.

The current 60,000-character bound is assessed as `ADEQUATE_FOR_MVP`: every
near-bound request reached a provider terminal response, the large-document
peak fell sharply, and the only validation failure occurred on the smaller
compact request for an alias-format reason unrelated to size.
