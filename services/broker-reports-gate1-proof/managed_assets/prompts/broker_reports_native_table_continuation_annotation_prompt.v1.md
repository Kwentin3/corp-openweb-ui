You receive selected, consecutive pages from one source PDF after OCR.

Return a continuation link only when a physical table on the later page is a
direct continuation of a physical table on the immediately preceding page.
Use only the exact page_index and table_id values present in the OCR material.
Do not infer, create, rename, merge, or repair tables, headers, rows, cells,
financial roles, instructional labels, or values.

Do not link a new table merely because it is nearby, looks similar, or has the
same number of columns. If the source does not establish a continuation,
return an empty continuation_links array.
