import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app # Main FastAPI application
from src.database import models, setup as db_setup, crud
from src.api_schemas import PositionCreate, OptionLegCreate, LegPricesUpdate, PositionBase
import datetime
from unittest.mock import patch # For mocking AlphaVantageAPI in delta calculation

class TestPositionsAPI(unittest.TestCase):

    engine = None
    TestSessionLocal = None # This will be the sessionmaker for the test engine
    client = None
    original_db_engine = None # To store the app's original engine

    @classmethod
    def setUpClass(cls):
        from sqlalchemy.pool import StaticPool

        cls.original_db_engine = db_setup.engine

        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )

        db_setup.engine = cls.engine
        models.Base.metadata.create_all(bind=cls.engine)

        cls.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        def override_get_db():
            db = cls.TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[db_setup.get_db_session] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        models.Base.metadata.drop_all(bind=cls.engine)
        app.dependency_overrides.clear()
        db_setup.engine = cls.original_db_engine


    def setUp(self):
        db = self.TestSessionLocal()
        try:
            db.query(models.OptionLeg).delete()
            db.query(models.Position).delete()
            db.query(models.PortfolioSetting).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def _create_bull_call_spread_payload(self, underlying_symbol="TESTXYZ", spread_type_override=None) -> dict:
        return {
            "underlying_symbol": underlying_symbol,
            "spread_type": spread_type_override if spread_type_override else "Bull Call Spread", # Use specific type
            "status": "OPEN",
            "legs_data": [
                {"option_type": "CALL", "strike_price": 100.0, "expiry_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(), "quantity": 1, "entry_price_per_unit": 2.00},
                {"option_type": "CALL", "strike_price": 105.0, "expiry_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(), "quantity": -1, "entry_price_per_unit": 1.00}
            ]
        }

    def test_create_position_success(self):
        payload = self._create_bull_call_spread_payload()
        response = self.client.post("/api/v1/positions/", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["spread_type"], payload["spread_type"])
        self.assertEqual(len(data["legs"]), 2)
        self.assertAlmostEqual(data["cost_basis"], 100.0) # (2.00 - 1.00) * 100
        self.assertIsNotNone(data["days_to_expiration"]) # Should be around 29 or 30
        self.assertTrue(28 <= data["days_to_expiration"] <= 30)


    def test_create_position_invalid_spread(self):
        # Ensure we use a spread_type that has a validator, like "Bull Call Spread"
        payload = self._create_bull_call_spread_payload(underlying_symbol="INVALIDTEST", spread_type_override="Bull Call Spread")
        payload["legs_data"].pop() # Make it invalid (only 1 leg for BCS)
        response = self.client.post("/api/v1/positions/", json=payload)
        self.assertEqual(response.status_code, 400) # Validation error from spread_validator
        self.assertIn("must have exactly two legs", response.json()["detail"])

    def test_list_positions(self):
        # Create a couple of positions
        self.client.post("/api/v1/positions/", json=self._create_bull_call_spread_payload(underlying_symbol="POS1"))
        # To ensure different spread_type for listing, override it or use a different helper if available
        self.client.post("/api/v1/positions/", json=self._create_bull_call_spread_payload(underlying_symbol="POS2", spread_type_override="Custom Spread For List"))


        response = self.client.get("/api/v1/positions/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

        # Test filtering by status (both are OPEN by default)
        response_open = self.client.get("/api/v1/positions/?status=OPEN")
        self.assertEqual(response_open.status_code, 200)
        self.assertEqual(len(response_open.json()), 2)

        response_closed = self.client.get("/api/v1/positions/?status=CLOSED")
        self.assertEqual(response_closed.status_code, 200)
        self.assertEqual(len(response_closed.json()), 0)


    @patch('src.core.derivatives_calculator.AlphaVantageAPI.get_stock_quote') # Mock the external API call
    def test_get_specific_position_with_delta(self, mock_get_quote):
        # Mock the return value of AlphaVantageAPI.get_stock_quote
        # The symbol will now be taken from position.underlying_symbol
        test_symbol = "TESTDELTA"
        mock_get_quote.return_value = {"05. price": "102.00"} # Underlying price for test_symbol

        payload = self._create_bull_call_spread_payload(underlying_symbol=test_symbol)
        # payload["spread_type"] will be f"{test_symbol} Bull Call Spread"

        create_response = self.client.post("/api/v1/positions/", json=payload)
        self.assertEqual(create_response.status_code, 201, create_response.json())
        position_id = create_response.json()["id"]

        # Get position with delta calculation
        # Pass vol and rfr as query params, or they'll use defaults from derivatives_calculator
        response = self.client.get(f"/api/v1/positions/{position_id}?volatility=0.20&risk_free_rate=0.01")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], position_id)
        self.assertIsNotNone(data["calculated_position_delta"])
        # Actual delta value depends on Black-Scholes with S=102, K1=100, K2=105, T~30/365, r=0.01, vol=0.20
        # Long 100C Delta: ~0.651
        # Short 105C Delta: ~0.322
        # Position Delta = (0.651 * 1) + (0.322 * -1) = 0.329
        expected_delta = 0.329
        self.assertIsNotNone(data["calculated_position_delta"], "Calculated delta should not be None")
        self.assertTrue(abs(data["calculated_position_delta"] - expected_delta) < 0.01,
                        f"Delta {data['calculated_position_delta']:.4f} not close to expected {expected_delta:.4f}")

        # Ensure the mock was called with the correct symbol from the position
        mock_get_quote.assert_called_once_with(test_symbol)


    def test_update_position_status_to_closed(self):
        create_response = self.client.post("/api/v1/positions/", json=self._create_bull_call_spread_payload())
        position_id = create_response.json()["id"]

        # Close the position with a closing price (net credit for the position)
        closing_price_val = 120.0 # e.g., closed for $1.20 per share credit
        response = self.client.put(f"/api/v1/positions/{position_id}/status?status=CLOSED&closing_price={closing_price_val}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "CLOSED")
        self.assertEqual(data["closing_price"], closing_price_val)
        # Initial CB = 100. RPL = 120 - 100 = 20.
        self.assertAlmostEqual(data["realized_pnl"], 20.0)
        self.assertAlmostEqual(data["unrealized_pnl"], 0.0)


    def test_update_position_notes(self):
        create_response = self.client.post("/api/v1/positions/", json=self._create_bull_call_spread_payload())
        position_id = create_response.json()["id"]

        notes_payload = {"notes": "This is a new note."} # This matches NotesUpdate schema
        response = self.client.post(f"/api/v1/positions/{position_id}/notes?append=false", json=notes_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["notes"], "This is a new note.")

        append_notes_payload = {"notes": "Appended note."} # This also matches NotesUpdate
        response_append = self.client.post(f"/api/v1/positions/{position_id}/notes?append=true", json=append_notes_payload)
        self.assertEqual(response_append.status_code, 200)
        data_append = response_append.json()
        self.assertIn("This is a new note.", data_append["notes"])
        self.assertIn("Appended note.", data_append["notes"])


    def test_update_leg_prices_and_upl(self):
        create_response = self.client.post("/api/v1/positions/", json=self._create_bull_call_spread_payload())
        position_data = create_response.json()
        position_id = position_data["id"]

        leg1_id = position_data["legs"][0]["id"]
        leg2_id = position_data["legs"][1]["id"]

        leg_prices_payload = {
            "leg_current_prices": {
                str(leg1_id): 2.50, # Long 100C: Entry 2.00, Current 2.50 -> UPL_leg1 = 50
                str(leg2_id): 0.80  # Short 105C: Entry 1.00, Current 0.80 -> UPL_leg2 = 20
            }
        } # Total UPL = 50 + 20 = 70

        response = self.client.post(f"/api/v1/positions/{position_id}/leg_prices", json=leg_prices_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertAlmostEqual(data["unrealized_pnl"], 70.0)
        # Check if leg current prices are updated (optional, as response shows position level)
        updated_leg1_price = next(leg["current_price_per_unit"] for leg in data["legs"] if leg["id"] == leg1_id)
        updated_leg2_price = next(leg["current_price_per_unit"] for leg in data["legs"] if leg["id"] == leg2_id)
        self.assertAlmostEqual(updated_leg1_price, 2.50)
        self.assertAlmostEqual(updated_leg2_price, 0.80)

if __name__ == '__main__':
    unittest.main()
