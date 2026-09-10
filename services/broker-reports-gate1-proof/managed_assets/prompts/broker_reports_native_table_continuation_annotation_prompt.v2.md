You receive selected, consecutive pages from one source PDF after OCR.

Each physical table in the OCR Markdown has a link placeholder such as
`[...](tbl-3.html)`. For each endpoint, return `selected_page_position` as its
zero-based position in the selected-page sequence and `markdown_table_target`
as the exact link target copied from that page's OCR Markdown. Do not count
tables. Do not invent, rename, or return another identifier.

Return a continuation link only when a physical table on the later page is the
direct continuation of a physical table on the immediately preceding page.
The pages must be adjacent, and the later rows must continue the same visible
section and table schema: compatible column meanings, order, row pattern,
value types and, where present, identifiers or sequence.

A repeated header is helpful but is not required. A later table may begin with
data rows. A headerless later table alone is not enough. Do not link it to a
nearby but distinct table or section.

Do not infer, create, rename, merge, or repair tables, headers, rows, cells,
financial roles, instructional labels, or values. A new title, section,
subject, explanatory block, or reset means a distinct table. If the evidence
is not unique, return an empty continuation_links array.
