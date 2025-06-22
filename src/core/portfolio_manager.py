from sqlalchemy.orm import Session
from src.database import models, crud # crud for positions
from src.core import pnl_calculator # For P&L contributions
from typing import Optional

from src.config import OPTION_MULTIPLIER # Centralized configuration

CASH_BALANCE_KEY = "cash_balance"
# OPTION_MULTIPLIER = 100 # Centralize this later (Task for step 7 of plan) # Now imported

# --- Cash Balance Functions ---

def get_cash_balance(db: Session) -> float:
    """Retrieves the current cash balance from PortfolioSettings."""
    cash_setting = db.query(models.PortfolioSetting).filter(models.PortfolioSetting.key == CASH_BALANCE_KEY).first()
    if cash_setting:
        return cash_setting.value
    return 0.0 # Default to 0 if not set

def update_cash_balance(db: Session, amount_change: float, is_deposit: bool) -> float:
    """
    Updates the cash balance. Adds if is_deposit is True, subtracts otherwise.
    `amount_change` should be positive.
    """
    if amount_change < 0:
        raise ValueError("Amount for cash balance change must be positive.")

    cash_setting = db.query(models.PortfolioSetting).filter(models.PortfolioSetting.key == CASH_BALANCE_KEY).first()

    current_balance = 0.0
    if cash_setting:
        current_balance = cash_setting.value

    if is_deposit:
        new_balance = current_balance + amount_change
    else: # Withdrawal
        if amount_change > current_balance:
            # Or handle this more gracefully, e.g., by not allowing withdrawal
            raise ValueError(f"Withdrawal amount {amount_change} exceeds current balance {current_balance}.")
        new_balance = current_balance - amount_change

    if cash_setting:
        cash_setting.value = new_balance
    else:
        cash_setting = models.PortfolioSetting(key=CASH_BALANCE_KEY, value=new_balance)
        db.add(cash_setting)

    # db.commit() # Caller handles commit
    db.flush()
    db.refresh(cash_setting)
    return cash_setting.value

# --- Portfolio Value Calculation Functions ---

def calculate_total_open_positions_market_value(db: Session) -> float:
    """
    Calculates the sum of the current market values of all open option positions.
    Market value of a leg = leg.current_price_per_unit * leg.quantity * OPTION_MULTIPLIER.
    Note: For short positions (quantity < 0), current_price_per_unit represents a liability.
          So, a short call at $1 (current_price_per_unit=1.0, quantity=-1) has a market value of -$100.
    """
    open_positions = crud.get_all_positions(db, status="OPEN") # Eager loads legs
    total_market_value = 0.0

    for position in open_positions:
        if position.spread_type == "Stock": # Placeholder for future stock handling
            # For stocks, market value = quantity * current_price_per_unit (no multiplier usually)
            # This needs a different model or field on Position/Leg for stock quantity/price.
            # For now, skipping stock positions or assuming they are handled as options if using OptionLeg.
            pass
        else: # Option Spreads
            for leg in position.legs:
                if leg.current_price_per_unit is not None:
                    # Long position (qty > 0): current_price * qty * mult = positive value
                    # Short position (qty < 0): current_price * qty * mult = negative value (liability)
                    total_market_value += leg.current_price_per_unit * leg.quantity * OPTION_MULTIPLIER
    return total_market_value


def get_overall_portfolio_pnl(db: Session) -> float:
    """
    Calculates the total P&L of the portfolio.
    Sum of all (Position.realized_pnl where status is CLOSED) +
    Sum of all (Position.unrealized_pnl where status is OPEN).
    """
    total_pnl = 0.0

    # Realized P&L from closed positions
    closed_positions_pnl = db.query(models.Position.realized_pnl)\
                               .filter(models.Position.status == "CLOSED",
                                       models.Position.realized_pnl.isnot(None))\
                               .all()
    for pnl_tuple in closed_positions_pnl:
        total_pnl += pnl_tuple[0]

    # Unrealized P&L from open positions
    open_positions_pnl = db.query(models.Position.unrealized_pnl)\
                             .filter(models.Position.status == "OPEN",
                                     models.Position.unrealized_pnl.isnot(None))\
                             .all()
    for pnl_tuple in open_positions_pnl:
        total_pnl += pnl_tuple[0]

    return total_pnl


