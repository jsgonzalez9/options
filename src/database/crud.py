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
    # This ensures models are loaded when Base.metadata.create_all is called
    setup.create_db_tables()


def calculate_position_cost_basis(legs_data: List[Dict[str, Any]]) -> float:
    """
    Calculates the total cost basis for a position from its legs.
    Assumes legs_data contains dicts with 'quantity' and 'entry_price_per_unit'.
    Cost is (quantity * entry_price_per_unit). Sum this over all legs.
    Multiply by OPTION_MULTIPLIER.
    A positive quantity means bought (debit), negative means sold (credit).
    Overall positive cost_basis is a net debit. Negative is a net credit.
    """
    total_cost = 0.0
    for leg_info in legs_data:
        cost_per_share = leg_info["quantity"] * leg_info["entry_price_per_unit"]
        total_cost += cost_per_share
    return total_cost * OPTION_MULTIPLIER


def create_position(db: Session, spread_type: str, legs_data: List[Dict[str, Any]],
                    status: str = "OPEN", notes: Optional[str] = None,
                    entry_date: Optional[datetime.datetime] = None) -> models.Position:
    """
    Creates a new position and its associated option legs.
    legs_data is a list of dictionaries, each representing an OptionLeg.
    Example leg_data entry:
    {
        "option_type": "CALL", "strike_price": 150.0, "expiry_date": datetime.date(2025, 1, 17),
        "quantity": 1 (long) or -1 (short), "entry_price_per_unit": 2.50
    }
    """

    # Calculate cost basis from legs
    # Note: The `cost_basis` on the Position model is the total for the contracts.
    # `entry_price_per_unit` on OptionLeg is per share.
    cost_basis = calculate_position_cost_basis(legs_data)

    db_position = models.Position(
        spread_type=spread_type,
        cost_basis=cost_basis,
        status=status,
        notes=notes,
        entry_date=entry_date if entry_date else datetime.datetime.utcnow(),
        unrealized_pnl=0.0, # Initial P&L is zero
        realized_pnl=0.0
    )
    db.add(db_position)
    # Flush to get db_position.id for foreign key in legs, if not using backref population before commit.
    # However, SQLAlchemy handles this well with relationships. Adding legs to session usually works.
    # db.flush()

    # Validate spread type before creating legs
    is_valid, validation_message = validate_spread_legs(spread_type, legs_data)
    if not is_valid:
        # If validation fails, we should not proceed. Rollback any session changes (like adding db_position).
        # However, db_position is not yet committed. Raising an error is cleaner.
        # db.rollback() # Not strictly necessary if we raise before commit.
        raise ValueError(f"Spread validation failed for {spread_type}: {validation_message}")

    for leg_info in legs_data:
        db_leg = models.OptionLeg(
            position=db_position, # Associate with the position
            option_type=leg_info["option_type"],
            strike_price=leg_info["strike_price"],
            expiry_date=leg_info["expiry_date"],
            quantity=leg_info["quantity"],
            entry_price_per_unit=leg_info["entry_price_per_unit"],
            # current_price_per_unit can be set later
            # entry_date_leg defaults to now in model
        )
        db.add(db_leg) # Add leg to session; it's already linked to db_position
        # db_position.legs.append(db_leg) # Also valid, happens automatically via back_populates

    db.flush() # Ensure IDs are populated and objects are in session for refresh
    db.refresh(db_position) # Refresh to get all attributes populated, including generated IDs and relationships
    # db.commit() # COMMIT IS HANDLED BY CALLER
    return db_position

def get_position_by_id(db: Session, position_id: int) -> Optional[models.Position]:
    """Retrieves a single position by its ID, including its legs."""
    return db.query(models.Position).options(joinedload(models.Position.legs)).filter(models.Position.id == position_id).first()

