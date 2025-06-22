import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base, Position, OptionLeg
import datetime

class TestDatabaseModels(unittest.TestCase):

    def setUp(self):
        # Use an in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine) # Create tables
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine) # Drop tables after tests

    def test_create_position(self):
        entry_time = datetime.datetime.utcnow()
        position = Position(
            spread_type="Test Spread",
            status="OPEN",
            cost_basis=100.0,
            entry_date=entry_time,
            notes="Test notes"
        )
        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)

        self.assertIsNotNone(position.id)
        self.assertEqual(position.spread_type, "Test Spread")
        self.assertEqual(position.status, "OPEN")
        self.assertEqual(position.cost_basis, 100.0)
        self.assertEqual(position.entry_date, entry_time)
        self.assertEqual(position.notes, "Test notes")
        self.assertEqual(len(position.legs), 0) # No legs added yet

    def test_create_option_leg(self):
        # First, create a position to associate the leg with
        position = Position(spread_type="Test For Leg", cost_basis=0)
        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)

        expiry_d = datetime.date(2025, 12, 31)
        leg_entry_time = datetime.datetime.utcnow()

        leg = OptionLeg(
            position_id=position.id, # Direct assignment
            option_type="CALL",
            strike_price=150.0,
            expiry_date=expiry_d,
            quantity=1,
            entry_price_per_unit=2.50,
            current_price_per_unit=2.60,
            entry_date_leg=leg_entry_time
        )
        self.db.add(leg)
        self.db.commit()
        self.db.refresh(leg)

        self.assertIsNotNone(leg.id)
        self.assertEqual(leg.position_id, position.id)
        self.assertEqual(leg.option_type, "CALL")
        self.assertEqual(leg.strike_price, 150.0)
        self.assertEqual(leg.expiry_date, expiry_d)
        self.assertEqual(leg.quantity, 1)
        self.assertEqual(leg.entry_price_per_unit, 2.50)
        self.assertEqual(leg.current_price_per_unit, 2.60)
        self.assertEqual(leg.entry_date_leg, leg_entry_time)

    def test_position_with_legs_relationship(self):
        position = Position(spread_type="Spread With Legs", cost_basis=50.0)
        # Add legs directly to the position's collection
        leg1_expiry = datetime.date(2025, 1, 1)
        leg2_expiry = datetime.date(2025, 1, 1)

        leg1 = OptionLeg(
            option_type="CALL", strike_price=100.0, expiry_date=leg1_expiry,
            quantity=1, entry_price_per_unit=1.0
        )
        leg2 = OptionLeg(
            option_type="CALL", strike_price=105.0, expiry_date=leg2_expiry,
            quantity=-1, entry_price_per_unit=0.5
        )

        # Append to the relationship. This should set leg.position backref.
        position.legs.append(leg1)
        position.legs.append(leg2)

        self.db.add(position)
        self.db.commit()
        self.db.refresh(position)
        # Refresh legs individually if they were not part of the cascade for refresh from position
        # or if their FKs were set by SQLAlchemy's magic before commit.
        # Typically, refreshing the parent (Position) should make the child collection available.
        # For explicit access to leg IDs etc., refresh them too if needed.
        self.db.refresh(leg1) # if leg1 was added separately to session or to see its generated ID
        self.db.refresh(leg2)


        self.assertIsNotNone(position.id)
        self.assertEqual(len(position.legs), 2)

        # Verify back-population and FK
        retrieved_leg1 = self.db.query(OptionLeg).filter_by(id=leg1.id).first()
        retrieved_leg2 = self.db.query(OptionLeg).filter_by(id=leg2.id).first()

        self.assertIsNotNone(retrieved_leg1)
        self.assertIsNotNone(retrieved_leg2)
        self.assertEqual(retrieved_leg1.position_id, position.id)
        self.assertEqual(retrieved_leg2.position_id, position.id)
        self.assertEqual(retrieved_leg1.position, position) # Check backref object

        # Check if legs are accessible from position object
        self.assertIn(retrieved_leg1, position.legs)
        self.assertIn(retrieved_leg2, position.legs)


    def test_cascade_delete_position_legs(self):
        position = Position(spread_type="Cascade Test", cost_basis=10.0)
        leg = OptionLeg(
            option_type="PUT", strike_price=50.0, expiry_date=datetime.date(2025, 6, 1),
            quantity=1, entry_price_per_unit=0.10
        )
        position.legs.append(leg)

        self.db.add(position)
        self.db.commit()

        position_id = position.id
        leg_id = leg.id # Assuming leg gets an ID after commit due to being part of position

        self.assertIsNotNone(self.db.query(Position).get(position_id))
        self.assertIsNotNone(self.db.query(OptionLeg).get(leg_id))

        # Delete the position
        self.db.delete(position)
        self.db.commit()

        # Check if position and its leg are deleted (due to cascade="all, delete-orphan")
        self.assertIsNone(self.db.query(Position).get(position_id))
        self.assertIsNone(self.db.query(OptionLeg).get(leg_id))


if __name__ == '__main__':
    unittest.main()
