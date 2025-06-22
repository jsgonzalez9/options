import unittest
import datetime
from src.core.spread_validator import validate_spread_legs # Assuming this is the main function to test

class TestSpreadValidators(unittest.TestCase):

    def test_bull_call_spread_valid(self):
        valid_bcs_legs = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.0}, # Added entry_price for completeness
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", valid_bcs_legs)
        self.assertTrue(is_valid, msg)

    def test_bull_call_spread_invalid_legs_count(self):
        invalid_bcs_legs_one = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs_one)
        self.assertFalse(is_valid, "Should fail with one leg.")
        self.assertIn("exactly two legs", msg)

        invalid_bcs_legs_three = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.0},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 0.5}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs_three)
        self.assertFalse(is_valid, "Should fail with three legs.")
        self.assertIn("exactly two legs", msg)

    def test_bull_call_spread_invalid_option_types(self):
        invalid_bcs_legs = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.0},
            {"option_type": "PUT", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs)
        self.assertFalse(is_valid, "Should fail with mixed option types.")
        self.assertIn("Both legs of a Bull Call Spread must be CALL options", msg)

    def test_bull_call_spread_invalid_quantities(self):
        invalid_bcs_legs_both_long = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs_both_long)
        self.assertFalse(is_valid, "Should fail if both legs are long.")
        self.assertIn("requires one long call and one short call", msg)

        invalid_bcs_legs_both_short = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs_both_short)
        self.assertFalse(is_valid, "Should fail if both legs are short.")
        self.assertIn("requires one long call and one short call", msg)

        invalid_bcs_legs_zero_qty = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 0, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs_zero_qty)
        self.assertFalse(is_valid, "Should fail with zero quantity leg.")
        self.assertIn("requires one long call and one short call", msg)

    def test_bull_call_spread_invalid_expiry(self):
        invalid_bcs_legs = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 2, 21), "quantity": -1, "entry_price_per_unit": 1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs)
        self.assertFalse(is_valid, "Should fail with different expiry dates.")
        self.assertIn("must have the same expiry date", msg)

    def test_bull_call_spread_invalid_strike_order(self):
        invalid_bcs_legs = [
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs)
        self.assertFalse(is_valid, "Should fail with incorrect strike order.")
        self.assertIn("long call strike must be lower", msg)

    def test_bull_call_spread_missing_keys(self):
        invalid_bcs_legs = [{"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025,1,17), "entry_price_per_unit":1.0}] # Missing quantity
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs)
        self.assertFalse(is_valid)
        self.assertIn("missing one or more required keys", msg)

    def test_bull_call_spread_invalid_date_type(self):
        invalid_bcs_legs = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": "2025-01-17", "quantity": 1, "entry_price_per_unit":1.0}, # String date
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs)
        self.assertFalse(is_valid)
        self.assertIn("expiry_date must be a datetime.date object", msg)

    # --- Iron Condor Tests ---
    def test_iron_condor_valid(self):
        valid_ic_legs = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("IRON CONDOR", valid_ic_legs)
        self.assertTrue(is_valid, msg)

    def test_iron_condor_invalid_legs_count(self):
        invalid_ic_legs = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs)
        self.assertFalse(is_valid)
        self.assertIn("must have exactly four legs", msg)

    def test_iron_condor_invalid_expiry(self):
        invalid_ic_legs = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 2, 21), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs)
        self.assertFalse(is_valid)
        self.assertIn("All legs of an Iron Condor must have the same expiry date", msg)

    def test_iron_condor_invalid_types(self):
        invalid_ic_legs = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "PUT", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs)
        self.assertFalse(is_valid)
        self.assertIn("must consist of two PUTs and two CALLs", msg)

    def test_iron_condor_invalid_quantities_structure(self):
        invalid_ic_legs = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs)
        self.assertFalse(is_valid)
        self.assertIn("structure incorrect", msg)

    def test_iron_condor_invalid_quantities_mismatch(self):
        invalid_ic_legs = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -2, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs)
        self.assertFalse(is_valid)
        self.assertIn("same absolute number of contracts", msg)

    def test_iron_condor_invalid_strike_order(self):
        invalid_ic_legs = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0},
            {"option_type": "PUT", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit":1.0},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit":1.0}
        ]
        is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs)
        self.assertFalse(is_valid)
        self.assertIn("Strike prices for Iron Condor are not in the correct order", msg)

    # --- Unknown Spread Type Test ---
    def test_unknown_spread_type(self):
        unknown_legs = [{"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit":1.0}]
        is_valid, msg = validate_spread_legs("MY CUSTOM SPREAD", unknown_legs)
        self.assertTrue(is_valid, "Should be True for unknown spread type with current default behavior.")
        self.assertIn("No specific validator for spread type", msg)

    # --- Placeholder tests for other spread types ---
    def test_validate_bear_call_spread_placeholder(self):
        self.skipTest("Validator for Bear Call Spread not yet implemented.")

    def test_validate_bear_put_spread_placeholder(self):
        self.skipTest("Validator for Bear Put Spread not yet implemented.")

    def test_validate_butterfly_spread_placeholder(self):
        self.skipTest("Validator for Butterfly Spread not yet implemented.")

if __name__ == '__main__':
    unittest.main()
