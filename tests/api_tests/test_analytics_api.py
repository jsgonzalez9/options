import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app # Main FastAPI application
from src.database import models, setup as db_setup, crud # Need crud to create test data
import datetime
from unittest.mock import patch

class TestAnalyticsAPI(unittest.TestCase):

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
        # Clean data from tables before each test method
        db = self.TestSessionLocal()
        try:
            # Position 1: Win
            legs1 = [{"option_type": "CALL", "strike_price": 100, "expiry_date": datetime.date(2023,1,1), "quantity": 1, "entry_price_per_unit": 1.0}] # CB = 100
            pos1 = crud.create_position(db, "Test Win", legs1)
            crud.update_position_status(db, pos1.id, "CLOSED", closing_price=200.0) # RPL = 200 - 100 = 100

            # Position 2: Loss
            legs2 = [{"option_type": "PUT", "strike_price": 50, "expiry_date": datetime.date(2023,1,1), "quantity": 1, "entry_price_per_unit": 2.0}] # CB = 200
            pos2 = crud.create_position(db, "Test Loss", legs2)
            crud.update_position_status(db, pos2.id, "CLOSED", closing_price=150.0) # RPL = 150 - 200 = -50

            # Position 3: Another Win
            legs3 = [{"option_type": "CALL", "strike_price": 200, "expiry_date": datetime.date(2023,2,1), "quantity": -1, "entry_price_per_unit": 3.0}] # CB = -300 (credit)
            pos3 = crud.create_position(db, "Test Win 2", legs3)
            crud.update_position_status(db, pos3.id, "CLOSED", closing_price=-100.0) # RPL = -100 - (-300) = 200

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


    def test_get_analytics_summary(self):
        response = self.client.get("/api/v1/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Based on setUp data: P&Ls are [100, -50, 200]
        # Total trades: 3
        # Wins: 2 (100, 200)
        # Losses: 1 (-50)
        # Win Rate: (2/3)*100 = 66.66...%
        # Average P&L: (100 - 50 + 200) / 3 = 250 / 3 = 83.33...
        # Gross Profit: 100 + 200 = 300
        # Gross Loss: -50
        # Profit Factor: 300 / |-50| = 6.0

        self.assertEqual(data["total_closed_trades"], 3)
        self.assertAlmostEqual(data["win_rate_percent"], (2/3)*100)
        self.assertAlmostEqual(data["average_pnl_per_trade"], 250/3)
        self.assertAlmostEqual(data["profit_factor"], 6.0)
        self.assertAlmostEqual(data["total_gross_profit"], 300.0)
        self.assertAlmostEqual(data["total_gross_loss"], -50.0)
        self.assertEqual(data["number_of_winning_trades"], 2)
        self.assertEqual(data["number_of_losing_trades"], 1)
        self.assertAlmostEqual(data["average_profit_per_winning_trade"], 150.0) # (100+200)/2
        self.assertAlmostEqual(data["average_loss_per_losing_trade"], -50.0) # -50/1

    def test_get_analytics_summary_no_closed_trades(self):
        # Clean tables again to ensure no data from setUp
        models.Base.metadata.drop_all(self.engine)
        models.Base.metadata.create_all(self.engine)

        response = self.client.get("/api/v1/analytics/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["total_closed_trades"], 0)
        self.assertEqual(data["win_rate_percent"], 0.0)
        self.assertEqual(data["average_pnl_per_trade"], 0.0)
        self.assertEqual(data["profit_factor"], 0.0)

if __name__ == '__main__':
    unittest.main()