def get_all_positions(db: Session, status: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[models.Position]:
    """
    Retrieves all positions, optionally filtered by status, with pagination.
    Includes legs for each position.
    """
    query = db.query(models.Position).options(joinedload(models.Position.legs))
    if status:
        query = query.filter(models.Position.status == status.upper())
    return query.order_by(models.Position.entry_date.desc()).offset(skip).limit(limit).all()

def update_position_status(db: Session, position_id: int, new_status: str,
                           closing_price: Optional[float] = None) -> Optional[models.Position]:
    """Updates the status of a position. If closing, closing_price can be provided."""
    db_position = get_position_by_id(db, position_id)
    if db_position:
        original_status = db_position.status
        new_status_upper = new_status.upper()
        db_position.status = new_status_upper

        if new_status_upper == "CLOSED":
            if closing_price is not None:
                db_position.closing_price = closing_price

            # Calculate and store realized P&L
            # This assumes that if individual leg closing prices are needed, they are already set on the legs.
            db_position.realized_pnl = pnl_calculator.calculate_realized_pnl_for_position(db_position)
            db_position.unrealized_pnl = 0.0 # No unrealized P&L once closed

            # Optionally, if position.closing_price was just set, and we want to ensure leg P&Ls are
            # consistent or legs are marked as closed, this would be the place.
            # For now, calculate_realized_pnl_for_position prefers position.closing_price if available.

        elif original_status == "CLOSED" and new_status_upper != "CLOSED": # E.g. Reopening a position
            db_position.realized_pnl = 0.0 # Clear realized P&L
            db_position.closing_price = None # Clear overall closing price
            # Unrealized P&L would need recalculation based on current market prices.
            # This might be handled by a subsequent call to update_legs_current_prices_and_unrealized_pnl.
            # For now, don't change unrealized_pnl here, let the dedicated function handle it.

        # db.commit() # COMMIT IS HANDLED BY CALLER
        db.flush()
        db.refresh(db_position)
    return db_position

def add_legs_to_position(db: Session, position_id: int, new_legs_data: List[Dict[str, Any]]) -> Optional[models.Position]:
    """Adds new legs to an existing position and recalculates cost basis."""
    db_position = get_position_by_id(db, position_id)
    if not db_position:
        return None

    for leg_info in new_legs_data:
        db_leg = models.OptionLeg(
            position_id=position_id, # Explicitly set, or use position=db_position
            option_type=leg_info["option_type"],
            strike_price=leg_info["strike_price"],
            expiry_date=leg_info["expiry_date"],
            quantity=leg_info["quantity"],
            entry_price_per_unit=leg_info["entry_price_per_unit"],
        )
        db.add(db_leg)
        # db_position.legs.append(db_leg) # Append to relationship if preferred

    new_legs_cost = calculate_position_cost_basis(new_legs_data)
    db_position.cost_basis += new_legs_cost # Add cost of new legs

    # db.commit() # COMMIT IS HANDLED BY CALLER
    db.flush()
    db.refresh(db_position)
    return db_position


def update_leg_current_price(db: Session, leg_id: int, new_price: float) -> Optional[models.OptionLeg]:
    """Updates the current market price of a single option leg."""
    db_leg = db.query(models.OptionLeg).filter(models.OptionLeg.id == leg_id).first()
    if db_leg:
        db_leg.current_price_per_unit = new_price
        # db.commit() # COMMIT IS HANDLED BY CALLER
        db.flush()
        db.refresh(db_leg)
    return db_leg

def update_leg_closing_price(db: Session, leg_id: int, closing_price: float) -> Optional[models.OptionLeg]:
    """Updates the closing price of a single option leg (e.g., when rolled or closed early)."""
    db_leg = db.query(models.OptionLeg).filter(models.OptionLeg.id == leg_id).first()
    if db_leg:
        db_leg.closing_price_per_unit = closing_price
        # db.commit() # COMMIT IS HANDLED BY CALLER
        db.flush()
        db.refresh(db_leg)
    return db_leg


def add_note_to_position(db: Session, position_id: int, note_text: str, append: bool = True) -> Optional[models.Position]:
    """Adds or appends a note to a position."""
    db_position = get_position_by_id(db, position_id)
    if db_position:
        if append and db_position.notes:
            db_position.notes += f"\n---\n{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n{note_text}"
        else:
            db_position.notes = note_text
        # db.commit() # COMMIT IS HANDLED BY CALLER
        db.flush()
        db.refresh(db_position)
    return db_position

def delete_position(db: Session, position_id: int) -> bool:
    """Deletes a position and its associated legs (due to cascade). Hard delete."""
    db_position = get_position_by_id(db, position_id)
    if db_position:
        db.delete(db_position)
        # db.commit() # COMMIT IS HANDLED BY CALLER
        db.flush()
        return True
    return False

def update_legs_current_prices_and_unrealized_pnl(
    db: Session,
    position_id: int,
    leg_current_prices: Dict[int, float],
    # price_fetcher: Optional[AlphaVantageAPI] = None # Placeholder for future use
) -> Optional[models.Position]:
    """
    Updates the current_price_per_unit for specified legs of a position
    and then recalculates and updates the position's total unrealized P&L.

    Args:
        db: The SQLAlchemy session.
        position_id: The ID of the position to update.
        leg_current_prices: A dictionary mapping leg_id to its new current_market_price_per_unit.
                           Example: {101: 2.50, 102: 1.80}

    Returns:
        The updated Position object or None if not found.
    """
    db_position = get_position_by_id(db, position_id) # This already eager loads legs
    if not db_position:
        return None

    if db_position.status == "CLOSED":
        db_position.unrealized_pnl = 0.0 # Closed positions have no unrealized P&L
        db.flush()
        # db.refresh(db_position) # Refresh might not be needed if only UPL is changed and it's the last op
        return db_position

    total_unrealized_pnl_for_position = 0.0
    # legs_updated_count = 0 # Not used currently

    for leg in db_position.legs:
        # Update leg's current price if provided in the input dictionary
        if leg.id in leg_current_prices:
            leg.current_price_per_unit = leg_current_prices[leg.id]
            # legs_updated_count += 1

        leg_pnl = pnl_calculator.calculate_unrealized_pnl_for_leg(leg)
        total_unrealized_pnl_for_position += leg_pnl

    db_position.unrealized_pnl = total_unrealized_pnl_for_position

    db.flush()
    # db.refresh(db_position) # Refresh to ensure the session object has the latest state from DB if needed by caller
                           # For this function, returning the modified db_position should be fine.
    return db_position


# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    print("Running CRUD example...")
    create_db_tables()

    db_session_gen = setup.get_db_session()
    db = next(db_session_gen)

    try:
        print("\n1. Creating a new Bull Call Spread position...")
        bull_call_legs_data = [
            {"option_type": "CALL", "strike_price": 200.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 5.50}, # Leg A
            {"option_type": "CALL", "strike_price": 210.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 2.50} # Leg B
        ]
        position1 = create_position(db, "Bull Call Spread", bull_call_legs_data, notes="SPY Bull Call")
        db.commit()
        print(f"Created position: {position1} with ID {position1.id}, Cost Basis: {position1.cost_basis}, UPL: {position1.unrealized_pnl}")
        leg_ids_pos1 = {leg.strike_price: leg.id for leg in position1.legs}

        print("\n1a. Update current prices and unrealized P&L for position 1")
        # Leg A (long 200C): Entry 5.50. Current 6.00. PNL = (6.00 - 5.50) * 1 * 100 = 50
        # Leg B (short 210C): Entry 2.50. Current 3.00. PNL = (2.50 - 3.00) * 1 * 100 = -50 (Note: pnl_calculator uses (market-entry)*qty)
        # So for Leg B: (3.00 - 2.50) * -1 * 100 = 0.50 * -1 * 100 = -50
        # Total Unrealized P&L = 50 - 50 = 0
        prices_pos1 = {
            leg_ids_pos1[200.0]: 6.00, # Leg A current price
            leg_ids_pos1[210.0]: 3.00  # Leg B current price
        }
        position1_updated_pnl = update_legs_current_prices_and_unrealized_pnl(db, position1.id, prices_pos1)
        db.commit()
        print(f"Position 1 after P&L update: ID {position1_updated_pnl.id}, Unrealized P&L: {position1_updated_pnl.unrealized_pnl:.2f}")


        print("\n2. Creating an Iron Condor position...")
        iron_condor_legs = [
            {"option_type": "PUT", "strike_price": 180.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 1.50},
            {"option_type": "PUT", "strike_price": 190.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 3.50},
            {"option_type": "CALL", "strike_price": 220.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 3.00},
            {"option_type": "CALL", "strike_price": 230.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 1.00}
        ]
        position2 = create_position(db, "Iron Condor", iron_condor_legs, notes="SPY Iron Condor")
        db.commit()
        print(f"Created position: {position2} with ID {position2.id}, Cost Basis: {position2.cost_basis}, UPL: {position2.unrealized_pnl}")

        print("\n3. Retrieving all OPEN positions:")
        all_open_positions = get_all_positions(db, status="OPEN")
        for pos in all_open_positions:
            print(f"  Found: {pos}, Legs: {len(pos.legs)}, UPL: {pos.unrealized_pnl:.2f}, RPL: {pos.realized_pnl:.2f}")

        print(f"\n4. Updating status of position {position1.id} to CLOSED...")
        # Position 1 CB = 300.0. Closed for net $350 credit. RPL = 350 - 300 = 50.
        updated_pos1 = update_position_status(db, position1.id, "CLOSED", closing_price=350.0)
        db.commit()
        print(f"Updated position: {updated_pos1}, Status: {updated_pos1.status}, Realized P&L: {updated_pos1.realized_pnl:.2f}, Unrealized P&L: {updated_pos1.unrealized_pnl:.2f}")

        print(f"\n5. Adding a note to position {position2.id}...")
        # ... (rest of example script remains largely the same) ...
        pos_with_note = add_note_to_position(db, position2.id, "Market moved, considering adjustment.")
        db.commit()
        print(f"Position with note: {pos_with_note.notes}")
        pos_with_note = add_note_to_position(db, position2.id, "Decided to hold.")
        db.commit()
        print(f"Position with appended note: \n{pos_with_note.notes}")


        if position2.legs:
            first_leg_id = position2.legs[0].id
            print(f"\n6. Updating current price for leg {first_leg_id} of position {position2.id}...")
            updated_leg = update_leg_current_price(db, first_leg_id, 1.80)
            db.commit()
            print(f"Updated leg: {updated_leg}, Current Price: {updated_leg.current_price_per_unit}")

        print("\n7. Retrieving position by ID (position2):")
        retrieved_pos2 = get_position_by_id(db, position2.id)
        if retrieved_pos2:
            print(f"Retrieved: {retrieved_pos2}")
            for leg in retrieved_pos2.legs:
                print(f"  Leg: {leg.option_type} {leg.strike_price}, Qty: {leg.quantity}, Entry: {leg.entry_price_per_unit}, Current: {leg.current_price_per_unit}")

        print(f"\n8. Adding new legs to position {position2.id} (e.g. rolling one side - conceptual)")
        new_legs_for_pos2 = [
             {"option_type": "PUT", "strike_price": 170.0, "expiry_date": datetime.date(2025, 4, 18), "quantity": 1, "entry_price_per_unit": 0.80},
             {"option_type": "PUT", "strike_price": 180.0, "expiry_date": datetime.date(2025, 4, 18), "quantity": -1, "entry_price_per_unit": 2.00}
        ]
        pos2_with_added_legs = add_legs_to_position(db, position2.id, new_legs_for_pos2)
        db.commit()
        if pos2_with_added_legs:
            print(f"Position {pos2_with_added_legs.id} after adding legs. New CB: {pos2_with_added_legs.cost_basis}. Total legs: {len(pos2_with_added_legs.legs)}")


    except Exception as e:
        import traceback
        print(f"An error occurred during CRUD operations: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        print("\nClosing DB session for CRUD example.")
        db.close()

    print("\nCRUD example finished.")
