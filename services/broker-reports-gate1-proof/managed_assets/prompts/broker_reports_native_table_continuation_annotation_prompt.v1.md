You receive selected, consecutive pages from one source PDF after OCR.

Return a continuation link only when a physical table on the later page is a
direct continuation of a physical table on the immediately preceding page.
For each endpoint, use selected_page_position: zero-based position in this
selected-page sequence, and table_ordinal: one-based order of that page's
physical tables in the OCR material. Do not use, invent, or return a native
table id.
Do not infer, create, rename, merge, or repair tables, headers, rows, cells,
financial roles, instructional labels, or values.

Do not link a new table merely because it is nearby, looks similar, or has the
same number of columns. If the source does not establish a continuation,
return an empty continuation_links array.
