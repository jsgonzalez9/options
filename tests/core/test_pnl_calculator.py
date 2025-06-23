import unittest
from src.core import pnl_calculator
from src.database import models # For MockOptionLeg or if we instantiate real models
import datetime

# Define OPTION_MULTIPLIER for consistency in tests, mirroring its use in the module
OPTION_MULTIPLIER = 100
pnl_calculator.OPTION_MULTIPLIER = OPTION_MULTIPLIER # Override if module's default is different or for test control

class MockOptionLeg:
    """Helper mock class for OptionLeg if we don't want full DB model instantiation."""
    def __init__(self, id, entry_price_per_unit, quantity,
                 current_price_per_unit=None, closing_price_per_unit=None,
                 option_type="CALL", strike_price=100, expiry_date=datetime.date(2025,1,1)):
        self.id = id
        self.entry_price_per_unit = entry_price_per_unit
        self.quantity = quantity
        self.current_price_per_unit = current_price_per_unit
        self.closing_price_per_unit = closing_price_per_unit
        # Add other fields if pnl_calculator starts using them
        self.option_type = option_type
        self.strike_price = strike_price
        self.expiry_date = expiry_date


class MockPosition:
    """Helper mock class for Position."""
    def __init__(self, id, cost_basis, status="CLOSED", closing_price=None, legs=None,
                 unrealized_pnl=0.0, realized_pnl=0.0,
                 is_stock_position=False, stock_quantity=None): # Added new fields
        self.id = id
        self.cost_basis = cost_basis
        self.status = status
        self.closing_price = closing_price
        self.legs = legs if legs is not None else []
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
        self.is_stock_position = is_stock_position # Added
        self.stock_quantity = stock_quantity   # Added
        # Add other fields if pnl_calculator starts using them
        self.spread_type = "Mock Spread"
        self.entry_date = datetime.datetime.utcnow()
        self.notes = None


