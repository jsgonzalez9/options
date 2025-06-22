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
                 unrealized_pnl=0.0, realized_pnl=0.0):
        self.id = id
        self.cost_basis = cost_basis
        self.status = status
        self.closing_price = closing_price
        self.legs = legs if legs is not None else []
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
        # Add other fields if pnl_calculator starts using them
        self.spread_type = "Mock Spread"
        self.entry_date = datetime.datetime.utcnow()
        self.notes = None


class TestPnlCalculator(unittest.TestCase):

    def test_calculate_leg_pnl(self):
        # Long leg, profit
        # (Market 3.0 - Entry 2.0) * 1 Qty * 100 Multiplier = 100
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, 1), 100.0)

        # Long leg, loss
        # (Market 1.0 - Entry 2.0) * 1 Qty * 100 Multiplier = -100
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 1.0, 1), -100.0)

        # Short leg, profit
        # (Market 1.0 - Entry 2.0) * -1 Qty * 100 Multiplier = (-1.0) * -1 * 100 = 100
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 1.0, -1), 100.0)

        # Short leg, loss
        # (Market 3.0 - Entry 2.0) * -1 Qty * 100 Multiplier = (1.0) * -1 * 100 = -100
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, -1), -100.0)

        # Zero quantity
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, 0), 0.0)

        # Multiple contracts (long, profit)
        # (Market 3.0 - Entry 2.0) * 2 Qty * 100 Multiplier = 200
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 3.0, 2), 200.0)

        # Multiple contracts (short, profit)
        # (Market 1.0 - Entry 2.0) * -3 Qty * 100 Multiplier = (-1.0) * -3 * 100 = 300
        self.assertAlmostEqual(pnl_calculator.calculate_leg_pnl(2.0, 1.0, -3), 300.0)

    def test_calculate_unrealized_pnl_for_leg(self):
        # Leg with current_price_per_unit set
        leg1 = MockOptionLeg(id=1, entry_price_per_unit=5.0, quantity=1, current_price_per_unit=7.5)
        # (7.5 - 5.0) * 1 * 100 = 250
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg1), 250.0)

        # Leg with current_market_price_per_unit override
        leg2 = MockOptionLeg(id=2, entry_price_per_unit=5.0, quantity=-1, current_price_per_unit=7.5) # This will be overridden
        # (4.0 - 5.0) * -1 * 100 = 100
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg2, current_market_price_per_unit=4.0), 100.0)

        # Leg with no current price information (should return 0.0 as per implementation)
        leg3 = MockOptionLeg(id=3, entry_price_per_unit=5.0, quantity=1, current_price_per_unit=None)
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg3), 0.0)
        # Test override with None also
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg3, current_market_price_per_unit=None), 0.0)


    def test_calculate_realized_pnl_for_position(self):
        # Method 1: Position-level closing_price is set
        # Position cost_basis = 100 (debit), closing_price = 150 (credit received at close) -> PNL = 150 - 100 = 50
        pos1 = MockPosition(id=1, cost_basis=100.0, closing_price=150.0, status="CLOSED")
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos1), 50.0)

        # Cost_basis = -200 (credit), closing_price = -50 (debit paid at close) -> PNL = -50 - (-200) = 150
        pos2 = MockPosition(id=2, cost_basis=-200.0, closing_price=-50.0, status="CLOSED")
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos2), 150.0)

        # Method 2: Leg-level closing_price_per_unit, position.closing_price is None
        leg_a = MockOptionLeg(id=101, entry_price_per_unit=2.0, quantity=1, closing_price_per_unit=3.0) # PNL = (3-2)*1*100 = 100
        leg_b = MockOptionLeg(id=102, entry_price_per_unit=1.5, quantity=-1, closing_price_per_unit=0.5) # PNL = (0.5-1.5)*-1*100 = 100
        pos3 = MockPosition(id=3, cost_basis=50.0, status="CLOSED", closing_price=None, legs=[leg_a, leg_b])
        # Total PNL = 100 + 100 = 200
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos3), 200.0)

        # Position is OPEN, should still calculate based on available data if forced, or follow logic.
        # Current implementation proceeds and calculates.
        pos4_open_legs_closed = MockPosition(id=4, cost_basis=50.0, status="OPEN", closing_price=None, legs=[leg_a, leg_b])
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos4_open_legs_closed), 200.0)

        # Position CLOSED, but one leg has no closing_price_per_unit, position.closing_price is None
        leg_c_no_close = MockOptionLeg(id=103, entry_price_per_unit=1.0, quantity=1, closing_price_per_unit=None)
        pos5 = MockPosition(id=5, cost_basis=0.0, status="CLOSED", closing_price=None, legs=[leg_a, leg_c_no_close])
        # PNL will only be from leg_a = 100. leg_c_no_close contributes 0 if its closing_price_per_unit is None.
        # This depends on how calculate_leg_pnl handles None for market_price, which it shouldn't get here.
        # calculate_realized_pnl_for_position filters for legs where leg.closing_price_per_unit is not None.
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos5), 100.0)

        # Position CLOSED, no legs, no position.closing_price. Should be 0.
        pos6_no_legs = MockPosition(id=6, cost_basis=0.0, status="CLOSED", closing_price=None, legs=[])
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos6_no_legs), 0.0)

        # Position CLOSED, no legs, but position.closing_price is set (e.g. a stock position)
        # Cost_basis = 1000 (stock buy), closing_price = 1200 (stock sell) -> PNL = 200
        pos7_stock_like = MockPosition(id=7, cost_basis=1000.0, status="CLOSED", closing_price=1200.0, legs=[])
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos7_stock_like), 200.0)

        # Position CLOSED, leg-level, but one leg has closing_price_per_unit = 0.0 (e.g. worthless expiry)
        leg_d_worthless = MockOptionLeg(id=104, entry_price_per_unit=0.5, quantity=1, closing_price_per_unit=0.0) # Bought for 0.5, closed at 0. PNL = (0-0.5)*1*100 = -50
        pos8_worthless_leg = MockPosition(id=8, cost_basis=50.0, status="CLOSED", closing_price=None, legs=[leg_d_worthless])
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos8_worthless_leg), -50.0)

        # Position CLOSED, leg-level, mix of closed and open (no closing price) legs - this is unusual for a "CLOSED" position
        # but tests robustness. calculate_realized_pnl_for_position should sum PNL for legs that DO have closing_price_per_unit.
        leg_e_closed = MockOptionLeg(id=105, entry_price_per_unit=1.0, quantity=1, closing_price_per_unit=1.5) # PNL = 50
        leg_f_no_close_price = MockOptionLeg(id=106, entry_price_per_unit=1.0, quantity=1, closing_price_per_unit=None)
        pos9_mixed_legs = MockPosition(id=9, cost_basis=200.0, status="CLOSED", closing_price=None, legs=[leg_e_closed, leg_f_no_close_price])
        self.assertAlmostEqual(pnl_calculator.calculate_realized_pnl_for_position(pos9_mixed_legs), 50.0,
                             "Should sum PNL only from legs with closing_price_per_unit if position.closing_price is None")

    def test_calculate_unrealized_pnl_for_leg_zero_quantity(self):
        leg_zero_qty = MockOptionLeg(id=4, entry_price_per_unit=5.0, quantity=0, current_price_per_unit=7.5)
        self.assertAlmostEqual(pnl_calculator.calculate_unrealized_pnl_for_leg(leg_zero_qty), 0.0)


if __name__ == '__main__':
    unittest.main()
