# G5.94 — Deterministic Parser vs Whole-Page VLM

Дата: 2026-08-18

Статус: `COMPLETE`

Архитектурный verdict: `HYBRID_JUSTIFIED`

## Результат

Простой Variant B доказал сильное преимущество в восстановлении видимой
табличной структуры, которую frozen Variant A не представляет как rows/columns:
на 53 заранее выбранных страницах у A квалифицированы 48 потерянных visual table
regions и 243 потерянные структурированные body rows. При этом буквальный текст
A остался доступен как lines/words с координатной provenance.

Variant B не доказал пригодность как универсальная замена A. В primary run он
вернул пригодный Markdown для 98/103 страниц, имел 5 terminal failures, а на
успешных страницах изменил 13 однозначно читаемых literal instances, включая
число и идентификаторы. Из восьми repeat pairs только шесть совпали и буквально,
и структурно. Поэтому `VARIANT_B_WINS` отвергнут.

Одновременно `VARIANT_A_WINS` тоже отвергнут: его нулевая provider-зависимость,
наблюдаемая literal fidelity и source-coordinate addressability не компенсируют
отсутствие видимой row/column structure на двух реальных layout families.

Данные показывают разные сильные стороны, а не компромисс «на всякий случай»:

- A — custody, literal/source refs и fail-closed deterministic representation;
- B — независимая whole-page visual transcription для layout classes, где
  внутренний PDF text/geometry не сохраняет человеческую структуру.

Это только архитектурный verdict. G5.94 не создаёт automatic A/B merge,
reconciliation, fallback activation или production routing.

## Frozen design

Manifest SHA-256:
`6b1c0b657ea356d71cf9af6a9ceb739833f8b2d82cff5a42f3d4ccc27f0d7917`.

Variant A использован через текущий public factory path с byte-frozen G5.93
owners. Проверены source hashes `full_source.py`, `pdf_layout.py`,
`table_projection.py` и двух focused test modules. Parser/config в ходе
эксперимента не менялись.

Variant B был заморожен до scored execution:

- input: один lossless full-page PNG, 150 DPI;
- model: exact `models/gemini-3.5-flash` через существующий provider seam;
- task: максимально дословная neutral Markdown transcription;
- response contract: один field `markdown`;
- temperature `0`, minimal thinking, output cap `16384`;
- parser output, Canonical, financial hints и expected answers отсутствуют;
- retry, provider failover, best-of-N, OCR verifier и ensemble отключены;
- после просмотра fidelity results prompt/model/config не менялись.

Qualification подтвердила exact model resolution, image input и structured
output. Первый успешный response попал в Windows alternate data stream из-за
двоеточия в имени slot. Он был восстановлен byte-exact и не отправлялся повторно;
изменена только filesystem-safe проекция имени следующих evidence files.

## Corpus и scoring

Использованы те же 4 real PDFs / 103 pages, что и в G5.93. Все 103 страницы
получили один primary B call. До provider execution были зафиксированы:

- development: 32 pages;
- untouched holdout: 21 pages;
- repeatability-only set: 8 pages.

Оставшиеся страницы участвовали в полной coverage/runtime/cost оценке. Scored
страницы не выбирались после просмотра B. Original page render был referee для
каждого засчитанного расхождения. Визуально неразличимые Latin/Cyrillic glyph
варианты не засчитывались как literal error.

G5.93 `77/77` относится к визуально подтверждённой candidate/admission
population. Whole-page comparator обнаружил дополнительные visual table regions,
для которых A вообще не создаёт table candidate. Они зафиксированы как frozen
limitation A, а не превращены в parser fix.

Error counts — qualified observed instances, а не character error rate.
Структурные категории намеренно перекрываются: одна потерянная таблица может
одновременно дать lost rows, lost header и lost column relation. Поэтому totals
между группами нельзя складывать в одну accuracy score.

## Fidelity matrix — 53 scored pages

