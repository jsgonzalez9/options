import unittest
from unittest.mock import MagicMock, patch
from src.core import analytics_engine
from sqlalchemy.orm import Session # For type hinting if using a real session mock

class TestAnalyticsEngine(unittest.TestCase):

    def test_calculate_win_rate(self):
        self.assertAlmostEqual(analytics_engine.calculate_win_rate([10, -5, 20]), (2/3)*100)
        self.assertAlmostEqual(analytics_engine.calculate_win_rate([-10, -5, -20]), 0.0)
        self.assertAlmostEqual(analytics_engine.calculate_win_rate([10, 5, 20]), 100.0)
        self.assertAlmostEqual(analytics_engine.calculate_win_rate([]), 0.0)
        self.assertAlmostEqual(analytics_engine.calculate_win_rate([0, 0, 0]), 0.0) # Trades with P&L=0 are not counted as wins
        self.assertAlmostEqual(analytics_engine.calculate_win_rate([1, 0, -1]), (1/3)*100)


    def test_calculate_average_pnl(self):
        self.assertAlmostEqual(analytics_engine.calculate_average_pnl([10, -5, 20]), (10-5+20)/3) # 25/3 = 8.333...
        self.assertAlmostEqual(analytics_engine.calculate_average_pnl([-10, -5, -20]), (-10-5-20)/3) # -35/3 = -11.666...
        self.assertAlmostEqual(analytics_engine.calculate_average_pnl([]), 0.0)
        self.assertAlmostEqual(analytics_engine.calculate_average_pnl([10, 20, 30]), 20.0)

    def test_calculate_profit_factor(self):
        # Gross Profit = 10+20 = 30. Gross Loss = -5. Profit Factor = 30 / 5 = 6
        self.assertAlmostEqual(analytics_engine.calculate_profit_factor([10, -5, 20]), 6.0)

        # All losses: Gross Profit = 0. Profit Factor = 0 / Gross Loss = 0
        self.assertAlmostEqual(analytics_engine.calculate_profit_factor([-10, -5, -20]), 0.0)

        # All profits: Gross Loss = 0. Profit Factor = inf
        self.assertEqual(analytics_engine.calculate_profit_factor([10, 5, 20]), float('inf'))

        # No trades
        self.assertAlmostEqual(analytics_engine.calculate_profit_factor([]), 0.0)

        # Zero P&L trades
        # Gross Profit = 0, Gross Loss = 0. Profit Factor = 0.0
        self.assertAlmostEqual(analytics_engine.calculate_profit_factor([0, 0, 0]), 0.0)

        # Mixed with zero
        # Gross Profit = 10, Gross Loss = -5. Profit Factor = 10/5 = 2
        self.assertAlmostEqual(analytics_engine.calculate_profit_factor([10, 0, -5]), 2.0)

    @patch('src.core.analytics_engine.get_realized_pnls_for_analytics')
    def test_get_performance_summary(self, mock_get_pnls):
        sample_pnls = [100, -50, 200, -80, 120, 0] # 3 wins, 2 losses, 1 break-even
        mock_get_pnls.return_value = sample_pnls

        mock_db_session = MagicMock(spec=Session) # Mock the DB session
        summary = analytics_engine.get_performance_summary(mock_db_session)

        mock_get_pnls.assert_called_once_with(mock_db_session)

        self.assertEqual(summary["total_closed_trades"], 6)
        self.assertEqual(summary["realized_pnls"], sample_pnls)

        # Win rate: 3 wins / 6 trades = 50%
        self.assertAlmostEqual(summary["win_rate_percent"], (3/6)*100)

        # Average P&L: (100 - 50 + 200 - 80 + 120 + 0) / 6 = 290 / 6 = 48.333...
        self.assertAlmostEqual(summary["average_pnl_per_trade"], 290/6)

        # Profit Factor: Gross Profit (100+200+120=420) / Gross Loss (abs(-50-80)=130) = 420/130 = 3.2307...
        self.assertAlmostEqual(summary["profit_factor"], 420/130)

        self.assertEqual(summary["total_gross_profit"], 420)
        self.assertEqual(summary["total_gross_loss"], -130) # Sum of negative P&Ls
        self.assertEqual(summary["number_of_winning_trades"], 3)
        self.assertEqual(summary["number_of_losing_trades"], 2)

        # Avg Win: 420 / 3 = 140
        self.assertAlmostEqual(summary["average_profit_per_winning_trade"], 140)
        # Avg Loss: -130 / 2 = -65
        self.assertAlmostEqual(summary["average_loss_per_losing_trade"], -65)


    @patch('src.core.analytics_engine.get_realized_pnls_for_analytics')
    def test_get_performance_summary_no_trades(self, mock_get_pnls):
        mock_get_pnls.return_value = []
        mock_db_session = MagicMock(spec=Session)
        summary = analytics_engine.get_performance_summary(mock_db_session)

        self.assertEqual(summary["total_closed_trades"], 0)
        self.assertEqual(summary["win_rate_percent"], 0.0)
        self.assertEqual(summary["average_pnl_per_trade"], 0.0)
        self.assertEqual(summary["profit_factor"], 0.0)
        self.assertEqual(summary["total_gross_profit"], 0)
        self.assertEqual(summary["total_gross_loss"], 0)


    @patch('src.core.analytics_engine.get_realized_pnls_for_analytics')
    def test_get_performance_summary_all_wins(self, mock_get_pnls):
        sample_pnls = [10, 20, 30]
        mock_get_pnls.return_value = sample_pnls
        mock_db_session = MagicMock(spec=Session)
        summary = analytics_engine.get_performance_summary(mock_db_session)

        self.assertEqual(summary["total_closed_trades"], 3)
        self.assertEqual(summary["win_rate_percent"], 100.0)
        self.assertAlmostEqual(summary["average_pnl_per_trade"], 20.0)
        self.assertEqual(summary["profit_factor"], float('inf'))
        self.assertEqual(summary["total_gross_profit"], 60)
        self.assertEqual(summary["total_gross_loss"], 0)
        self.assertEqual(summary["number_of_winning_trades"], 3)
        self.assertEqual(summary["number_of_losing_trades"], 0)
        self.assertAlmostEqual(summary["average_profit_per_winning_trade"], 20)
        self.assertAlmostEqual(summary["average_loss_per_losing_trade"], 0)


    @patch('src.core.analytics_engine.get_realized_pnls_for_analytics')
    def test_get_performance_summary_all_losses(self, mock_get_pnls):
        sample_pnls = [-10, -20, -30]
        mock_get_pnls.return_value = sample_pnls
        mock_db_session = MagicMock(spec=Session)
        summary = analytics_engine.get_performance_summary(mock_db_session)

        self.assertEqual(summary["total_closed_trades"], 3)
        self.assertEqual(summary["win_rate_percent"], 0.0)
        self.assertAlmostEqual(summary["average_pnl_per_trade"], -20.0)
        self.assertEqual(summary["profit_factor"], 0.0)
        self.assertEqual(summary["total_gross_profit"], 0)
        self.assertEqual(summary["total_gross_loss"], -60)
        self.assertEqual(summary["number_of_winning_trades"], 0)
        self.assertEqual(summary["number_of_losing_trades"], 3)
        self.assertAlmostEqual(summary["average_profit_per_winning_trade"], 0)
        self.assertAlmostEqual(summary["average_loss_per_losing_trade"], -20)

    # Test for get_realized_pnls_for_analytics would require mocking the DB query itself.
    # This is more of an integration test for that specific function.
    # For now, we are testing the calculation functions that use its output.

if __name__ == '__main__':
    unittest.main()
