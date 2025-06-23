import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.main import app # Main FastAPI application
from src.database import models, setup as db_setup
from src.core import portfolio_manager # To help setup initial cash
import datetime # Import datetime

class TestPortfolioAPI(unittest.TestCase):

    engine = None
    TestSessionLocal = None
    client = None
    engine = None
    TestSessionLocal = None # This will be the sessionmaker for the test engine
    client = None
    original_db_engine = None # To store the app's original engine

    @classmethod
    def setUpClass(cls):
        from sqlalchemy.pool import StaticPool

        # Store the original engine from the app's setup
        cls.original_db_engine = db_setup.engine

        # Create a new engine for testing (in-memory SQLite)
        cls.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False}, # Essential for SQLite with multiple threads
            poolclass=StaticPool # Recommended for SQLite with TestClient
        )

        # Override the app's engine with the test engine
        db_setup.engine = cls.engine

        # Create all tables in the test database
        models.Base.metadata.create_all(bind=cls.engine)

        # Create a sessionmaker for the test engine
        cls.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        # Override the get_db dependency for the FastAPI app
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
        db_setup.engine = cls.original_db_engine # Restore original engine
        # Optionally recreate tables on original engine if it was file-based and expected to persist
        # models.Base.metadata.create_all(bind=db_setup.engine)


    def setUp(self):
        # Clean data from tables before each test method
        db = self.TestSessionLocal()
        try:
            # Order matters for foreign key constraints
            db.query(models.OptionLeg).delete() # If positions test creates legs
            db.query(models.Position).delete()   # If positions test creates positions
            db.query(models.PortfolioSetting).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    def test_get_initial_cash_balance(self):
        response = self.client.get("/api/v1/portfolio/cash")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["key"], portfolio_manager.CASH_BALANCE_KEY)
        self.assertEqual(data["value"], 0.0) # Expect 0.0 if not set

    def test_update_cash_balance_deposit(self):
        deposit_amount = 5000.0
        response = self.client.post(
            "/api/v1/portfolio/cash",
            json={"amount": deposit_amount, "is_deposit": True}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["key"], portfolio_manager.CASH_BALANCE_KEY)
        self.assertEqual(data["value"], deposit_amount)

        # Verify by getting
        getResponse = self.client.get("/api/v1/portfolio/cash")
        self.assertEqual(getResponse.status_code, 200)
        self.assertEqual(getResponse.json()["value"], deposit_amount)

    def test_update_cash_balance_withdrawal(self):
        # First, deposit some cash
        initial_deposit = 1000.0
        self.client.post("/api/v1/portfolio/cash", json={"amount": initial_deposit, "is_deposit": True})

        withdrawal_amount = 300.0
        response = self.client.post(
            "/api/v1/portfolio/cash",
            json={"amount": withdrawal_amount, "is_deposit": False}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["value"], initial_deposit - withdrawal_amount)

    def test_update_cash_balance_withdrawal_overdraw(self):
        initial_deposit = 100.0
        self.client.post("/api/v1/portfolio/cash", json={"amount": initial_deposit, "is_deposit": True})

        withdrawal_amount = 200.0 # More than balance
        response = self.client.post(
            "/api/v1/portfolio/cash",
            json={"amount": withdrawal_amount, "is_deposit": False}
        )
        self.assertEqual(response.status_code, 400) # Bad request due to overdraw
        self.assertIn("exceeds current balance", response.json()["detail"])

    def test_update_cash_balance_negative_amount(self):
        response = self.client.post(
            "/api/v1/portfolio/cash",
            json={"amount": -100.0, "is_deposit": True} # Negative amount
        )
        # This should be caught by Pydantic validation if amount is restricted to positive,
        # or by the ValueError in portfolio_manager.update_cash_balance.
        # If Pydantic schema `CashUpdate` enforces `amount: float = Field(..., gt=0)`,
        # FastAPI would return 422 Unprocessable Entity. This is what happens now.
        self.assertEqual(response.status_code, 422)
        # The detail message from Pydantic will be more structured.
        # Example: [{'type': 'greater_than', 'loc': ('body', 'amount'), 'msg': 'Input should be greater than 0', ...}]
        # For simplicity, we'll just check the status code.
        # self.assertIn("Input should be greater than 0", response.text) # Check Pydantic's message if needed


    def test_get_portfolio_summary_initial(self):
        response = self.client.get("/api/v1/portfolio/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["cash_balance"], 0.0)
        self.assertEqual(data["total_open_positions_market_value"], 0.0)
        self.assertEqual(data["total_portfolio_value"], 0.0)
        self.assertEqual(data["overall_portfolio_pnl"], 0.0)

    def test_get_portfolio_summary_with_cash_and_positions(self):
        # This test is more complex as it requires setting up positions
        # and their current market values. For now, we test the cash part.
        # A more complete test would involve creating positions via API first.

        cash_deposit = 10000.0
        self.client.post("/api/v1/portfolio/cash", json={"amount": cash_deposit, "is_deposit": True})

        response = self.client.get("/api/v1/portfolio/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["cash_balance"], cash_deposit)
        # open_positions_market_value and overall_portfolio_pnl would be 0 without positions
        self.assertEqual(data["total_open_positions_market_value"], 0.0)
        self.assertEqual(data["total_portfolio_value"], cash_deposit)
        self.assertEqual(data["overall_portfolio_pnl"], 0.0)

        # TODO: Extend this test later by:
        # 1. Creating a position via the /positions API.
        # 2. Updating its leg current prices via the /positions/{id}/leg_prices API.
        # 3. Then calling /portfolio/summary and verifying all fields.

        # Create a stock position
        stock_payload = {
            "underlying_symbol": "STK1", "spread_type": "Stock", "is_stock_position": True,
            "stock_quantity": 100, "status": "OPEN",
            "legs_data": [{"option_type": "STOCK", "strike_price": 0, "expiry_date": datetime.date.today().isoformat(), "quantity": 100, "entry_price_per_unit": 50.0}]
        }
        stock_pos_resp = self.client.post("/api/v1/positions/", json=stock_payload)
        self.assertEqual(stock_pos_resp.status_code, 201)
        stock_pos_id = stock_pos_resp.json()["id"]
        stock_pos_leg_id = stock_pos_resp.json()["legs"][0]["id"]

        # Update its current price
        self.client.post(f"/api/v1/positions/{stock_pos_id}/leg_prices", json={"leg_current_prices": {str(stock_pos_leg_id): 55.0}})
        # Stock Market Value = 55.0 * 100 = 5500

        # Create an option position
        option_payload = {
            "underlying_symbol": "OPT1", "spread_type": "Bull Call Spread", "is_stock_position": False,
            "status": "OPEN",
            "legs_data": [
                {"option_type": "CALL", "strike_price": 100.0, "expiry_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(), "quantity": 1, "entry_price_per_unit": 2.00},
                {"option_type": "CALL", "strike_price": 105.0, "expiry_date": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(), "quantity": -1, "entry_price_per_unit": 1.00}
            ]
        }
        option_pos_resp = self.client.post("/api/v1/positions/", json=option_payload)
        self.assertEqual(option_pos_resp.status_code, 201)
        option_pos_id = option_pos_resp.json()["id"]
        leg1_id = option_pos_resp.json()["legs"][0]["id"]
        leg2_id = option_pos_resp.json()["legs"][1]["id"]

        # Update its leg prices
        self.client.post(f"/api/v1/positions/{option_pos_id}/leg_prices", json={"leg_current_prices": {str(leg1_id): 2.20, str(leg2_id): 1.10}})
        # Option Market Value = (2.20 * 1 * 100) + (1.10 * -1 * 100) = 220 - 110 = 110

        # Total Open Positions Market Value = 5500 (stock) + 110 (option) = 5610

        # Get summary again
        response_final = self.client.get("/api/v1/portfolio/summary")
        self.assertEqual(response_final.status_code, 200)
        data_final = response_final.json()

        self.assertEqual(data_final["cash_balance"], cash_deposit)
        self.assertAlmostEqual(data_final["total_open_positions_market_value"], 5610.0)
        self.assertAlmostEqual(data_final["total_portfolio_value"], cash_deposit + 5610.0)

        # P&L calculation:
        # Stock: Entry 50, Current 55, Qty 100. UPL = (55-50)*100 = 500
        # Option: Leg1 Entry 2.0, Current 2.2. UPL1 = (2.2-2.0)*1*100 = 20
        #         Leg2 Entry 1.0, Current 1.1. UPL2 = (1.1-1.0)*-1*100 = -10 (loss for short call as price rose)
        # Option UPL = 20 - 10 = 10
        # Total UPL = 500 + 10 = 510. Since no closed positions, Overall PNL = Total UPL.
        self.assertAlmostEqual(data_final["overall_portfolio_pnl"], 510.0)


if __name__ == '__main__':
    unittest.main()