| Error class | A | B |
|---|---:|---:|
| Lost text segments | 0 | 5 |
| Invented text segments | 0 | 0 |
| Changed literals | 0 | 13 |
| Lost signs | 0 | 0 |
| Changed decimal separators | 0 | 0 |
| Distorted dates | 0 | 0 |
| Changed currency symbols | 0 | 0 |
| Lost rows | 243 | 30 |
| Invented rows | 0 | 0 |
| Duplicated rows | 0 | 0 |
| Merged rows | 0 | 0 |
| Split rows | 0 | 0 |
| Lost column relations | 48 | 1 |
| Incorrect/lost headers | 48 | 1 |
| Lost tables | 48 | 1 |
| False tables | 0 | 0 |
| Broken section/paragraph order | 15 | 0 |

Нулевые значения означают «не найдено в квалифицированной выборке», а не
универсальную гарантию.

### Development / holdout

| Split | Arm | Literal-group errors | Structural-group errors |
|---|---|---:|---:|
| Development, 32 pages | A | 0 | 299 |
| Development, 32 pages | B | 13 | 0 |
| Holdout, 21 pages | A | 0 | 103 |
| Holdout, 21 pages | B | 5 | 33 |

Holdout сохранил тот же trade-off. Prompt tuning или повторный scored run после
его открытия не выполнялись.

### Source-truth disagreements

- На трёхстраничном визуально табличном document family A сохранил literals,
  но не создал ни одной table projection; B сохранил rows/columns/headers.
- На другом real statement family тот же результат повторился на обычных,
  continuation и subtotal pages.
- B девять раз одинаково изменил один security identifier на одной странице;
  это девять literal instances, а не девять независимых failure causes.
- Ещё на трёх страницах B изменил одно число и три security identifiers.
- Две prose pages завершились `RECITATION` без Markdown; одна table page
  завершилась `MAX_TOKENS`; ещё два primary failures были вне 53-page visual
  sample.
- На одной успешной странице B пропустил два footer segments.

## Addressability

| Capability | A | B |
|---|---:|---:|
| Page identity | yes | yes |
| Stable representation line identity | yes | yes |
| Source bbox/coordinate identity | yes | no |
| Source cell identity/path | yes | no |
| Lines with page/source/bbox refs | 5542/5542 | n/a |
| Cells with source paths | 18516/18516 | n/a |

B позволяет указать page и Markdown line, но не доказывает соответствие этой
строки конкретным source glyphs/bbox/cell. Специальный coordinate framework ради
победы B не строился.

## Repeatability

Восемь predeclared pages получили ровно один дополнительный run. Повторы не
участвовали в выборе output:

- terminal pairs: 8/8;
- both accepted: 7/8;
- exact matches: 6/7 accepted pairs;
- structural matches: 6/7 accepted pairs;
- selected outputs: 0;
- classification: `STOCHASTIC`.

## Runtime, tokens и provider cost

| Metric | A | B primary |
|---|---:|---:|
| Pages | 103 | 103 |
| Successful representations | 103 | 98 |
| Runtime total | 128.3 s frozen G5.93 replay | 1304.587 s provider-duration sum |
| Runtime/page | ~1.25 s | 12.666 s mean / 9.902 s median |
| Provider calls/page | 0 | 1 |
| Input tokens | 0 | 125,968 |
| Output tokens | 0 | 221,926 |
| Total tokens | 0 | 347,894 |
| Network dependency | no | yes |
| Marginal provider cost | 0 | $2.186286 |

В текущем G5.94 harness подготовка A вместе с page rendering/persistence заняла
160.782 s; для чистого strategic comparison используется frozen parser-only
G5.93 timing 128.3 s. B primary оказался примерно в 10.2 раза медленнее по
последовательной сумме provider durations.

