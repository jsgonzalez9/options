from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm import Session, joinedload
from . import models
from . import setup # For SessionLocal and engine if needed directly, though session is passed
from typing import List, Dict, Any, Optional
import datetime
from src.core.spread_validator import validate_spread_legs # Moved import to top

# Multiplier for option contracts (typically 100 shares per contract)
OPTION_MULTIPLIER = 100

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
        entry_date=entry_date if entry_date else datetime.datetime.utcnow()
    )
    db.add(db_position)
    # Flush to get db_position.id for foreign key in legs, if not using backref population before commit.
    # However, SQLAlchemy handles this well with relationships. Adding legs to session usually works.
    # db.flush()

    # Validate spread type before creating legs
    # This import should ideally be at the top of the file
    from src.core.spread_validator import validate_spread_legs
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
        db_position.status = new_status.upper()
        if new_status.upper() == "CLOSED" and closing_price is not None:
            db_position.closing_price = closing_price
            # Optionally, update all leg closing prices if not done individually
            # for leg in db_position.legs:
            #     if leg.closing_price_per_unit is None: # Only if not already set
            #         # This is tricky without knowing individual leg closing prices
            #         # Placeholder for more complex logic if needed
            #         pass
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

    # Recalculate cost basis: get all current legs data + new legs data
    # This is simpler: fetch all legs from DB after new ones are flushed (or before commit)
    # For now, we assume cost_basis is additive or needs more complex adjustment logic
    # For simplicity, let's assume the existing cost_basis is correct for existing legs,
    # and we add the cost of new legs.

    new_legs_cost = calculate_position_cost_basis(new_legs_data)
    db_position.cost_basis += new_legs_cost # Add cost of new legs

    # db.commit() # COMMIT IS HANDLED BY CALLER
    db.flush()
    db.refresh(db_position)
    # Eager load legs again after refresh might require re-querying if session state is complex
    # For now, assume refresh is sufficient or caller requeries.
    return db_position # Return the instance that should be in the session


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
        # Potentially update parent position status or P&L here or in a service layer
        # db.commit() # COMMIT IS HANDLED BY CALLER
        db.flush()
        db.refresh(db_leg)
    return db_leg


def add_note_to_position(db: Session, position_id: int, note_text: str, append: bool = True) -> Optional[models.Position]:
    """Adds or appends a note to a position."""
    db_position = get_position_by_id(db, position_id) # This uses joinedload, good.
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
    db_position = get_position_by_id(db, position_id) # Uses joinedload
    if db_position:
        db.delete(db_position)
        # db.commit() # COMMIT IS HANDLED BY CALLER
        db.flush() # Make sure delete operation is sent to DB if other operations follow before commit
        return True
    return False


