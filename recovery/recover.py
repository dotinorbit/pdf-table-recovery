#!/usr/bin/env python3
"""Reproduce three fixed pdfplumber boundary settings for one source PDF.

No source text or expected cell values are embedded. This is a file-specific
recipe, not an automatic boundary detector or a general table repair tool.
"""
import argparse
import hashlib
import json
from pathlib import Path

SOURCE_SHA256 = "0ea6b14d62ccf3778737482fccb4477f9994493635b6e18099025cfac7cb96aa"
# One-based physical PDF page, zero-based target row, boundary in PDF points.
PAGES = ((117, 16, 554.62), (201, 18, 546.47), (317, 14, 538.02))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SOURCE_SHA256:
        parser.error("Source hash differs from the selected reproduction")

    import pdfplumber

    args.output.mkdir(parents=True, exist_ok=True)
    summary = []
    with pdfplumber.open(args.source) as pdf:
        for number, target_row, bottom in PAGES:
            page = pdf.pages[number - 1]
            before = page.extract_table()
            after = page.extract_table({"explicit_horizontal_lines": [bottom]})
            for label, rows in (("before", before), ("after", after)):
                path = args.output / f"page{number}-{label}.json"
                path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
            summary.append({
                "physical_page_1based": number,
                "target_row_0based": target_row,
                "explicit_horizontal_line_pt": bottom,
                "before_rows": len(before or []),
                "after_rows": len(after or []),
                "whole_table_unchanged": before == after,
            })
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