Все 111 calls, включая восемь repeats, потребили 370,606 tokens и стоили
$2.316684. Primary cost экстраполируется в $21.2261 на 1000 страниц при том же
page mix. Расчёт использует standard paid rates Gemini 3.5 Flash $1.50 / 1M
input tokens и $9.00 / 1M output tokens, проверенные 2026-08-18 по
[официальной таблице Google](https://ai.google.dev/gemini-api/docs/pricing).
Цена provider может измениться; local compute, storage, engineering labor и
будущая production observability в доллары не оценивались.

## Maintenance complexity / TCO

| Product-owned complexity | A frozen | B simple transcription |
|---|---:|---:|
| Table strategies | 2 | 0 new |
| Rejection classes | 11 | n/a |
| Named thresholds | 14 | 0 task thresholds |
| Local numeric/ratio decisions | ~23 | 0 |
| Threshold/ratio knob order | ~37 | 0 |
| Direct parser tests | 25 | 9 comparator tests |
| Known structural debt classes | 4 | n/a |
| Prompt contracts | 0 | 1 |
| Response fields | 0 | 1 |
| Markdown validation rules | 0 | 4 |
| New production runtime modules | 0 | 0 |
| New provider-specific owners | 0 | 0 |
| Observed B failure classes | n/a | 6 |

B действительно проще в поддерживаемой product logic: renderer и provider seam
уже существовали, а transcription contract один. Но эксперимент потребовал
1092-line local coordinator; это research harness, не доказанная production
architecture и не аргумент скрыть будущие operational costs.

Шесть observed B failure classes: recitation refusal, exhausted/no valid
response, max-output truncation, literal substitution, visible-segment omission
и stochastic Markdown structure. Внутренняя сложность модели не считается нашей,
но network/provider availability и model behavior входят в TCO.

## Архитектурное решение

`HYBRID_JUSTIFIED` выбран по данным:

1. A даёт нулевые наблюдаемые literal errors, 100% primary availability и
   полную coordinate provenance, но системно не сохраняет часть visual tables.
2. B резко лучше сохраняет именно visual structure, включая layouts вне A
   candidate population, но 4.85% primary pages не имеют результата, а critical
   literals меняются и на development, и на holdout.
3. Ошибки сторон относятся к разным слоям: A теряет representation structure,
   B теряет или меняет source truth и provenance.
4. B дешевле по нашей ingestion logic, но дороже по runtime, network dependency,
   stochasticity и marginal provider cost.

Следовательно, B не становится source truth автоматически и не заменяет A.
Архитектурно оправдано разделить роли/классы входа: A остаётся deterministic
custody/provenance baseline, B может давать независимую visual representation там,
где layout не представлен A. Конкретный routing/acceptance contract должен быть
отдельно спроектирован и доказан; G5.94 его не реализует и не разрешает field-level
reconciliation.

## Verification и границы

```text
Frozen manifest/hash checks: PASS
Same corpus: PASS (4 documents / 103 pages)
Primary B terminal slots: 103/103
Repeat B terminal slots: 8/8
Retry / failover / best-of-N / response selection: 0
Visual scored pages: 53 (32 development / 21 holdout)
Comparator tests: 9 passed
Ruff: PASS
Parser source changes: 0
Gate 3+ changes: 0
Semantic VLM work: 0
Production activation: false
Commit / push / PR / deploy: not performed
```

Private PDFs, page renders, raw text, model payloads and page-level review stay
под `local/`/private evidence вне Git. Tracked machine receipt содержит только
aggregates, hashes и safe operational metadata. Dirty user-owned work сохранён.

## Terminal

```text
PDF_INGESTION_A_B_COMPARISON_PROVEN
VARIANT_A_MATURE_BASELINE_FROZEN
VARIANT_B_WHOLE_PAGE_VISUAL_TRANSCRIPTION_PROVEN
SOURCE_FIDELITY_COMPARISON_PROVEN
LITERAL_FIDELITY_COMPARISON_PROVEN
STRUCTURAL_FIDELITY_COMPARISON_PROVEN
TOTAL_COST_OF_OWNERSHIP_COMPARISON_PROVEN
FINAL_RECOMMENDATION=HYBRID
PRODUCTION_ACTIVATION=false
NEXT_GOAL=DESIGN_GATE2_HYBRID_ROUTING_AND_ACCEPTANCE
```