class TestPnlCalculator(unittest.TestCase):

    def test_calculate_leg_pnl(self):
        # Long leg, profit (option)
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, 1, OPTION_MULTIPLIER), 100.0)

        # Long leg, loss (option)
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 1.0, 1, OPTION_MULTIPLIER), -100.0)

        # Short leg, profit (option)
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 1.0, -1, OPTION_MULTIPLIER), 100.0)

        # Short leg, loss
        # (Market 3.0 - Entry 2.0) * -1 Qty * OPTION_MULTIPLIER Multiplier = (1.0) * -1 * 100 = -100
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, -1, OPTION_MULTIPLIER), -100.0)

        # Zero quantity
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, 0, OPTION_MULTIPLIER), 0.0)

        # Multiple contracts (long, profit)
        # (Market 3.0 - Entry 2.0) * 2 Qty * OPTION_MULTIPLIER Multiplier = 200
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, 2, OPTION_MULTIPLIER), 200.0)

        # Multiple contracts (short, profit)
        # (Market 1.0 - Entry 2.0) * -3 Qty * OPTION_MULTIPLIER Multiplier = (-1.0) * -3 * 100 = 300
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 1.0, -3, OPTION_MULTIPLIER), 300.0)

        # Stock leg (multiplier 1)
        # (Market 155 - Entry 150) * 100 shares * 1 multiplier = 500
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(150.0, 155.0, 100, 1), 500.0) # Already correct

    def test_calculate_unrealized_pnl_for_leg(self):
        # Option Leg with current_price_per_unit set
        leg1 = MockOptionLeg(id=1, entry_price_per_unit=5.0, quantity=1, current_price_per_unit=7.5, option_type="CALL")
        # (7.5 - 5.0) * 1 * 100 = 250
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg1), 250.0)

        # Option Leg with current_market_price_per_unit override
        leg2 = MockOptionLeg(id=2, entry_price_per_unit=5.0, quantity=-1, current_price_per_unit=7.5, option_type="PUT") # This will be overridden
        # (4.0 - 5.0) * -1 * 100 = 100
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg2, current_market_price_per_unit=4.0), 100.0)

        # Leg with no current price information (should return 0.0 as per implementation)
        leg3 = MockOptionLeg(id=3, entry_price_per_unit=5.0, quantity=1, current_price_per_unit=None)
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg3), 0.0)
        # Test override with None also
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg3, current_market_price_per_unit=None), 0.0)

        # Test for "STOCK" type leg (should use multiplier 1)
        stock_leg = MockOptionLeg(id=4, entry_price_per_unit=100.0, quantity=10, current_price_per_unit=102.0, option_type="STOCK")
        # (102.0 - 100.0) * 10 * 1 = 20.0
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(stock_leg), 20.0)


    def test_calculate_stock_position_unrealized_pnl(self):
        # Profit
        self.assertAlmostEqual(pnl_calculator.calculate_stock_position_unrealized_pnl(100, 150.0, 155.0), 500.0) # (155-150)*100
        # Loss
        self.assertAlmostEqual(pnl_calculator.calculate_stock_position_unrealized_pnl(100, 150.0, 140.0), -1000.0) # (140-150)*100
        # No change
        self.assertAlmostEqual(pnl_calculator.calculate_stock_position_unrealized_pnl(100, 150.0, 150.0), 0.0)
        # No current market price
        self.assertAlmostEqual(pnl_calculator.calculate_stock_position_unrealized_pnl(100, 150.0, None), 0.0)


    def test_calculate_realized_pnl_for_position(self):
        # --- Option Spread Scenarios ---
        # Method 1: Position-level closing_price is set
        pos_opt_m1 = MockPosition(id=1, cost_basis=100.0, closing_price=150.0, status="CLOSED", is_stock_position=False)
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_opt_m1), 50.0)

        pos_opt_m1_credit = MockPosition(id=2, cost_basis=-200.0, closing_price=-50.0, status="CLOSED", is_stock_position=False)
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_opt_m1_credit), 150.0)

        # Method 2: Leg-level closing_price_per_unit for options
        leg_opt_a = MockOptionLeg(id=101, entry_price_per_unit=2.0, quantity=1, closing_price_per_unit=3.0, option_type="CALL") # PNL = 100
        leg_opt_b = MockOptionLeg(id=102, entry_price_per_unit=1.5, quantity=-1, closing_price_per_unit=0.5, option_type="CALL") # PNL = 100
        pos_opt_m2 = MockPosition(id=3, cost_basis=50.0, status="CLOSED", closing_price=None, legs=[leg_opt_a, leg_opt_b], is_stock_position=False)
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_opt_m2), 200.0)

        leg_opt_c_no_close = MockOptionLeg(id=103, entry_price_per_unit=1.0, quantity=1, closing_price_per_unit=None, option_type="PUT")
        pos_opt_m2_partial = MockPosition(id=5, cost_basis=0.0, status="CLOSED", closing_price=None, legs=[leg_opt_a, leg_opt_c_no_close], is_stock_position=False)
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_opt_m2_partial), 100.0) # Only leg_a PNL

        # --- Stock Position Scenarios ---
        # Method 1 (Position-level closing_price) for stock
        pos_stock_m1 = MockPosition(id=7, cost_basis=1000.0, status="CLOSED", closing_price=1200.0, is_stock_position=True, stock_quantity=10, legs=[]) # Legs might be empty if PNL is position level
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_stock_m1), 200.0)

        # Method 2 (Leg-level) for stock (assuming a single representative "STOCK" leg)
        # Stock: 10 shares, entry @ 10, close @ 12. Cost basis = 100. PNL = (12-10)*10 = 20
        stock_leg_closed = MockOptionLeg(id=201, entry_price_per_unit=10.0, quantity=10, closing_price_per_unit=12.0, option_type="STOCK")
        pos_stock_m2 = MockPosition(id=8, cost_basis=100.0, status="CLOSED", closing_price=None, legs=[stock_leg_closed], is_stock_position=True, stock_quantity=10)
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_stock_m2), 20.0)

        # Stock position closed, but representative leg has no closing_price_per_unit, and no position.closing_price
        stock_leg_no_close_price = MockOptionLeg(id=202, entry_price_per_unit=10.0, quantity=10, closing_price_per_unit=None, option_type="STOCK")
        pos_stock_m2_no_leg_price = MockPosition(id=9, cost_basis=100.0, status="CLOSED", closing_price=None, legs=[stock_leg_no_close_price], is_stock_position=True, stock_quantity=10)
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_stock_m2_no_leg_price), 0.0) # Expect 0 as PNL is indeterminate

        # General cases
        pos_no_legs_no_cp = MockPosition(id=6, cost_basis=0.0, status="CLOSED", closing_price=None, legs=[], is_stock_position=False)
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos_no_legs_no_cp), 0.0)


    def test_calculate_unrealized_pnl_for_leg_zero_quantity(self):
        leg_zero_qty = MockOptionLeg(id=4, entry_price_per_unit=5.0, quantity=0, current_price_per_unit=7.5, option_type="CALL")
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg_zero_qty), 0.0)


if __name__ == '__main__':
    unittest.main()
