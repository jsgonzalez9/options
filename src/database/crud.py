from sqlalchemy.orm import Session, joinedload
from . import models
from . import setup # For SessionLocal and engine if needed directly, though session is passed
from typing import List, Dict, Any, Optional
import datetime
from src.core.spread_validator import validate_spread_legs
from src.core import pnl_calculator # For P&L calculations
from src.api.alpha_vantage import AlphaVantageAPI # For type hinting PriceFetcher
from src.config import OPTION_MULTIPLIER # Centralized configuration

def create_db_tables():
    """Utility function to create tables. Delegates to setup.py or can be called directly."""
    setup.create_db_tables()


def calculate_position_cost_basis(legs_data: List[Dict[str, Any]]) -> float:
    """
    Calculates the total cost basis for a position from its option legs.
    """
    total_cost = 0.0
    for leg_info in legs_data:
        cost_per_share = leg_info["quantity"] * leg_info["entry_price_per_unit"]
        total_cost += cost_per_share
    return total_cost * OPTION_MULTIPLIER


def create_position(db: Session, spread_type: str, legs_data: List[Dict[str, Any]],
                    status: str = "OPEN", notes: Optional[str] = None,
                    entry_date: Optional[datetime.datetime] = None,
                    underlying_symbol: Optional[str] = None,
                    is_stock_position: bool = False,
                    stock_quantity: Optional[int] = None) -> models.Position:

    cost_basis = 0.0
    if is_stock_position:
        if not stock_quantity or not legs_data or not legs_data[0].get("entry_price_per_unit"):
            raise ValueError("For stock positions, stock_quantity and entry_price_per_unit (in legs_data[0]) are required.")
        cost_basis = stock_quantity * legs_data[0]["entry_price_per_unit"]
    elif legs_data: # Option spread
        cost_basis = calculate_position_cost_basis(legs_data)

    db_position = models.Position(
        underlying_symbol=underlying_symbol,
        spread_type=spread_type,
        is_stock_position=is_stock_position,
        stock_quantity=stock_quantity if is_stock_position else None,
        cost_basis=cost_basis,
        status=status,
        notes=notes,
        entry_date=entry_date if entry_date else datetime.datetime.utcnow(),
        unrealized_pnl=0.0,
        realized_pnl=0.0
    )
    db.add(db_position) # Add position to session

    if not is_stock_position and legs_data:
        is_valid, validation_message = validate_spread_legs(spread_type, legs_data)
        if not is_valid:
            raise ValueError(f"Spread validation failed for {spread_type}: {validation_message}")

    if legs_data:
        for leg_info in legs_data:
            db_leg = models.OptionLeg(
                option_type=leg_info["option_type"],
                strike_price=leg_info["strike_price"],
                expiry_date=leg_info["expiry_date"],
                quantity=leg_info["quantity"],
                entry_price_per_unit=leg_info["entry_price_per_unit"],
            )
            db_position.legs.append(db_leg) # Append to collection, SQLAlchemy handles session add via cascade

    db.flush()
    db.refresh(db_position)
    # Eagerly load legs after refresh to ensure they are available to the caller
    if db_position.legs:
        for leg in db_position.legs: # This access will trigger lazy load if not already loaded
            pass # Or db.refresh(leg) if individual leg attributes need to be up-to-date from DB

    return db_position

def get_position_by_id(db: Session, position_id: int) -> Optional[models.Position]:
    return db.query(models.Position).options(joinedload(models.Position.legs)).filter(models.Position.id == position_id).first()

