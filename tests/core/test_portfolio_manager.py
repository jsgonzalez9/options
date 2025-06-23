import unittest
from unittest.mock import MagicMock, patch
import datetime
from sqlalchemy.orm import Session

from src.core import portfolio_manager, pnl_calculator # Ensure pnl_calculator is also available for context
from src.database import models
from src.config import OPTION_MULTIPLIER

# Mock for OptionLeg and Position to be used in these tests
class MockOptionLeg:
    def __init__(self, id, current_price_per_unit, quantity, option_type="CALL"):
        self.id = id
        self.current_price_per_unit = current_price_per_unit
        self.quantity = quantity
        self.option_type = option_type # To distinguish stock "legs"

class MockPosition:
    def __init__(self, id, is_stock_position, stock_quantity, legs, status="OPEN",
                 realized_pnl=None, unrealized_pnl=None, closing_price=None, cost_basis=0):
        self.id = id
        self.is_stock_position = is_stock_position
        self.stock_quantity = stock_quantity
        self.legs = legs
        self.status = status
        self.realized_pnl = realized_pnl
        self.unrealized_pnl = unrealized_pnl
        self.closing_price = closing_price # For realized PNL calc if method 1
        self.cost_basis = cost_basis # For realized PNL calc if method 1


class TestPortfolioManager(unittest.TestCase):

    def setUp(self):
        self.mock_db_session = MagicMock(spec=Session)
        portfolio_manager.OPTION_MULTIPLIER = 100 # Ensure consistent multiplier for tests

    def test_get_cash_balance_exists(self):
        mock_setting = models.PortfolioSetting(key=portfolio_manager.CASH_BALANCE_KEY, value=1000.0)
        self.mock_db_session.query(models.PortfolioSetting).filter().first.return_value = mock_setting

        balance = portfolio_manager.get_cash_balance(self.mock_db_session)
        self.assertEqual(balance, 1000.0)

    def test_get_cash_balance_not_exists(self):
        self.mock_db_session.query(models.PortfolioSetting).filter().first.return_value = None
        balance = portfolio_manager.get_cash_balance(self.mock_db_session)
        self.assertEqual(balance, 0.0)

    def test_update_cash_balance_deposit_new(self):
        self.mock_db_session.query(models.PortfolioSetting).filter().first.return_value = None # No existing setting

        new_balance = portfolio_manager.update_cash_balance(self.mock_db_session, 500.0, True)
        self.assertEqual(new_balance, 500.0)
        self.mock_db_session.add.assert_called_once()
        added_obj = self.mock_db_session.add.call_args[0][0]
        self.assertEqual(added_obj.key, portfolio_manager.CASH_BALANCE_KEY)
        self.assertEqual(added_obj.value, 500.0)

    def test_update_cash_balance_deposit_existing(self):
        mock_setting = models.PortfolioSetting(key=portfolio_manager.CASH_BALANCE_KEY, value=1000.0)
        self.mock_db_session.query(models.PortfolioSetting).filter().first.return_value = mock_setting

        new_balance = portfolio_manager.update_cash_balance(self.mock_db_session, 500.0, True)
        self.assertEqual(new_balance, 1500.0)
        self.assertEqual(mock_setting.value, 1500.0) # Check original object was modified

    def test_update_cash_balance_withdraw_sufficient_funds(self):
        mock_setting = models.PortfolioSetting(key=portfolio_manager.CASH_BALANCE_KEY, value=1000.0)
        self.mock_db_session.query(models.PortfolioSetting).filter().first.return_value = mock_setting

        new_balance = portfolio_manager.update_cash_balance(self.mock_db_session, 300.0, False)
        self.assertEqual(new_balance, 700.0)
        self.assertEqual(mock_setting.value, 700.0)

    def test_update_cash_balance_withdraw_insufficient_funds(self):
        mock_setting = models.PortfolioSetting(key=portfolio_manager.CASH_BALANCE_KEY, value=100.0)
        self.mock_db_session.query(models.PortfolioSetting).filter().first.return_value = mock_setting

        with self.assertRaisesRegex(ValueError, "exceeds current balance"):
            portfolio_manager.update_cash_balance(self.mock_db_session, 200.0, False)

    def test_update_cash_balance_negative_amount_change(self):
        with self.assertRaisesRegex(ValueError, "Amount for cash balance change must be positive"):
            portfolio_manager.update_cash_balance(self.mock_db_session, -100.0, True)


    @patch('src.core.portfolio_manager.crud.get_all_positions')
    def test_calculate_total_open_positions_market_value(self, mock_get_all_positions):
        # Stock position: 10 shares @ $150 current price = $1500 market value
        stock_leg = MockOptionLeg(id=1, current_price_per_unit=150.0, quantity=10, option_type="STOCK")
        stock_pos = MockPosition(id=1, is_stock_position=True, stock_quantity=10, legs=[stock_leg])

        # Option position:
        # Leg 1: Long 2 CALLS, current price $2.50/share -> 2.50 * 2 * 100 = $500
        # Leg 2: Short 2 CALLS, current price $1.00/share -> 1.00 * -2 * 100 = -$200
        # Option position market value = 500 - 200 = $300
        opt_leg1 = MockOptionLeg(id=2, current_price_per_unit=2.50, quantity=2, option_type="CALL")
        opt_leg2 = MockOptionLeg(id=3, current_price_per_unit=1.00, quantity=-2, option_type="CALL")
        option_pos = MockPosition(id=2, is_stock_position=False, stock_quantity=None, legs=[opt_leg1, opt_leg2])

        # Position with leg missing current price
        opt_leg_no_price = MockOptionLeg(id=4, current_price_per_unit=None, quantity=1, option_type="CALL")
        pos_no_price = MockPosition(id=3, is_stock_position=False, stock_quantity=None, legs=[opt_leg_no_price])

        mock_get_all_positions.return_value = [stock_pos, option_pos, pos_no_price]

        total_mv = portfolio_manager.calculate_total_open_positions_market_value(self.mock_db_session)
        self.assertEqual(total_mv, 1500.0 + 300.0) # 1800.0

    def test_get_overall_portfolio_pnl(self):
        # Mocking query results for realized and unrealized P&L
        mock_closed_pnl_query = MagicMock()
        mock_closed_pnl_query.all.return_value = [(100.0,), (-50.0,)] # Realized P&Ls: 100, -50

        mock_open_pnl_query = MagicMock()
        mock_open_pnl_query.all.return_value = [(75.0,), (25.0,)] # Unrealized P&Ls: 75, 25

        # Setup the side_effect for db.query(...).filter(...).all()
        # This needs to return an object that has an .all() method.
        # The .all() method should return the list of tuples.

        # Mock for the query on realized_pnl
        mock_query_realized = MagicMock()
        mock_query_realized.filter.return_value = mock_query_realized # filter returns self
        mock_query_realized.all.return_value = [(100.0,), (-50.0,)]

        # Mock for the query on unrealized_pnl
        mock_query_unrealized = MagicMock()
        mock_query_unrealized.filter.return_value = mock_query_unrealized # filter returns self
        mock_query_unrealized.all.return_value = [(75.0,), (25.0,)]

        def query_side_effect(query_arg):
            if query_arg == models.Position.realized_pnl:
                return mock_query_realized
            elif query_arg == models.Position.unrealized_pnl:
                return mock_query_unrealized
            return MagicMock() # Should not be called for other types in this test

        self.mock_db_session.query.side_effect = query_side_effect

        overall_pnl = portfolio_manager.get_overall_portfolio_pnl(self.mock_db_session)
        # Expected: (100 - 50) + (75 + 25) = 50 + 100 = 150
        self.assertEqual(overall_pnl, 150.0)

        # Check that query was called twice (once for realized, once for unrealized)
        self.assertEqual(self.mock_db_session.query.call_count, 2)
        self.mock_db_session.query.assert_any_call(models.Position.realized_pnl)
        self.mock_db_session.query.assert_any_call(models.Position.unrealized_pnl)
        mock_query_realized.filter.assert_called_once() # Add more specific checks for filter if needed
        mock_query_unrealized.filter.assert_called_once()


    @patch('src.core.portfolio_manager.get_cash_balance', return_value=10000.0)
    @patch('src.core.portfolio_manager.calculate_total_open_positions_market_value', return_value=5000.0)
    @patch('src.core.portfolio_manager.get_overall_portfolio_pnl', return_value=1500.0)
    def test_get_portfolio_summary_data(self, mock_overall_pnl, mock_open_mv, mock_cash):
        summary = portfolio_manager.get_portfolio_summary_data(self.mock_db_session)

        self.assertEqual(summary["cash_balance"], 10000.0)
        self.assertEqual(summary["total_open_positions_market_value"], 5000.0)
        self.assertEqual(summary["total_portfolio_value"], 15000.0) # 10000 + 5000
        self.assertEqual(summary["overall_portfolio_pnl"], 1500.0)

        mock_cash.assert_called_once_with(self.mock_db_session)
        mock_open_mv.assert_called_once_with(self.mock_db_session)
        mock_overall_pnl.assert_called_once_with(self.mock_db_session)

if __name__ == '__main__':
    unittest.main()
