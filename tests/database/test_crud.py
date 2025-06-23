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
        cls.engine = create_engine("sqlite:///:memory:")
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

    def setUp(self):
        models.Base.metadata.create_all(self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.rollback() # Ensure session is rolled back if a commit failed or was missed.
        self.db.close()
        models.Base.metadata.drop_all(self.engine)

    def test_calculate_position_cost_basis(self):
        legs_data_debit = [
            {"quantity": 1, "entry_price_per_unit": 2.00},
            {"quantity": -1, "entry_price_per_unit": 1.00}
        ]
        self.assertAlmostEqual(crud.calculate_position_cost_basis(legs_data_debit), 100.0)

        legs_data_credit = [
            {"quantity": -1, "entry_price_per_unit": 3.00},
            {"quantity": 1, "entry_price_per_unit": 0.50}
        ]
        self.assertAlmostEqual(crud.calculate_position_cost_basis(legs_data_credit), -250.0)

    def test_create_and_get_position_valid_bull_call(self):
        bcs_legs_data: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.00}
        ]
        position = crud.create_position(self.db, "Bull Call Spread", bcs_legs_data, notes="Test BCS")
        self.db.commit()
        self.db.refresh(position)
        for leg in position.legs: self.db.refresh(leg) # Ensure legs are fully loaded/refreshed

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
        invalid_bcs_legs: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00}
        ]
        with self.assertRaisesRegex(ValueError, "Spread validation failed for Bull Call Spread: Bull Call Spread must have exactly two legs."):
            crud.create_position(self.db, "Bull Call Spread", invalid_bcs_legs)
        self.db.rollback() # Ensure rollback after expected error

    def test_create_and_get_position_valid_iron_condor(self):
        ic_legs_data: List[Dict[str, Any]] = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 1.00},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 2.50},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 0.80}
        ]
        position = crud.create_position(self.db, "Iron Condor", ic_legs_data, notes="Test IC")
        self.db.commit()
        self.db.refresh(position)
        for leg in position.legs: self.db.refresh(leg)

        self.assertIsNotNone(position.id)
        self.assertEqual(position.spread_type, "Iron Condor")
        self.assertAlmostEqual(position.cost_basis, -270.0)
        self.assertEqual(len(position.legs), 4)

    def test_create_position_custom_spread_no_validation_error(self):
        custom_legs: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00}
        ]
        position = crud.create_position(self.db, "My Custom Spread", custom_legs)
        self.db.commit()
        self.db.refresh(position)
        if position.legs: # Check if legs exist before trying to refresh them
             for leg in position.legs: self.db.refresh(leg)

        self.assertIsNotNone(position.id)
        self.assertEqual(position.spread_type, "My Custom Spread")
        self.assertEqual(len(position.legs), 1)

    def test_get_all_positions(self):
        bcs_legs_data: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1, "entry_price_per_unit": 1.00}
        ]
        crud.create_position(self.db, "Bull Call Spread", bcs_legs_data, status="OPEN")
        crud.create_position(self.db, "Iron Condor", [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit": 1.0},
            {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025,1,17), "quantity": -1, "entry_price_per_unit": 2.0},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025,1,17), "quantity": -1, "entry_price_per_unit": 2.5},
            {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit": 0.8}
        ], status="CLOSED")
        self.db.commit()

        all_pos = crud.get_all_positions(self.db)
        self.assertEqual(len(all_pos), 2)

        open_pos = crud.get_all_positions(self.db, status="OPEN")
        self.assertEqual(len(open_pos), 1)
        self.assertEqual(open_pos[0].spread_type, "Bull Call Spread")

        closed_pos = crud.get_all_positions(self.db, status="CLOSED")
        self.assertEqual(len(closed_pos), 1)

    def test_update_position_status(self):
        pos = crud.create_position(self.db, "Test Status", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit()
        self.assertEqual(pos.status, "OPEN")

        updated_pos = crud.update_position_status(self.db, pos.id, "CLOSED", closing_price=150.0)
        self.db.commit()
        self.db.refresh(updated_pos)

        self.assertIsNotNone(updated_pos)
        self.assertEqual(updated_pos.status, "CLOSED")
        self.assertEqual(updated_pos.closing_price, 150.0)
        self.assertAlmostEqual(updated_pos.realized_pnl, 50.0)
        self.assertAlmostEqual(updated_pos.unrealized_pnl, 0.0)

    def test_reopen_position_clears_realized_pnl(self):
        pos_data = [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}]
        pos = crud.create_position(self.db, "Test Reopen", pos_data)
        self.db.commit()

        closed_pos = crud.update_position_status(self.db, pos.id, "CLOSED", closing_price=120.0)
        self.db.commit()
        self.assertAlmostEqual(closed_pos.realized_pnl, 20.0)
        self.assertEqual(closed_pos.closing_price, 120.0)

        reopened_pos = crud.update_position_status(self.db, pos.id, "OPEN")
        self.db.commit()
        self.db.refresh(reopened_pos)

        self.assertIsNotNone(reopened_pos)
        self.assertEqual(reopened_pos.status, "OPEN")
        self.assertAlmostEqual(reopened_pos.realized_pnl, 0.0)
        self.assertIsNone(reopened_pos.closing_price)

    def test_add_legs_to_position(self):
        pos = crud.create_position(self.db, "Test Add Legs", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit()
        self.db.refresh(pos)
        if pos.legs:
            for leg in pos.legs: self.db.refresh(leg)
        original_leg_count = len(pos.legs)
        original_cb = pos.cost_basis

        new_legs_data: List[Dict[str, Any]] = [
            {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 1), "quantity": -1, "entry_price_per_unit": 0.50}
        ]
        updated_pos = crud.add_legs_to_position(self.db, pos.id, new_legs_data)
        self.db.commit()
        self.db.refresh(updated_pos)
        if updated_pos.legs:
            for leg in updated_pos.legs: self.db.refresh(leg)

        self.assertIsNotNone(updated_pos)
        self.assertEqual(len(updated_pos.legs), original_leg_count + 1)
        self.assertAlmostEqual(updated_pos.cost_basis, original_cb - 50.0)

    def test_update_leg_current_price(self):
        pos = crud.create_position(self.db, "Test Leg Price", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit()
        self.db.refresh(pos)
        if not pos.legs: self.fail("Position created without legs")
        leg_id = pos.legs[0].id

        updated_leg = crud.update_leg_current_price(self.db, leg_id, 1.50)
        self.db.commit()
        self.db.refresh(updated_leg)
        self.assertIsNotNone(updated_leg)
        self.assertEqual(updated_leg.current_price_per_unit, 1.50)

    def test_update_leg_closing_price(self):
        pos = crud.create_position(self.db, "Test Leg Close Price", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit()
        self.db.refresh(pos)
        if not pos.legs: self.fail("Position created without legs")
        leg_id = pos.legs[0].id

        updated_leg = crud.update_leg_closing_price(self.db, leg_id, 1.80)
        self.db.commit()
        self.db.refresh(updated_leg)
        self.assertIsNotNone(updated_leg)
        self.assertEqual(updated_leg.closing_price_per_unit, 1.80)

    def test_add_note_to_position(self):
        pos = crud.create_position(self.db, "Test Notes", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit()
        self.assertIsNone(pos.notes)

        crud.add_note_to_position(self.db, pos.id, "First note.")
        self.db.commit()
        self.db.refresh(pos)
        self.assertIn("First note.", pos.notes)

        crud.add_note_to_position(self.db, pos.id, "Second note.", append=True)
        self.db.commit()
        self.db.refresh(pos)
        self.assertIn("First note.", pos.notes)
        self.assertIn("Second note.", pos.notes)
        self.assertIn("---\n", pos.notes)

        crud.add_note_to_position(self.db, pos.id, "Replaced note.", append=False)
        self.db.commit()
        self.db.refresh(pos)
        self.assertEqual(pos.notes, "Replaced note.")

    def test_delete_position(self):
        pos = crud.create_position(self.db, "Test Delete", [{"option_type":"CALL", "strike_price":100, "expiry_date":datetime.date(2025,1,1), "quantity":1, "entry_price_per_unit":1.0}])
        self.db.commit()
        self.db.refresh(pos)
        if not pos.legs: self.fail("Position created without legs")
        position_id = pos.id
        leg_id = pos.legs[0].id

        self.assertIsNotNone(crud.get_position_by_id(self.db, position_id))
        self.assertIsNotNone(self.db.query(models.OptionLeg).get(leg_id))

        delete_success = crud.delete_position(self.db, position_id)
        self.db.commit()
        self.assertTrue(delete_success)
        self.assertIsNone(crud.get_position_by_id(self.db, position_id))
        self.assertIsNone(self.db.query(models.OptionLeg).get(leg_id))

        delete_fail = crud.delete_position(self.db, 99999)
        self.assertFalse(delete_fail)

    def test_update_legs_current_prices_and_unrealized_pnl(self):
        legs_data: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit": 2.00},
            {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025,1,17), "quantity": -1, "entry_price_per_unit": 1.00}
        ]
        pos = crud.create_position(self.db, "Test UPL Update", legs_data)
        self.db.commit()
        self.db.refresh(pos)
        if not pos.legs or len(pos.legs) < 2 : self.fail("Position legs not created/refreshed properly")

        leg1_id = None
        leg2_id = None
        for leg in pos.legs:
            if leg.strike_price == 100.0: leg1_id = leg.id
            if leg.strike_price == 105.0: leg2_id = leg.id

        self.assertIsNotNone(leg1_id, "Leg 1 ID not found")
        self.assertIsNotNone(leg2_id, "Leg 2 ID not found")
        self.assertAlmostEqual(pos.unrealized_pnl, 0.0)

        leg_current_prices = { leg1_id: 2.50, leg2_id: 0.80 }
        updated_pos = crud.update_legs_current_prices_and_unrealized_pnl(self.db, pos.id, leg_current_prices)
        self.db.commit()
        self.db.refresh(updated_pos)
        if updated_pos.legs:
            for leg in updated_pos.legs: self.db.refresh(leg)

        self.assertIsNotNone(updated_pos)
        self.assertAlmostEqual(updated_pos.unrealized_pnl, 70.0)

        for leg in updated_pos.legs:
            if leg.id == leg1_id:
                self.assertAlmostEqual(leg.current_price_per_unit, 2.50)
            if leg.id == leg2_id:
                self.assertAlmostEqual(leg.current_price_per_unit, 0.80)

    def test_update_unrealized_pnl_for_closed_position(self):
        legs_data: List[Dict[str, Any]] = [
            {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1, "entry_price_per_unit": 2.00},
        ]
        pos = crud.create_position(self.db, "Test UPL Closed", legs_data)
        self.db.commit()
        self.db.refresh(pos)
        if not pos.legs: self.fail("Position created without legs for UPL closed test")

        crud.update_position_status(self.db, pos.id, "CLOSED", closing_price=250.0)
        self.db.commit()

        leg_id = pos.legs[0].id
        leg_current_prices = {leg_id: 3.00}

        updated_pos = crud.update_legs_current_prices_and_unrealized_pnl(self.db, pos.id, leg_current_prices)
        self.db.commit()
        self.db.refresh(updated_pos)

        self.assertIsNotNone(updated_pos)
        self.assertEqual(updated_pos.status, "CLOSED")
        self.assertAlmostEqual(updated_pos.unrealized_pnl, 0.0)
        self.assertAlmostEqual(updated_pos.realized_pnl, 50.0)


if __name__ == '__main__':
    unittest.main()
