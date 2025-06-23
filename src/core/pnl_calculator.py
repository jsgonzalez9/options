from src.database import models # For type hinting if needed, though direct model access isn't planned here for core calc
from typing import Optional

# Multiplier for option contracts (typically 100 shares per contract)
# This should ideally be configurable or passed in if it can vary.
# For now, using a global constant consistent with crud.py.
from src.config import OPTION_MULTIPLIER # Centralized configuration

def calculate_leg_pnl( # Renamed OPTION_MULTIPLIER to multiplier
    leg_entry_price: float,
    leg_market_price: float,
    leg_quantity: int,
    multiplier: int # Added multiplier argument
) -> float:
    """
    Calculates the Profit or Loss for a single leg (option or stock) based on its market price.

    Args:
        leg_entry_price: The price per unit at which the leg was entered.
        leg_market_price: The current market price per unit (or closing price per unit).
        leg_quantity: The quantity of contracts. Positive for long, negative for short.

    Returns:
        The P&L for the leg. Positive for profit, negative for loss.
    """
    if leg_quantity == 0:
        return 0.0

    price_diff_per_unit = leg_market_price - leg_entry_price

    # For long positions (bought options, quantity > 0), P&L = (market_price - entry_price) * quantity * multiplier
    # For short positions (sold options, quantity < 0), P&L = (entry_price - market_price) * abs(quantity) * multiplier
    # This can be unified: P&L = (market_price - entry_price) * quantity * multiplier
    # Example Long: quantity=1, entry=2, market=3. PNL = (3-2)*1*100 = 100 (Profit)
    # Example Short: quantity=-1, entry=2, market=1. PNL = (1-2)*-1*100 = (-1)*-1*100 = 100 (Profit)
    # Example Short: quantity=-1, entry=2, market=3. PNL = (3-2)*-1*multiplier = 1*-1*multiplier = -multiplier (Loss)

    pnl = price_diff_per_unit * leg_quantity * multiplier
    return pnl

def calculate_unrealized_pnl_for_leg(
    leg: models.OptionLeg,
    current_market_price_per_unit: Optional[float] = None
) -> float:
    """
    Calculates the unrealized P&L for a single option leg using its current_price_per_unit
    or a provided market price. This is primarily for option legs.
    For stock positions, use calculate_stock_position_unrealized_pnl.
    """
    market_price = current_market_price_per_unit if current_market_price_per_unit is not None else leg.current_price_per_unit

    if market_price is None:
        return 0.0

    # Determine multiplier based on leg type (STOCK vs OPTION)
    # This assumes our "STOCK" type leg has option_type == "STOCK"
    # and its quantity field stores number of shares.
    effective_multiplier = 1 if leg.option_type == "STOCK" else OPTION_MULTIPLIER

    return calculate_leg_pnl(
        leg_entry_price=leg.entry_price_per_unit,
        leg_market_price=market_price,
        leg_quantity=leg.quantity,
        multiplier=effective_multiplier
    )

def calculate_stock_position_unrealized_pnl(
    stock_quantity: int,
    entry_price_per_unit: float, # This would be from the "representative" leg or Position field
    current_market_price: float
) -> float:
    """Calculates unrealized P&L for a simple stock position."""
    if current_market_price is None:
        return 0.0
    return (current_market_price - entry_price_per_unit) * stock_quantity


