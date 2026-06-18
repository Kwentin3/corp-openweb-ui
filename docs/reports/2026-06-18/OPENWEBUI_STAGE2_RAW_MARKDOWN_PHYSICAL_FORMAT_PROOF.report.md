# OpenWebUI Stage 2 Raw Markdown Physical Format Proof Report

## 1. Summary

This report answers the raw-markdown formatting concern raised after the
previous Stage 2 domain-boundary refine.

The concern was that several files looked physically compressed into very few
raw lines, which would make line-based diff and review ineffective.

I rechecked the current repository state against both:

- the working tree files;
- the committed git `HEAD` blobs.

The reported low line counts are not reproduced in current `HEAD`:

- `CONTRACT_BOUNDARIES.md` is not 14 raw lines; it is 170 lines in `HEAD`.
- `ADR-0004-stt-proxy-boundary.md` is not 7 raw lines; it is 191 lines in `HEAD`.
- `IMPLEMENTATION_GATES.md` is not 7 raw lines; it is 264 lines in `HEAD`.
- `README.md` is not 12 raw lines; it is 205 lines in `HEAD`.
- `DOMAIN_MAP.md` is not 17 raw lines; it is 534 lines in `HEAD`.
- `decisions/README.md` is not 3 raw lines; it is 54 lines in `HEAD`.

No source code, provider setup, runtime, compose/env/scripts or `.env` files
were read or changed.

## 2. Files checked

- `README.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/decisions/README.md`

## 3. Proof commands

Working tree line count and maximum line length:

```powershell
$files = @(
  'README.md',
  'docs/stage2/CONTRACT_BOUNDARIES.md',
  'docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md',
  'docs/stage2/IMPLEMENTATION_GATES.md',
  'docs/stage2/DOMAIN_MAP.md',
  'docs/stage2/decisions/README.md'
)

foreach ($f in $files) {
  $lines = Get-Content -LiteralPath $f -Encoding UTF8
  $max = 0
  $num = 0

  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i].Length -gt $max) {
      $max = $lines[$i].Length
      $num = $i + 1
    }
  }

  "$f`tWT_lines=$($lines.Count)`tmax_line=$max`tmax_line_no=$num"
}
```

Committed git `HEAD` blob line count:

```powershell
$files = @(
  'README.md',
  'docs/stage2/CONTRACT_BOUNDARIES.md',
  'docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md',
  'docs/stage2/IMPLEMENTATION_GATES.md',
  'docs/stage2/DOMAIN_MAP.md',
  'docs/stage2/decisions/README.md'
)

foreach ($f in $files) {
  $text = git show "HEAD:$f"
  $joined = ($text -join "`n")
  $lines = $text.Count
  $lf = ([regex]::Matches($joined, "`n")).Count

  "$f`tHEAD_lines=$lines`tjoined_LF=$lf"
}
```

Table scan for the checked files:

```powershell
rg -n "^\\|" README.md `
  docs/stage2/CONTRACT_BOUNDARIES.md `
  docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md `
  docs/stage2/IMPLEMENTATION_GATES.md `
  docs/stage2/DOMAIN_MAP.md `
  docs/stage2/decisions/README.md
```

Git tree status:

```powershell
git status -sb
git log --oneline --decorate -n 3
```

## 4. Working tree proof

Measured after the check:

| File | Working tree lines | Max line length | Max line number |
| ---- | -----------------: | --------------: | --------------: |
| `README.md` | 205 | 124 | 128 |
| `docs/stage2/CONTRACT_BOUNDARIES.md` | 170 | 82 | 73 |
| `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md` | 191 | 85 | 190 |
| `docs/stage2/IMPLEMENTATION_GATES.md` | 264 | 79 | 13 |
| `docs/stage2/DOMAIN_MAP.md` | 534 | 97 | 397 |
| `docs/stage2/decisions/README.md` | 54 | 91 | 5 |

Interpretation:

- the checked files are physically multi-line;
- maximum line lengths are reviewable;
- no checked file is a one-line or few-line raw markdown blob.

## 5. Git HEAD proof

Measured against committed `HEAD` blobs:

| File | HEAD lines | Joined LF count |
| ---- | ---------: | --------------: |
| `README.md` | 205 | 204 |
| `docs/stage2/CONTRACT_BOUNDARIES.md` | 170 | 169 |
| `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md` | 191 | 190 |
| `docs/stage2/IMPLEMENTATION_GATES.md` | 264 | 263 |
| `docs/stage2/DOMAIN_MAP.md` | 534 | 533 |
| `docs/stage2/decisions/README.md` | 54 | 53 |

Interpretation:

- the committed repository blob is also physically multi-line;
- the line breaks are present in git, not only in the local checkout;
- the current remote-tracked `origin/main` points at the same commit as local
  `main` during the check.

## 6. Table and raw review proof

The checked files do not contain markdown tables:

- `README.md`
- `docs/stage2/CONTRACT_BOUNDARIES.md`
- `docs/stage2/decisions/ADR-0004-stt-proxy-boundary.md`
- `docs/stage2/IMPLEMENTATION_GATES.md`
- `docs/stage2/DOMAIN_MAP.md`
- `docs/stage2/decisions/README.md`

The command returned no table rows for these checked files.

This matters because the previous problem was not just line count; wide tables
were also making raw review difficult. These specific files are now section- and
list-based.

## 7. Current commit proof

Current commit at check time:

```text
4fb9939 (HEAD -> main, origin/main, origin/HEAD) docs: refine stage2 domain boundaries and formatting
```

Working tree at the beginning of this proof pass:

```text
## main...origin/main
```

## 8. Conclusion

The specific raw-line-count problem described for the listed files is not
present in current `HEAD`.

The current Stage 2 docs are physically formatted for line-based review in the
checked files:

- headings are on separate lines;
- lists are separate lines;
- wide-table-only structure is not present in the checked files;
- root README is physically multi-line and has bounded line length;
- `CONTRACT_BOUNDARIES.md`, `ADR-0004`, `IMPLEMENTATION_GATES.md`,
  `DOMAIN_MAP.md` and decisions registry are multi-line documents in git.

If a viewer still reports very small line counts, the likely causes to check are:

- viewing an older commit before `4fb9939`;
- viewing a stale local checkout that has not pulled `origin/main`;
- using a command mode that intentionally reads the whole file as one string,
  such as `Get-Content -Raw`, instead of counting physical line breaks;
- viewing rendered Markdown rather than raw file content.

## 9. Next recommended step

Continue with:

`ADR-0004 STT Proxy Boundary review + inspection contract existing ffmpeg workflow artifact`.