# --- Example Usage (for testing or direct script execution) ---
if __name__ == '__main__':
    print("Running CRUD example...")
    # Create tables if they don't exist (using a local test DB)
    # This should point to the same DB used by models.py if run together, or a dedicated test DB.
    # For consistency with models.py __main__, let's use a similar DB or in-memory.
    # import os
    # db_file = "trading_journal_crud_test.db"
    # if os.path.exists(db_file):
    #     os.remove(db_file)
    # setup.DATABASE_URL = f"sqlite:///./{db_file}" # Override for this test run

    # Re-create engine if DATABASE_URL was changed in setup
    # setup.engine = setup.create_engine(setup.DATABASE_URL, connect_args={"check_same_thread": False})
    # setup.SessionLocal = setup.sessionmaker(autocommit=False, autoflush=False, bind=setup.engine)

    # Use the setup module's engine and session
    create_db_tables() # Creates tables based on setup.DATABASE_URL

    db_session_gen = setup.get_db_session()
    db = next(db_session_gen)

    try:
        print("\n1. Creating a new Bull Call Spread position...")
        bull_call_legs_data = [
            {"option_type": "CALL", "strike_price": 200.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 5.50},
            {"option_type": "CALL", "strike_price": 210.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 2.50}
        ]
        # Expected cost_basis: (1 * 5.50 - 1 * 2.50) * 100 = 3.00 * 100 = 300.0
        position1 = create_position(db, "Bull Call Spread", bull_call_legs_data, notes="SPY Bull Call")
        print(f"Created position: {position1} with ID {position1.id}, Cost Basis: {position1.cost_basis}")
        for leg in position1.legs:
            print(f"  Leg: {leg}")

        print("\n2. Creating an Iron Condor position...")
        iron_condor_legs = [
            {"option_type": "PUT", "strike_price": 180.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 1.50}, # Buy Put
            {"option_type": "PUT", "strike_price": 190.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 3.50},# Sell Put
            {"option_type": "CALL", "strike_price": 220.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": -1, "entry_price_per_unit": 3.00},# Sell Call
            {"option_type": "CALL", "strike_price": 230.0, "expiry_date": datetime.date(2025, 3, 21), "quantity": 1, "entry_price_per_unit": 1.00}  # Buy Call
        ]
        # Expected cost_basis: (1.50 (debit) - 3.50 (credit) - 3.00 (credit) + 1.00 (debit)) * 100
        # = (2.50 - 6.50) * 100 = -4.00 * 100 = -400.0 (Net Credit)
        position2 = create_position(db, "Iron Condor", iron_condor_legs, notes="SPY Iron Condor, expecting credit")
        print(f"Created position: {position2} with ID {position2.id}, Cost Basis: {position2.cost_basis}")

        print("\n3. Retrieving all OPEN positions:")
        all_open_positions = get_all_positions(db, status="OPEN")
        for pos in all_open_positions:
            print(f"  Found: {pos}, Legs: {len(pos.legs)}")

        print(f"\n4. Updating status of position {position1.id} to CLOSED...")
        updated_pos1 = update_position_status(db, position1.id, "CLOSED", closing_price=350.0) # Closed for a $350 credit
        print(f"Updated position: {updated_pos1}")

        print(f"\n5. Adding a note to position {position2.id}...")
        pos_with_note = add_note_to_position(db, position2.id, "Market moved, considering adjustment.")
        print(f"Position with note: {pos_with_note.notes}")
        pos_with_note = add_note_to_position(db, position2.id, "Decided to hold.")
        print(f"Position with appended note: \n{pos_with_note.notes}")


        if position2.legs:
            first_leg_id = position2.legs[0].id
            print(f"\n6. Updating current price for leg {first_leg_id} of position {position2.id}...")
            updated_leg = update_leg_current_price(db, first_leg_id, 1.80)
            print(f"Updated leg: {updated_leg}, Current Price: {updated_leg.current_price_per_unit}")

        print("\n7. Retrieving position by ID (position2):")
        retrieved_pos2 = get_position_by_id(db, position2.id)
        if retrieved_pos2:
            print(f"Retrieved: {retrieved_pos2}")
            for leg in retrieved_pos2.legs:
                print(f"  Leg: {leg.option_type} {leg.strike_price}, Qty: {leg.quantity}, Entry: {leg.entry_price_per_unit}, Current: {leg.current_price_per_unit}")

        print(f"\n8. Adding new legs to position {position2.id} (e.g. rolling one side - conceptual)")
        # This is a simplified roll; actual rolling involves closing old and opening new.
        # Here, just adding more legs for testing 'add_legs_to_position'
        new_legs_for_pos2 = [
             {"option_type": "PUT", "strike_price": 170.0, "expiry_date": datetime.date(2025, 4, 18), "quantity": 1, "entry_price_per_unit": 0.80},
             {"option_type": "PUT", "strike_price": 180.0, "expiry_date": datetime.date(2025, 4, 18), "quantity": -1, "entry_price_per_unit": 2.00}
        ]
        # Cost of new legs: (0.80 - 2.00) * 100 = -1.20 * 100 = -120 (credit)
        # Original cost_basis for pos2: -400. New cost_basis = -400 - 120 = -520
        pos2_with_added_legs = add_legs_to_position(db, position2.id, new_legs_for_pos2)
        if pos2_with_added_legs:
            print(f"Position {pos2_with_added_legs.id} after adding legs. New CB: {pos2_with_added_legs.cost_basis}. Total legs: {len(pos2_with_added_legs.legs)}")


        # print(f"\n9. Deleting position {position1.id}...")
        # delete_success = delete_position(db, position1.id)
        # print(f"Deletion successful: {delete_success}")
        # self.assertIsNone(crud.get_position_by_id(db, self.position1.id))


    except Exception as e:
        import traceback
        print(f"An error occurred during CRUD operations: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        print("\nClosing DB session for CRUD example.")
        db.close()

    print("\nCRUD example finished.")