def calculate_realized_pnl_for_position(position: models.Position) -> float:
    """
    Calculates the realized P&L for a closed position.
    Handles both option spreads and simple stock positions.

    Method 1: If position.closing_price is set (net credit/debit for closing entire position).
              This is the total P&L for the position.
              P&L = position.closing_price - position.cost_basis.
              (Note: cost_basis is typically stored as a positive value for debits, negative for credits.
               closing_price would be positive for credits received on close, negative for debits paid on close).
               So, if cost_basis = 100 (debit) and closing_price = 150 (credit), P&L = 150 - 100 = 50.
               If cost_basis = -200 (credit) and closing_price = -50 (debit to close), P&L = -50 - (-200) = 150.

    Method 2: If position.closing_price is NOT set, but individual legs have closing_price_per_unit.
              Sum the P&L from each leg. P&L_leg = (closing_price_leg - entry_price_leg) * quantity * multiplier.

    Args:
        position: The Position object (expected to be 'CLOSED').

    Returns:
        The total realized P&L for the position.
    """
    if position.status != "CLOSED":
        # print(f"Warning: Position {position.id} is not CLOSED. Realized P&L calculation might be premature.")
        # Or return 0.0, or raise error. For now, let it proceed if data is available.
        pass

    # Method 1: Position-level closing_price is set (suitable for stocks or entire spreads closed for a net value)
    if position.closing_price is not None:
        # cost_basis is total cost (positive for debit, negative for credit)
        # closing_price is total proceeds (positive for credit, negative for debit)
        return position.closing_price - position.cost_basis

    # Method 2: Leg-level closing prices (primarily for option spreads where legs might be managed individually)
    # If it's a stock position without a position.closing_price, this path might not be appropriate
    # unless the stock "leg" has a closing_price_per_unit.
    if position.is_stock_position and position.legs: # Stock position represented by a single leg
        leg = position.legs[0] # Assuming one representative leg for stock
        if leg.closing_price_per_unit is not None:
             # For stock, leg.quantity is share count, multiplier is 1.
            return calculate_leg_pnl(
                leg_entry_price=leg.entry_price_per_unit,
                leg_market_price=leg.closing_price_per_unit,
                leg_quantity=leg.quantity,
                multiplier=1
            )
        else: # Stock position closed but leg has no closing price - fallback to position level if possible, else 0
            # This case implies data might be incomplete for leg-based stock P&L.
            # If position.closing_price was None, and leg.closing_price_per_unit is None, P&L is indeterminate here.
            print(f"Warning: Stock Position {position.id} is CLOSED but has no position.closing_price and its leg has no closing_price_per_unit.")
            return 0.0

    elif not position.is_stock_position and position.legs: # Option spread
        total_realized_pnl = 0.0
        all_legs_have_closing_price = True
        for leg in position.legs:
            if leg.closing_price_per_unit is not None:
                total_realized_pnl += calculate_leg_pnl(
                    leg_entry_price=leg.entry_price_per_unit,
                    leg_market_price=leg.closing_price_per_unit,
                    leg_quantity=leg.quantity,
                    multiplier=OPTION_MULTIPLIER # Options use the standard multiplier
                )
            else:
                all_legs_have_closing_price = False

        if not all_legs_have_closing_price:
            print(f"Warning: Option Position {position.id} is CLOSED, but not all legs have closing_price_per_unit. P&L may be partial.")
        return total_realized_pnl

    # Default if no other condition met (e.g., no legs, no position.closing_price)
    return 0.0