def get_portfolio_summary_data(db: Session) -> dict:
    """
    Gathers all data needed for the portfolio summary.
    """
    cash = get_cash_balance(db)
    open_positions_value = calculate_total_open_positions_market_value(db)
    total_value = cash + open_positions_value
    overall_pnl = get_overall_portfolio_pnl(db) # This includes realized and current unrealized

    return {
        "cash_balance": cash,
        "total_open_positions_market_value": open_positions_value,
        "total_portfolio_value": total_value,
        "overall_portfolio_pnl": overall_pnl,
    }


if __name__ == '__main__':
    # Example usage (requires DB setup and potentially some data)
    from src.database import setup as db_setup
    from src.database import crud # For creating positions for testing

    print("--- Portfolio Manager Examples ---")

    # Setup in-memory DB for example
    engine = db_setup.create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    TestSessionLocal = db_setup.sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSessionLocal()

    try:
        # 1. Cash Balance
        print("\n1. Cash Balance Management:")
        initial_cash = get_cash_balance(db)
        print(f"  Initial cash balance: {initial_cash}") # Expected 0.0

        update_cash_balance(db, 10000.0, is_deposit=True)
        db.commit()
        print(f"  Cash after deposit 10000: {get_cash_balance(db)}")

        update_cash_balance(db, 500.0, is_deposit=False)
        db.commit()
        print(f"  Cash after withdrawal 500: {get_cash_balance(db)}")

        try:
            update_cash_balance(db, 100000.0, is_deposit=False) # Try to overdraw
        except ValueError as e:
            print(f"  Correctly caught overdraw attempt: {e}")
        db.rollback() # Rollback failed withdrawal

        # 2. Portfolio Value and P&L (requires positions)
        print("\n2. Portfolio Value & P&L:")
        # Create an open position for testing
        legs_data_pos1 = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025,1,17), "quantity": -1, "entry_price_per_unit": 1.00}
        ] # Cost basis: (2-1)*100 = 100
        pos1 = crud.create_position(db, "Bull Call Spread", legs_data_pos1, status="OPEN")
        db.commit()

        # Update current prices for its legs & UPL
        # Leg 1 (long 100C): Entry 2.00, Current 2.50 -> UPL_leg1 = 50
        # Leg 2 (short 105C): Entry 1.00, Current 0.80 -> UPL_leg2 = (0.8-1)*-1*100 = 20
        # Position UPL = 50 + 20 = 70
        leg_prices_pos1 = {}
        for leg in pos1.legs:
            if leg.strike_price == 100.0: leg_prices_pos1[leg.id] = 2.50
            if leg.strike_price == 105.0: leg_prices_pos1[leg.id] = 0.80

        crud.update_legs_current_prices_and_unrealized_pnl(db, pos1.id, leg_prices_pos1)
        db.commit()
        db.refresh(pos1) # Refresh to get updated UPL on pos1 object

        print(f"  Position 1 UPL: {pos1.unrealized_pnl}") # Expected 70

        # Create a closed position
        legs_data_pos2 = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2024,1,19), "quantity": 1, "entry_price_per_unit": 1.00},
        ] # Cost basis 100
        pos2 = crud.create_position(db, "Long Put", legs_data_pos2, status="OPEN")
        db.commit()
        # Close it for a profit: closing_price = 150 (credit), RPL = 150 - 100 = 50
        crud.update_position_status(db, pos2.id, "CLOSED", closing_price=150.0)
        db.commit()
        db.refresh(pos2)
        print(f"  Position 2 RPL: {pos2.realized_pnl}") # Expected 50

        summary = get_portfolio_summary_data(db)
        print("\n  Portfolio Summary:")
        for key, val in summary.items():
            print(f"    {key}: {val:.2f}")

        # Expected Open Positions Market Value:
        # Leg 1: 2.50 * 1 * 100 = 250
        # Leg 2: 0.80 * -1 * 100 = -80
        # Total = 250 - 80 = 170
        # Expected Cash = 9500
        # Expected Total Portfolio Value = 9500 + 170 = 9670
        # Expected Overall P&L = RPL_pos2 (50) + UPL_pos1 (70) = 120

    except Exception as e:
        print(f"Error in example: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

    print("\nPortfolio Manager examples finished.")
