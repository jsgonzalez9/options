import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database import models, crud, setup
from src.core import spread_validator # For direct validator calls if needed, though crud uses it
import datetime
from typing import List, Dict, Any

class TestCrudOperations(unittest.TestCase):

    engine = None
    SessionLocal = None

    @classmethod
    def setUpClass(cls):
        # Set up an in-memory SQLite database for the entire test class
        cls.engine = create_engine("sqlite:///:memory:")
        # Tables will be created/dropped per test method now
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    # No tearDownClass needed if dropping tables per test

    def setUp(self):
        # Create tables fresh for each test
        models.Base.metadata.create_all(self.engine)
        self.db = self.SessionLocal()
        # No need for begin_nested() if we are dropping tables each time

    def tearDown(self):
        self.db.close() # Close the session
        # Drop all tables to ensure clean slate for next test
        models.Base.metadata.drop_all(self.engine)

    def test_calculate_position_cost_basis(self):
        legs_data_debit = [
            {"quantity": 1, "entry_price_per_unit": 2.00}, # 200
            {"quantity": -1, "entry_price_per_unit": 1.00} # -100
        ] # Net: 1.00 per share * 100 = 100.0
        self.assertAlmostEqual(crud.calculate_position_cost_basis(legs_data_debit), 100.0)

        legs_data_credit = [
            {"quantity": -1, "entry_price_per_unit": 3.00}, # -300
            {"quantity": 1, "entry_price_per_unit": 0.50}   # 50
        ] # Net: -2.50 per share * 100 = -250.0
        self.assertAlmostEqual(crud.calculate_position_cost_basis(legs_data_credit), -250.0)

        legs_data_stock = [ # Simulating a stock purchase (though model is OptionLeg)
            {"quantity": 100, "entry_price_per_unit": 150.00}
        ]
        # If OPTION_MULTIPLIER is 1 for stocks, result is 15000. If 100, it's 1.5M.
        # Our current calculate_position_cost_basis assumes options.
        # For stock positions, cost_basis would be calculated differently or set directly.
        # Test with current logic: 100 * 150 * 100 = 1,500,000. This highlights a need for context.
        # For now, this function is only for options.
        # A "Stock" position type would bypass this specific calculation in create_position.
        # self.assertAlmostEqual(crud.calculate_position_cost_basis(legs_data_stock), 1500000.0)


    def test_create_and_get_position_valid_bull_call(self):
        bcs_legs_data: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.00}
        ]
        # Expected cost_basis = (1*2.00 - 1*1.00) * 100 = 100.0
        position = crud.create_position(self.db, "Bull Call Spread", bcs_legs_data, notes="Test BCS")

        self.assertIsNotNone(position.id)
        self.assertEqual(position.spread_type, "Bull Call Spread")
        self.assertAlmostEqual(position.cost_basis, 100.0)
        self.assertEqual(len(position.legs), 2)
        self.assertEqual(position.legs[0].strike_price, 100.0)

        retrieved_pos = crud.get_position_by_id(self.db, position.id)
        self.assertIsNotNone(retrieved_pos)
        self.assertEqual(retrieved_pos.id, position.id)
        self.assertEqual(len(retrieved_pos.legs), 2)

    def test_create_position_invalid_bull_call_fails(self):
        invalid_bcs_legs: List[Dict[str, Any]] = [ # Missing short leg
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00}
        ]
        with self.assertRaisesRegex(ValueError, "Spread validation failed for Bull Call Spread: Bull Call Spread must have exactly two legs."):
            crud.create_position(self.db, "Bull Call Spread", invalid_bcs_legs)

    def test_create_and_get_position_valid_iron_condor(self):
        ic_legs_data: List[Dict[str, Any]] = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 1.00},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 2.50},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 0.80}
        ]
        # Cost: (1.00 - 2.00 - 2.50 + 0.80) * 100 = (-1.00 - 1.70) * 100 = -2.70 * 100 = -270.0 (credit)
        position = crud.create_position(self.db, "Iron Condor", ic_legs_data, notes="Test IC")
        self.assertIsNotNone(position.id)
        self.assertEqual(position.spread_type, "Iron Condor")
        self.assertAlmostEqual(position.cost_basis, -270.0)
        self.assertEqual(len(position.legs), 4)

    def test_create_position_custom_spread_no_validation_error(self):
        # Assumes custom spreads without specific validators are allowed
        custom_legs: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00}
        ]
        position = crud.create_position(self.db, "My Custom Spread", custom_legs)
        self.assertIsNotNone(position.id)
        self.assertEqual(position.spread_type, "My Custom Spread")
        self.assertEqual(len(position.legs), 1)

    def test_get_all_positions(self):
        bcs_legs_data: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.00}
        ]
        crud.create_position(self.db, "Bull Call Spread", bcs_legs_data, status="OPEN")
        crud.create_position(self.db, "Iron Condor", [ # Minimal data for another position
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit": 1.0},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025,1,17), "quantity": -1, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025,1,17), "quantity": -1, "entry_price_per_unit": 2.5},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit": 0.8}
        ], status="CLOSED")

        self.db.commit() # Commit the created positions so they are queryable

        all_pos = crud.get_all_positions(self.db)
        self.assertEqual(len(all_pos), 2)

        open_pos = crud.get_all_positions(self.db, status="OPEN")
        self.assertEqual(len(open_pos), 1)
        self.assertEqual(open_pos[0].spread_type, "Bull Call Spread")

        closed_pos = crud.get_all_positions(self.db, status="CLOSED")
        self.assertEqual(len(closed_pos), 1)

    def test_update_position_status(self):
        pos = crud.create_position(self.db, "Test Status", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1}])
        self.db.commit() # Commit pos
        self.assertEqual(pos.status, "OPEN")

        updated_pos = crud.update_position_status(self.db, pos.id, "CLOSED", closing_price=150.0)
        self.assertIsNotNone(updated_pos)
        self.assertEqual(updated_pos.status, "CLOSED")
        self.assertEqual(updated_pos.closing_price, 150.0)

    def test_add_legs_to_position(self):
        pos = crud.create_position(self.db, "Test Add Legs", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}]) # CB = 100
        self.db.commit() # Commit pos
        original_leg_count = len(pos.legs)
        original_cb = pos.cost_basis

        new_legs_data: List[Dict[str, Any]] = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 1), "quantity": -1, "entry_price_per_unit": 0.50} # Credit -50
        ]
        # Cost of new legs = -1 * 0.50 * 100 = -50.0
        # New CB = 100.0 - 50.0 = 50.0

        updated_pos = crud.add_legs_to_position(self.db, pos.id, new_legs_data)
        self.assertIsNotNone(updated_pos)
        self.assertEqual(len(updated_pos.legs), original_leg_count + 1)
        self.assertAlmostEqual(updated_pos.cost_basis, original_cb - 50.0)

    def test_update_leg_current_price(self):
        pos = crud.create_position(self.db, "Test Leg Price", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit() # Commit pos
        leg_id = pos.legs[0].id

        updated_leg = crud.update_leg_current_price(self.db, leg_id, 1.50)
        self.assertIsNotNone(updated_leg)
        self.assertEqual(updated_leg.current_price_per_unit, 1.50)

    def test_update_leg_closing_price(self):
        pos = crud.create_position(self.db, "Test Leg Close Price", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit() # Commit pos
        leg_id = pos.legs[0].id

        updated_leg = crud.update_leg_closing_price(self.db, leg_id, 1.80)
        self.assertIsNotNone(updated_leg)
        self.assertEqual(updated_leg.closing_price_per_unit, 1.80)


    def test_add_note_to_position(self):
        pos = crud.create_position(self.db, "Test Notes", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit() # Commit pos
        self.assertIsNone(pos.notes)

        crud.add_note_to_position(self.db, pos.id, "First note.")
        self.db.refresh(pos) # Refresh to see changes from crud function
        self.assertIn("First note.", pos.notes)

        crud.add_note_to_position(self.db, pos.id, "Second note.", append=True)
        self.db.refresh(pos)
        self.assertIn("First note.", pos.notes)
        self.assertIn("Second note.", pos.notes)
        self.assertIn("---\n", pos.notes) # Check for separator

        crud.add_note_to_position(self.db, pos.id, "Replaced note.", append=False)
        self.db.refresh(pos)
        self.assertEqual(pos.notes, "Replaced note.")


    def test_delete_position(self):
        pos = crud.create_position(self.db, "Test Delete", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit() # Commit pos
        position_id = pos.id
        leg_id = pos.legs[0].id

        self.assertIsNotNone(crud.get_position_by_id(self.db, position_id))
        # Check leg exists too
        self.assertIsNotNone(self.db.query(models.OptionLeg).get(leg_id))


        delete_success = crud.delete_position(self.db, position_id)
        self.assertTrue(delete_success)
        self.assertIsNone(crud.get_position_by_id(self.db, position_id))
        # Check leg is also deleted due to cascade
        self.assertIsNone(self.db.query(models.OptionLeg).get(leg_id))

        delete_fail = crud.delete_position(self.db, 99999) # Non-existent ID
        self.assertFalse(delete_fail)

if __name__ == '__main__':
    unittest.main()