if __name__ == '__main__':
    # Example Usages
    print("--- P&L Calculator Examples ---")

    # Leg P&L
    print("\n1. Leg P&L Calculation:")
    # Long Call, Profit
    # Entry: $2.00, Market: $3.00, Qty: 1 (long)
    # P&L = (3.00 - 2.00) * 1 * 100 = $100
    pnl1 = calculate_leg_pnl(leg_entry_price=2.00, leg_market_price=3.00, leg_quantity=1)
    print(f"Long Leg (Profit): Entry @ 2.00, Market @ 3.00, Qty 1 => P&L: {pnl1:.2f}") # Expected: 100.00

    # Short Put, Loss
    # Entry: $1.50 (credit), Market: $2.50, Qty: -1 (short)
    # P&L = (2.50 - 1.50) * -1 * 100 = 1.00 * -1 * 100 = -$100
    pnl2 = calculate_leg_pnl(leg_entry_price=1.50, leg_market_price=2.50, leg_quantity=-1)
    print(f"Short Leg (Loss): Entry @ 1.50, Market @ 2.50, Qty -1 => P&L: {pnl2:.2f}") # Expected: -100.00

    # Short Call, Profit
    # Entry: $3.00 (credit), Market: $1.00, Qty: -2 (short 2 contracts)
    # P&L = (1.00 - 3.00) * -2 * 100 = -2.00 * -2 * 100 = $400
    pnl3 = calculate_leg_pnl(leg_entry_price=3.00, leg_market_price=1.00, leg_quantity=-2)
    print(f"Short Leg (Profit): Entry @ 3.00, Market @ 1.00, Qty -2 => P&L: {pnl3:.2f}") # Expected: 400.00

    # Mock OptionLeg for unrealized P&L
    class MockOptionLeg:
        def __init__(self, id, entry_price, quantity, current_price=None, closing_price=None):
            self.id = id
            self.entry_price_per_unit = entry_price
            self.quantity = quantity
            self.current_price_per_unit = current_price
            self.closing_price_per_unit = closing_price

    leg_a = MockOptionLeg(id=1, entry_price=10.0, quantity=1, current_price=12.0)
    unreal_pnl_a = calculate_unrealized_pnl_for_leg(leg_a)
    # (12.0 - 10.0) * 1 * 100 = 200
    print(f"\n2. Unrealized P&L for Leg A: {unreal_pnl_a:.2f}") # Expected: 200.00

    leg_b = MockOptionLeg(id=2, entry_price=5.0, quantity=-1, current_price=6.0) # No current price override
    unreal_pnl_b = calculate_unrealized_pnl_for_leg(leg_b)
    # (6.0 - 5.0) * -1 * 100 = -100
    print(f"Unrealized P&L for Leg B (using leg.current_price_per_unit): {unreal_pnl_b:.2f}") # Expected: -100.00

    leg_c = MockOptionLeg(id=3, entry_price=5.0, quantity=-1) # Missing current price
    unreal_pnl_c = calculate_unrealized_pnl_for_leg(leg_c, current_market_price_per_unit=None)
    print(f"Unrealized P&L for Leg C (no market price): {unreal_pnl_c:.2f}") # Expected: 0.00

    # Realized P&L for Position
    print("\n3. Realized P&L for Position:")
    # Method 1: Position-level closing price
    class MockPosition:
        def __init__(self, id, cost_basis, status="CLOSED", closing_price=None, legs=None):
            self.id = id
            self.cost_basis = cost_basis
            self.status = status
            self.closing_price = closing_price
            self.legs = legs if legs is not None else []

    # Scenario 1: Debit spread, closed for larger credit
    # Cost basis: 100 (debit), Closing price: 150 (credit from closing)
    # P&L = 150 - 100 = 50
    pos1 = MockPosition(id=1, cost_basis=100.0, closing_price=150.0)
    real_pnl1 = calculate_realized_pnl_for_position(pos1)
    print(f"Position 1 (CB: 100, CP: 150) Realized P&L: {real_pnl1:.2f}") # Expected: 50.00

    # Scenario 2: Credit spread, closed for smaller debit
    # Cost basis: -200 (credit from opening), Closing price: -50 (debit to close)
    # P&L = -50 - (-200) = 150
    pos2 = MockPosition(id=2, cost_basis=-200.0, closing_price=-50.0)
    real_pnl2 = calculate_realized_pnl_for_position(pos2)
    print(f"Position 2 (CB: -200, CP: -50) Realized P&L: {real_pnl2:.2f}") # Expected: 150.00

    # Method 2: Leg-level closing prices
    leg_x = MockOptionLeg(id=10, entry_price=2.0, quantity=1, closing_price=3.5) # PNL = (3.5-2)*1*100 = 150
    leg_y = MockOptionLeg(id=11, entry_price=1.0, quantity=-1, closing_price=0.2) # PNL = (0.2-1)*-1*100 = 80
    # Total PNL = 150 + 80 = 230
    pos3 = MockPosition(id=3, cost_basis=100.0, status="CLOSED", closing_price=None, legs=[leg_x, leg_y]) # cost_basis here is (2-1)*100=100
    real_pnl3 = calculate_realized_pnl_for_position(pos3)
    print(f"Position 3 (Leg-level closing) Realized P&L: {real_pnl3:.2f}") # Expected: 230.00

    # Scenario: Position closed, but one leg has no closing price (should use what it can)
    leg_z_no_close = MockOptionLeg(id=12, entry_price=1.0, quantity=1) # No closing_price_per_unit
    pos4 = MockPosition(id=4, cost_basis=0.0, status="CLOSED", closing_price=None, legs=[leg_x, leg_z_no_close])
    real_pnl4 = calculate_realized_pnl_for_position(pos4) # Will only use leg_x
    print(f"Position 4 (One leg no close price) Realized P&L: {real_pnl4:.2f}") # Expected: 150.00 (from leg_x only)

    print("\nP&L Calculator examples finished.")
