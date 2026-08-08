# G3.4A — Safe table expansion examples

These examples contain no customer values. Exact human-readable excerpts are
kept in the private bundle outside Git.

## Renderer shape

```text
| row | column 1 | column 2 |
| --- | --- | --- |
| [row-alias] 1 | [cell-alias] VALUE | [cell-alias] VALUE |
```

For every canonical cell physically present in `content.cells`, the renderer
adds one cell alias. For every row containing at least one such cell, it also
adds one row alias. Missing positions inside the printed rectangle remain blank
and receive no alias. A physically present cell whose displayed value is blank
still receives an alias.

## Measured examples

| Shape | Tables | Largest table rows × columns | Actual cells | Missing rectangle positions | Explicit empty actual cells | Row + cell aliases on same rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| compact HTML | 12 | 17 × 18 | 244 | 62 | 33 | 17/17 rows with cells |
| large CSV | 1 | 1,255 × 17 | 12,863 | 8,472 | 922 | 1,255/1,255 rows with cells |
| REPO XLSX | 20 | 1,369 × 15 | 13,185 | 7,350 | 13,158 | 1,015/1,015 rows with cells |

Across all REPO tables there are 153,352 actual cell aliases, 29,145 row
aliases, 39,499 explicitly empty aliased cells and 134,222 unaliased missing
rectangle positions.

The largest REPO table illustrates why “empty” must be interpreted carefully:
the canonical shape contains many physical cells with no displayed value. The
projection does not invent values, but still spends addressability on them.
Suppressing only the alias markup would preserve the blank cell and its
coordinate in the rendered rectangle; whether losing a backend target for that
blank is acceptable remains a contract-review question.

## Repetition

The large CSV has 10 rows participating in five repeated exact row signatures.
The largest REPO table has 1,363 rows participating in one repeated signature,
driven by blank structure. No selected table repeated its exact header row.
These are source/canonical observations, not proof that the renderer duplicated
business content. Removing repeated rows or headers would therefore be a
semantic/source decision, not a safe renderer cleanup.
