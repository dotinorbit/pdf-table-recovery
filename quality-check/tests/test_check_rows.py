"""Small executable contract tests, including deliberate limits."""
import copy
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_rows.py"
spec = importlib.util.spec_from_file_location("check_rows", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CheckRowsTests(unittest.TestCase):
    def setUp(self):
        self.body = [
            ["alpha", "1.23", "2.34", "-", "-", None],
            ["beta", "2.34", "3.45", "-", "-", None],
        ]

    def check(self, rows):
        original = copy.deepcopy(rows)
        result = checker.check_table(rows)
        self.assertEqual(rows, original, "Checker mutated input")
        return result

    def test_full_collapse_after_context(self):
        result = self.check(self.body + [["gamma 3.45 - 4.56 8.01", None, None, None, None, None]])
        self.assertEqual([w["row_index_0based"] for w in result["warnings"]], [2])

    def test_labels_and_column_positions_are_not_hardcoded(self):
        result = self.check(self.body + [[None, None, "random 3.45 - 4.56 8.01", None, None, None]])
        self.assertEqual(result["warnings"][0]["populated_column_0based"], 2)

    def test_merged_year_header_is_not_a_decimal_signature(self):
        result = self.check(self.body + [["Section FY 2025 FY 2026 FY 2027", None, None, None, None, None]])
        self.assertEqual(result["warnings"], [])

    def test_empty_frame_row_is_ignored(self):
        self.assertEqual(self.check(self.body + [["", None, None, None, None, None]])["warnings"], [])

    def test_legitimate_merged_label_keeps_separate_amounts(self):
        self.assertEqual(self.check(self.body + [["total", None, "1.23", "2.34", "3.45", None]])["warnings"], [])

    def test_recovered_row_not_flagged(self):
        self.assertEqual(self.check(self.body + [["gamma", "3.45", "4.56", "8.01", "-", None]])["warnings"], [])

    def test_ambiguous_decimal_note_is_deliberate_false_positive(self):
        result = self.check(self.body + [["Values discussed: 1.23 2.34 3.45", None, None, None, None, None]])
        self.assertEqual(len(result["warnings"]), 1)

    def test_insufficient_context_is_known_false_negative(self):
        result = self.check([["item 1.23 2.34 3.45", None, None, None, None, None]])
        self.assertEqual(result["warnings"], [])
        self.assertIn("insufficient", result["single_nonempty_slot_candidates"][0]["disposition"])

    def test_integer_only_collapse_is_known_false_negative(self):
        self.assertEqual(self.check(self.body + [["item 1 2 3 4 -", None, None, None, None, None]])["warnings"], [])

    def test_partial_collapse_is_known_false_negative(self):
        self.assertEqual(self.check(self.body + [["item", "1.23 2.34 3.45", None, None, None, None]])["warnings"], [])

    def test_null_to_blank_conversion_is_outside_scope(self):
        self.assertEqual(self.check(self.body + [["item 1.23 2.34 3.45", "", "", "", "", ""]])["warnings"], [])

    def test_signed_grouped_decimal_lexemes(self):
        self.assertEqual(checker.decimal_tokens("x -1.20 +2.30 1,234.50 5 1.2.3"), ["-1.20", "+2.30", "1,234.50"])

    def test_reject_ragged_rows(self):
        with self.assertRaises(ValueError):
            checker.check_table([["x"], ["y", None]])

    def test_reject_coerced_cells(self):
        with self.assertRaises(ValueError):
            checker.check_table([[1.23, None]])

    def test_two_decimal_tokens_do_not_cross_threshold(self):
        self.assertEqual(self.check(self.body + [["item 1.23 2.34", None, None, None, None, None]])["warnings"], [])

    def test_one_prior_numeric_row_does_not_cross_threshold(self):
        self.assertEqual(self.check(self.body[:1] + [["item 1.23 2.34 3.45", None, None, None, None, None]])["warnings"], [])

    def test_body_requires_four_numeric_or_dash_cells(self):
        self.assertFalse(checker.body_evidence(["x", "1.23", "2.34", "-", None, None]))
        self.assertTrue(checker.body_evidence(["x", "1.23", "2.34", "-", "-", None]))

    def test_body_requires_two_decimal_cells(self):
        self.assertFalse(checker.body_evidence(["x", "1.23", "-", "-", "-", None]))

    def test_context_is_not_reset_by_a_header(self):
        # This is a documented limitation, not evidence of local body continuity.
        result = self.check(self.body + [["new section", None, None, None, None, None],
                                         ["note 1.23 2.34 3.45", None, None, None, None, None]])
        self.assertEqual([w["row_index_0based"] for w in result["warnings"]], [3])


if __name__ == "__main__":
    unittest.main()
