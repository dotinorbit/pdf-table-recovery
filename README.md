# PDF table recovery and a narrow row warning

Two small, AI-authored utilities based on [pdfplumber issue #1370](https://github.com/jsvine/pdfplumber/issues/1370): a fixed-coordinate recovery recipe for one PDF, and a separate output-only review check. Neither is a general parser or an upstream library fix.

## Public code and tests

- `recovery/recover.py` applies `explicit_horizontal_lines` at 554.62 points on physical page 117, 538.02 on page 317, and the existing 546.47 boundary on control page 201. It requires the exact source SHA-256 and writes before/after JSON locally
- `quality-check/scripts/check_rows.py` warns about one full-row-collapse signature in rectangular string/null arrays. It never reads a PDF or changes the input
- `quality-check/tests/test_check_rows.py` contains 19 synthetic contract tests, including deliberate false positives and false negatives. These tests contain no extracted PDF text
- `recovery/tests/test_recover.py` contains 13 synthetic CLI/path tests. Successful-path tests substitute an in-memory source hash and PDF reader; they do not validate PDF extraction

Run the public tests from this directory; no packages are required:

```sh
python3 -B -m unittest discover -s quality-check/tests -v
python3 -B -m unittest discover -s recovery/tests -v
```

Tested with Python 3.12.14. The checker and its 19 heuristic tests are unchanged from the original utility; `quality-check/frozen-rule.sha256` records the checker hash.

## Reproduce locally from the public source

Download the [public PDF attachment](https://github.com/user-attachments/files/27534369/RDTE.-.Vol.2.-.Budget.Activity.4B.pdf) separately as `../source.pdf`. Expected SHA-256: `0ea6b14d62ccf3778737482fccb4477f9994493635b6e18099025cfac7cb96aa`.

```sh
python3 -m venv ../pdf-table-recovery-venv
../pdf-table-recovery-venv/bin/python -m pip install -r recovery/requirements.txt
../pdf-table-recovery-venv/bin/python -B recovery/recover.py ../source.pdf --output ../pdf-table-recovery-rerun
python3 -B quality-check/scripts/check_rows.py ../pdf-table-recovery-rerun/page117-before.json
python3 -B quality-check/scripts/check_rows.py ../pdf-table-recovery-rerun/page117-after.json
```

On Windows use the environment's `Scripts/python.exe`. The before array should report `review_required`; the after array should report `no_signature_found_not_validated`. Both checker calls exit successfully: inspect the JSON status, not just the exit code. No source PDF, extracted fixture, screenshot or generated output is bundled.

### CLI input and output behavior

- The checker reads UTF-8 JSON without a byte-order mark (BOM), not CSV. Invalid input, missing files and invalid array shapes produce an error on stderr and exit 2. An empty file is invalid; an empty JSON array `[]` exits 0 with `no_signature_found_not_validated`
- Recovery rejects missing/unreadable source files, a mismatched source hash, source/output collisions, unresolvable output paths (including symlink loops) and output-directory setup errors with an error on stderr and exit 2. Successful recovery exits 0
- Recovery overwrites the six matching `page<number>-before.json` / `page<number>-after.json` files in `--output`; unrelated files are retained. Use a separate output directory to keep earlier results
- All six output paths are checked against the source before any output is written, including resolved symlink aliases and existing hard links. This is not a transaction or protection against concurrent filesystem changes: later extraction/write failures can still leave partial output

## Prior real-PDF observations, separate from the public tests

In the earlier, separately retained benchmark, the page-specific settings recovered 32 printed fields in two final-row fragments. All 72 targeted raw-slot checks passed and 900 untargeted slots were preserved, including the whole page 201 control. The checker flagged both known collapses, neither recovered version, and no rows on five preselected neighboring pages (78 rows).

Those observations cover one document; they are not reproduced by the 19 synthetic tests and do not establish general accuracy, precision or recall. The prior source-derived fixtures, expected cell values and benchmark reports are deliberately excluded. Running the recipe produces extraction arrays; it does not independently certify their accuracy.

## Limits

- Coordinates are tied to the exact source file. Page numbers are one-based physical PDF pages; target row indices are zero-based. Coordinates are PDF points measured from the top. See [pdfplumber's settings](https://github.com/jsvine/pdfplumber#table-extraction-settings)
- The recovery method covers three pages, with two affected rows and one control. It leaves page-fragment labels unjoined and adds an empty frame row on each affected page. No OCR, full-document validation or reconciliation is provided
- The warning requires at least four columns, exactly one nonempty non-null slot, at least two earlier numeric-context rows, and three whitespace-separated decimal tokens in the candidate. Numeric-context rows need at least four decimal-or-dash cells, including two decimal cells
- Integer-only cases, partial collapses, insufficient context and null-to-blank conversions are missed. A legitimate merged decimal note can be flagged. Context is not reset by section headers
- Preserve JSON null, empty string, literal dash and lexical zero. A missing warning is not evidence that an extraction is correct

Implementation, synthetic tests and documentation were generated by dot, an OpenAI-powered assistant. No affiliation or endorsement by pdfplumber or the source publisher is implied. The [MIT license](LICENSE) applies only to this project's original code, synthetic tests and documentation, to the extent rights apply. It does not license downloaded PDFs, locally generated source extracts or third-party dependencies. See [source and licensing notes](SOURCE_NOTICES.md).
