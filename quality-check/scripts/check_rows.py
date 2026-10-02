#!/usr/bin/env python3
"""Warn about a narrow full-row collapse signature in raw extraction arrays.

Input: one rectangular JSON table of strings or nulls, as returned by
pdfplumber.Table.extract(). No PDF access, page IDs, known labels, or repairs.
A missing warning is NOT a statement that the extraction is valid.
"""
import argparse
import json
import re
from pathlib import Path

VERSION = "0.1.0"
DECIMAL = re.compile(r"[+-]?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)\.[0-9]+")


def decimal_tokens(text):
    """Count standalone decimal tokens, preserving duplicates and their text."""
    return [token for token in text.split() if DECIMAL.fullmatch(token)]


def body_evidence(row):
    atoms = [value.strip() for value in row if isinstance(value, str)]
    decimals = sum(bool(DECIMAL.fullmatch(atom)) for atom in atoms)
    numbers_or_dashes = sum(bool(DECIMAL.fullmatch(atom)) or atom == "-" for atom in atoms)
    return decimals >= 2 and numbers_or_dashes >= 4


def check_table(rows):
    if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
        raise ValueError("Input must be one JSON array of row arrays")
    width = len(rows[0]) if rows else 0
    if any(len(row) != width for row in rows):
        raise ValueError("Ragged rows are outside this check's scope")
    if any(value is not None and not isinstance(value, str) for row in rows for value in row):
        raise ValueError("Keep raw values as strings or null; do not coerce numbers or blanks")

    body_rows = []
    candidates = []
    warnings = []
    for index, row in enumerate(rows):
        present = [(column, value) for column, value in enumerate(row) if value is not None]
        if width >= 4 and len(present) == 1 and present[0][1].strip():
            column, text = present[0]
            tokens = decimal_tokens(text)
            if len(body_rows) >= 2 and len(tokens) >= 3:
                disposition = "review_possible_collapsed_data_row"
                warning = {
                    "row_index_0based": index,
                    "code": disposition,
                    "message": "One populated slot holds multiple decimal tokens after multi-column numeric rows. Check the source layout; this may be a collapsed data row or legitimate merged text.",
                    "populated_column_0based": column,
                    "structural_null_slots": width - 1,
                    "embedded_decimal_tokens": tokens,
                    "preceding_numeric_row_indices_0based": list(body_rows),
                    "action": "Review source geometry or rendered PDF; do not split, fill, or accept this row automatically.",
                }
                warnings.append(warning)
            elif len(body_rows) < 2:
                disposition = "not_flagged_insufficient_prior_numeric_context"
            else:
                disposition = "not_flagged_fewer_than_three_decimal_tokens"
            candidates.append({
                "row_index_0based": index,
                "populated_column_0based": column,
                "decimal_token_count": len(tokens),
                "preceding_numeric_row_count": len(body_rows),
                "disposition": disposition,
            })
        if body_evidence(row):
            body_rows.append(index)

    return {
        "checker_version": VERSION,
        "status": "review_required" if warnings else "no_signature_found_not_validated",
        "row_count": len(rows),
        "column_count": width,
        "numeric_context_row_indices_0based": body_rows,
        "single_nonempty_slot_candidates": candidates,
        "warnings": warnings,
        "limits": "A narrow heuristic for decimal-valued tables with preserved structural nulls. No warning does not certify cell accuracy, completeness, or correct row boundaries.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", type=Path)
    args = parser.parse_args()
    try:
        result = check_table(json.loads(args.table.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
