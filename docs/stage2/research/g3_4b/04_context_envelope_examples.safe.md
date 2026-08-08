# G3.4B privacy-safe structural examples

The values below are synthetic. Exact customer-bearing first/middle/last and
adjacent-boundary chunks are available in the private evidence manifest.

## Small document

When the complete projection is under the bound, its original Markdown is
returned unchanged as one `whole_document` chunk. No wrapper or repeated
context is added.

## Oversized table: first row group

```markdown
## Structural context (context only)

### Table

| row | column 1 | column 2 |
| --- | --- | --- |

## Target content

| [t001] 1 | [t002] Example header A | [t003] Example header B |
| [t004] 2 | [t005] Example value A  | [t006] Example value B  |
```

## Oversized table: following row group

```markdown
## Structural context (context only)

### Table

| row | column 1 | column 2 |
| --- | --- | --- |
| 1 | Example header A | Example header B |

## Target content

| [t007] 3 | [t008] Example value C | [t009] Example value D |
```

The repeated header is alias-free. `t001..t006` remain working targets only in
the first chunk; the next row starts with the next original aliases. Row ranges
are contiguous and non-overlapping.

## Workbook boundary

An existing sheet boundary is context, not a target-bearing request:

```markdown
## Structural context (context only)

--- Sheet break ---

### Table

| row | column 1 | column 2 |
| --- | --- | --- |

## Target content

| [t010] 1 | [t011] Example sheet header | [t012] Example amount |
```

Human review of the exact private cases confirmed that first, middle, last and
adjacent row-group chunks retain table identity, grid headings and the
canonical header row where applicable. No bare row was found.
