import sys
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from alerts import alert, compare, snapshot
from build_inputs import qualify


class QuoteIdentityTests(unittest.TestCase):
    def setUp(self):
        self.pair = dict(
            market="Southeast",
            date="2024-01-02",
            unit="cents_per_pound",
            other_quality_convention="source_base",
            base_native="80",
            added_native="88",
        )
        self.old, self.new = snapshot(self.pair, True, "0", "normal")

    def test_composition_only_false_alert(self):
        value, status = compare(self.old, self.new, "grade_blind")
        self.assertEqual(value, Fraction(1, 20))
        self.assertTrue(alert(value, "1/20"))

    def test_quality_preserves_original_quote(self):
        self.assertEqual(
            compare(self.old, self.new, "quality_matched"), (Fraction(0), "available")
        )

    def test_no_expansion_same_quality(self):
        old, new = snapshot(self.pair, False, "-1/20", "normal")
        for rule in ["grade_blind", "quality_matched"]:
            self.assertEqual(compare(old, new, rule)[0], Fraction(-1, 20))

    def test_negative_shock_can_be_hidden_by_composition(self):
        old, new = snapshot(self.pair, True, "-1/20", "normal")
        self.assertEqual(compare(old, new, "grade_blind")[0], Fraction(-1, 400))
        self.assertFalse(alert(compare(old, new, "grade_blind")[0], "1/50"))

    def test_positive_shock_is_not_source_fact(self):
        original = self.pair.copy()
        old, new = snapshot(self.pair, True, "1/10", "normal")
        self.assertEqual(self.pair, original)
        self.assertEqual(Fraction(new[0]["price"]), 88)

    def test_exact_boundary_above(self):
        self.assertTrue(alert(Fraction(1, 50), "1/50"))

    def test_exact_boundary_negative(self):
        self.assertTrue(alert(Fraction(-1, 50), "1/50"))

    def test_exact_boundary_below(self):
        self.assertFalse(alert(Fraction(199999, 10000000), "1/50"))

    def test_abstention_not_negative(self):
        self.assertIsNone(alert(None, "1/50"))

    def test_missing_base(self):
        old, new = snapshot(self.pair, True, "0", "missing_base")
        self.assertIsNone(compare(old, new, "quality_matched")[0])
        self.assertIsNotNone(compare(old, new, "grade_blind")[0])

    def test_empty_snapshot_both_abstain(self):
        old, new = snapshot(self.pair, False, "0", "missing_base")
        for rule in ["grade_blind", "quality_matched"]:
            self.assertIsNone(compare(old, new, rule)[0])

    def test_changed_quality_is_not_crosswalked(self):
        old, new = snapshot(self.pair, True, "0", "changed_quality")
        self.assertIsNone(compare(old, new, "quality_matched")[0])

    def test_missing_baseline_identity(self):
        old = self.old.copy()
        del old["quality"]
        self.assertIsNone(compare(old, self.new, "quality_matched")[0])

    def test_market_mismatch(self):
        self.new[0]["market"] = "North Delta"
        self.assertIsNone(compare(self.old, self.new, "quality_matched")[0])

    def test_unit_mismatch(self):
        self.new[0]["unit"] = "basis_points"
        self.assertIsNone(compare(self.old, self.new, "grade_blind")[0])

    def test_other_quality_mismatch(self):
        self.new[0]["other_quality_convention"] = "different"
        self.assertIsNone(compare(self.old, self.new, "quality_matched")[0])

    def test_zero_baseline_unavailable(self):
        self.old["price"] = "0"
        self.assertIsNone(compare(self.old, self.new, "grade_blind")[0])

    def test_negative_quote_unavailable(self):
        self.new[0]["price"] = "-1"
        self.assertIsNone(compare(self.old, self.new, "grade_blind")[0])

    def test_zero_alternative_is_a_number(self):
        self.new[1]["price"] = "0"
        self.assertEqual(compare(self.old, self.new, "grade_blind")[0], Fraction(-1, 2))

    def test_unknown_quote_is_not_zero(self):
        self.new[0]["price"] = None
        self.assertIsNone(compare(self.old, self.new, "quality_matched")[0])

    def test_conflicting_same_quality_abstains(self):
        extra = self.new[0].copy()
        extra["price"] = "81"
        self.new.append(extra)
        self.assertIsNone(compare(self.old, self.new, "quality_matched")[0])

    def test_identical_copy_not_double_counted_by_matched(self):
        self.new.append(self.new[0].copy())
        self.assertEqual(compare(self.old, self.new, "quality_matched")[0], 0)

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):
            alert(Fraction(0), "0")

    def test_unknown_rule(self):
        with self.assertRaises(ValueError):
            compare(self.old, self.new, "unplanned")

    def test_native_decimal_precision(self):
        self.old["price"] = "80.00000000000001"
        self.new = [self.old.copy()]
        self.assertEqual(compare(self.old, self.new, "quality_matched")[0], 0)

    def test_missing_price_is_unknown(self):
        del self.new[0]["price"]
        self.assertIsNone(compare(self.old, self.new, "quality_matched")[0])

    def test_binary_float_input_requires_native_token(self):
        self.new[0]["price"] = 81.6
        self.assertIsNone(compare(self.old, self.new, "quality_matched")[0])

    def test_boolean_is_not_a_price(self):
        self.old["price"] = True
        self.assertIsNone(compare(self.old, self.new, "quality_matched")[0])


if __name__ == "__main__":
    unittest.main()