def get_all_positions(db: Session, status: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[models.Position]:
    query = db.query(models.Position).options(joinedload(models.Position.legs))
    if status:
        query = query.filter(models.Position.status == status.upper())
    return query.order_by(models.Position.entry_date.desc()).offset(skip).limit(limit).all()

def update_position_status(db: Session, position_id: int, new_status: str,
                           closing_price: Optional[float] = None) -> Optional[models.Position]:
    db_position = get_position_by_id(db, position_id)
    if db_position:
        original_status = db_position.status
        new_status_upper = new_status.upper()
        db_position.status = new_status_upper

        if new_status_upper == "CLOSED":
            if closing_price is not None:
                db_position.closing_price = closing_price
            db_position.realized_pnl = pnl_calculator.calculate_realized_pnl_for_position(db_position)
            db_position.unrealized_pnl = 0.0
        elif original_status == "CLOSED" and new_status_upper != "CLOSED":
            db_position.realized_pnl = 0.0
            db_position.closing_price = None
        db.flush()
        db.refresh(db_position)
    return db_position

def add_legs_to_position(db: Session, position_id: int, new_legs_data: List[Dict[str, Any]]) -> Optional[models.Position]:
    db_position = get_position_by_id(db, position_id)
    if not db_position or db_position.is_stock_position: # Cannot add legs to a stock position this way
        return None

    for leg_info in new_legs_data:
        db_leg = models.OptionLeg(
            option_type=leg_info["option_type"],
            strike_price=leg_info["strike_price"],
            expiry_date=leg_info["expiry_date"],
            quantity=leg_info["quantity"],
            entry_price_per_unit=leg_info["entry_price_per_unit"],
        )
        db_position.legs.append(db_leg)

    # Recalculate cost basis based on ALL legs for an option spread
    all_legs_data_for_recalc = [{
        "quantity": leg.quantity,
        "entry_price_per_unit": leg.entry_price_per_unit
    } for leg in db_position.legs]
    db_position.cost_basis = calculate_position_cost_basis(all_legs_data_for_recalc)

    db.flush()
    db.refresh(db_position)
    if db_position.legs:
        for leg in db_position.legs: pass
    return db_position


def update_leg_current_price(db: Session, leg_id: int, new_price: float) -> Optional[models.OptionLeg]:
    db_leg = db.query(models.OptionLeg).filter(models.OptionLeg.id == leg_id).first()
    if db_leg:
        db_leg.current_price_per_unit = new_price
        db.flush()
        db.refresh(db_leg)
    return db_leg

def update_leg_closing_price(db: Session, leg_id: int, closing_price: float) -> Optional[models.OptionLeg]:
    db_leg = db.query(models.OptionLeg).filter(models.OptionLeg.id == leg_id).first()
    if db_leg:
        db_leg.closing_price_per_unit = closing_price
        db.flush()
        db.refresh(db_leg)
    return db_leg

def add_note_to_position(db: Session, position_id: int, note_text: str, append: bool = True) -> Optional[models.Position]:
    db_position = get_position_by_id(db, position_id)
    if db_position:
        if append and db_position.notes:
            db_position.notes += f"\n---\n{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n{note_text}"
        else:
            db_position.notes = note_text
        db.flush()
        db.refresh(db_position)
    return db_position

def delete_position(db: Session, position_id: int) -> bool:
    db_position = get_position_by_id(db, position_id)
    if db_position:
        db.delete(db_position)
        db.flush()
        return True
    return False

def update_legs_current_prices_and_unrealized_pnl(
    db: Session,
    position_id: int,
    leg_current_prices: Dict[int, float],
) -> Optional[models.Position]:
    db_position = get_position_by_id(db, position_id)
    if not db_position:
        return None

    if db_position.status == "CLOSED":
        db_position.unrealized_pnl = 0.0
        db.flush()
        return db_position

    total_unrealized_pnl_for_position = 0.0

    if db_position.is_stock_position and db_position.legs:
        # For stock, UPL is based on position.stock_quantity and its single representative leg's prices
        stock_leg = db_position.legs[0]
        if stock_leg.id in leg_current_prices:
            stock_leg.current_price_per_unit = leg_current_prices[stock_leg.id]

        if stock_leg.current_price_per_unit is not None and db_position.stock_quantity is not None:
            # Assuming the leg's entry_price_per_unit is the stock's entry price.
            total_unrealized_pnl_for_position = pnl_calculator.calculate_stock_position_unrealized_pnl(
                stock_quantity=db_position.stock_quantity,
                entry_price_per_unit=stock_leg.entry_price_per_unit,
                current_market_price=stock_leg.current_price_per_unit
            )
    elif not db_position.is_stock_position and db_position.legs: # Option spread
        for leg in db_position.legs:
            if leg.id in leg_current_prices:
                leg.current_price_per_unit = leg_current_prices[leg.id]
            leg_pnl = pnl_calculator.calculate_unrealized_pnl_for_leg(leg)
            total_unrealized_pnl_for_position += leg_pnl

    db_position.unrealized_pnl = total_unrealized_pnl_for_position

    db.flush()
    return db_position

# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    # ... (example usage code remains largely the same, ensure it's updated if method signatures changed)
    print("Running CRUD example...")
    create_db_tables()

    db_session_gen = setup.get_db_session()
    db = next(db_session_gen)

    try:
        print("\n1. Creating a new Bull Call Spread position...")
        bull_call_legs_data = [
            {"option_type": "CALL", "strike_price": 200.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 5.50},
            {"option_type": "CALL", "strike_price": 210.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 2.50}
        ]
        position1 = create_position(db, "Bull Call Spread", bull_call_legs_data, notes="SPY Bull Call", underlying_symbol="SPY")
        db.commit()
        print(f"Created position: {position1} with ID {position1.id}, Cost Basis: {position1.cost_basis}, UPL: {position1.unrealized_pnl}")
        if position1.legs:
            leg_ids_pos1 = {leg.strike_price: leg.id for leg in position1.legs}

            print("\n1a. Update current prices and unrealized P&L for position 1")
            prices_pos1 = {
                leg_ids_pos1[200.0]: 6.00,
                leg_ids_pos1[210.0]: 3.00
            }
            position1_updated_pnl = update_legs_current_prices_and_unrealized_pnl(db, position1.id, prices_pos1)
            db.commit()
            print(f"Position 1 after P&L update: ID {position1_updated_pnl.id}, Unrealized P&L: {position1_updated_pnl.unrealized_pnl:.2f}")


        print("\n2. Creating an Iron Condor position...")
        # ... (rest of example script)
        iron_condor_legs = [
            {"option_type": "PUT", "strike_price": 180.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 1.50},
            {"option_type": "PUT", "strike_price": 190.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 3.50},
            {"option_type": "CALL", "strike_price": 220.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 3.00},
            {"option_type": "CALL", "strike_price": 230.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 1.00}
        ]
        position2 = create_position(db, "Iron Condor", iron_condor_legs, notes="SPY Iron Condor", underlying_symbol="SPY")
        db.commit()
        print(f"Created position: {position2} with ID {position2.id}, Cost Basis: {position2.cost_basis}, UPL: {position2.unrealized_pnl}")

        print("\n2b. Creating a Stock position...")
        stock_leg_data = [{
            "option_type": "STOCK", "strike_price": 0, "expiry_date": datetime.date(2023,1,1), # Expiry/strike N/A for stock
            "quantity": 100, "entry_price_per_unit": 150.00
        }]
        position3 = create_position(db, underlying_symbol="AAPL", spread_type="Stock",
                                    is_stock_position=True, stock_quantity=100,
                                    legs_data=stock_leg_data, notes="AAPL Stock Holding")
        db.commit()
        print(f"Created stock position: {position3} with ID {position3.id}, Cost Basis: {position3.cost_basis}, UPL: {position3.unrealized_pnl}")
        if position3.legs:
             prices_pos3 = {position3.legs[0].id: 155.00} # Current price for AAPL stock
             position3_updated_pnl = update_legs_current_prices_and_unrealized_pnl(db, position3.id, prices_pos3)
             db.commit()
             print(f"Stock Position 3 after P&L update: ID {position3_updated_pnl.id}, UPL: {position3_updated_pnl.unrealized_pnl:.2f}")


        print("\n3. Retrieving all OPEN positions:")
        # ... (rest of example script)

    except Exception as e:
        import traceback
        print(f"An error occurred during CRUD operations: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        print("\nClosing DB session for CRUD example.")
        db.close()

    print("\nCRUD example finished.")
