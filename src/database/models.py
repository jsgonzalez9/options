import sqlalchemy # Import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, Text, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    underlying_symbol = Column(String, nullable=True, index=True)
    spread_type = Column(String, index=True, nullable=False)
    entry_date = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    status = Column(String, default="OPEN", index=True)

    # Fields for stock positions
    is_stock_position = Column(sqlalchemy.Boolean, default=False, nullable=False) # Corrected to sqlalchemy.Boolean
    stock_quantity = Column(Integer, nullable=True) # Number of shares for a stock position
    # cost_basis is the net cost to open the position. Positive if debit, negative if credit.
    cost_basis = Column(Float, nullable=False, default=0.0)
    closing_price = Column(Float, nullable=True) # Net price when position is closed
    notes = Column(Text, nullable=True)

    # P&L fields
    unrealized_pnl = Column(Float, nullable=True, default=0.0)
    realized_pnl = Column(Float, nullable=True, default=0.0)

    # Relationship to OptionLeg: A position can have multiple legs
    legs = relationship("OptionLeg", back_populates="position", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Position(id={self.id}, type='{self.spread_type}', status='{self.status}', cost_basis={self.cost_basis})>"


class OptionLeg(Base):
    __tablename__ = "option_legs"

    id = Column(Integer, primary_key=True, index=True)
    position_id = Column(Integer, ForeignKey("positions.id"), nullable=False, index=True) # Add index (FKs often auto-indexed but explicit is fine)

    option_type = Column(String, nullable=False)  # "CALL" or "PUT"
    strike_price = Column(Float, nullable=False)
    expiry_date = Column(Date, nullable=False, index=True) # Add index

    # Quantity: positive for long (bought), negative for short (sold)
    quantity = Column(Integer, nullable=False)

    # Price per unit/share at which this leg was entered.
    # For a bought option, this is the debit. For a sold option, this is the credit.
    entry_price_per_unit = Column(Float, nullable=False)

    current_price_per_unit = Column(Float, nullable=True) # For P&L tracking later
    closing_price_per_unit = Column(Float, nullable=True) # Price when this specific leg is closed/expires

    # entry_date_leg is useful if legs are added/modified at different times than the parent position's entry_date
    entry_date_leg = Column(DateTime, default=datetime.datetime.utcnow)

    position = relationship("Position", back_populates="legs")

    def __repr__(self):
        direction = "Long" if self.quantity > 0 else "Short"
        abs_quantity = abs(self.quantity)
        return (f"<OptionLeg(id={self.id}, pos_id={self.position_id}, {direction} {abs_quantity} "
                f"{self.option_type} @ {self.strike_price:.2f} Exp: {self.expiry_date.strftime('%Y-%m-%d')} "
                f"EntryPrc: {self.entry_price_per_unit:.2f})>")


class PortfolioSetting(Base):
    __tablename__ = "portfolio_settings"

    key = Column(String, primary_key=True, index=True) # e.g., "cash_balance"
    value = Column(Float, nullable=False)

    def __repr__(self):
        return f"<PortfolioSetting(key='{self.key}', value={self.value})>"


if __name__ == '__main__':
    # This section is for basic testing or direct execution of this file.
    # In a real application, table creation is typically handled by a migration tool
    # or a setup script like the one in `setup.py`.

    print("Defining database engine and creating tables for models.py direct execution...")
    # Use an in-memory SQLite database for this example, or a file-based one.
    # DATABASE_URL = "sqlite:///:memory:"
    DATABASE_URL = "sqlite:///./trading_journal_models_test.db" # Test with a file

    engine = create_engine(DATABASE_URL)

    print(f"Creating tables in {DATABASE_URL}...")
    Base.metadata.create_all(bind=engine)
    print("Tables created (or already exist).")

    SessionLocalExample = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocalExample()
    print("Test session created.")

    # Example: Create a dummy position with legs
    try:
        print("\nAttempting to create a sample position...")

        # Calculate cost_basis from legs
        # Leg 1: Buy 1 Call @ $2.00 -> cost = 1 * 2.00 * 100 = $200 (assuming 100 shares/contract)
        # Leg 2: Sell 1 Call @ $1.00 -> credit = -1 * 1.00 * 100 = -$100
        # Net cost_basis = 200 - 100 = $100 (debit)

        # For cost_basis on Position, we'll sum (leg.quantity * leg.entry_price_per_unit * 100)
        # Note: quantity is +ve for buy, -ve for sell.
        # So, for a bought leg: +1 * 2.00 = +2.00 (per share)
        # For a sold leg: -1 * 1.00 = -1.00 (per share)
        # Net per share = +1.00. For 1 contract (100 shares usually): 1.00 * 100 = $100.

        leg1_data = {
            "option_type": "CALL", "strike_price": 155.0,
            "expiry_date": datetime.date(2024, 12, 20),
            "quantity": 1, "entry_price_per_unit": 2.50
        }
        leg2_data = {
            "option_type": "CALL", "strike_price": 160.0,
            "expiry_date": datetime.date(2024, 12, 20),
            "quantity": -1, "entry_price_per_unit": 1.20
        }

        # Cost basis calculation:
        # Leg1: 1 * 2.50 = 2.50 (debit)
        # Leg2: -1 * 1.20 = -1.20 (credit received)
        # Net cost per share = 2.50 - 1.20 = 1.30.
        # If 1 contract = 100 shares, total cost_basis = 1.30 * 100 = 130.00
        # The CRUD function will handle this calculation. Here, we'd set it manually if creating directly.
        calculated_cost_basis = (leg1_data["quantity"] * leg1_data["entry_price_per_unit"] + \
                                leg2_data["quantity"] * leg2_data["entry_price_per_unit"]) * 100 # Assuming 100 multiplier

        new_position = Position(
            spread_type="Bull Call Spread",
            status="OPEN",
            cost_basis=calculated_cost_basis, # This would be calculated by CRUD logic
            notes="Example Bull Call Spread for AAPL"
        )

        leg1 = OptionLeg(**leg1_data, position=new_position)
        leg2 = OptionLeg(**leg2_data, position=new_position)

        # db.add(new_position) # Adding position cascades to legs
        # If not using cascade on position for legs, add them individually or via new_position.legs.append()
        db.add_all([new_position, leg1, leg2]) # More explicit if not relying on cascade from Position for legs initially.
                                              # Corrected: new_position already has legs via relationship.
                                              # db.add(new_position) should be enough if cascade is set up.
                                              # Let's test with db.add(new_position)

        db.add(new_position) # This should add legs too due to cascade.
        db.commit()
        db.refresh(new_position) # To get ID and see legs if they were cascaded.

        print(f"Created Position: {new_position}")
        if new_position.legs:
            for leg in new_position.legs:
                print(f"  With Leg: {leg}")
        else:
            print("  Position was created without legs or legs were not cascaded/retrieved correctly.")

        # Query back
        retrieved_pos = db.query(Position).filter_by(id=new_position.id).first()
        print(f"\nRetrieved Position: {retrieved_pos}")
        if retrieved_pos and retrieved_pos.legs:
            for leg in retrieved_pos.legs:
                print(f"  Retrieved Leg: {leg}")

        print("\nSample data interaction complete.")

    except Exception as e:
        db.rollback()
        print(f"Error during example data interaction: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        print("Test session closed.")

    print("\nTo use these models and setup in your application:")
    print("1. Ensure `src.database.setup.create_db_tables()` is called once at application startup.")
    print("2. Use `src.database.setup.get_db_session()` to get a session for CRUD operations.")
