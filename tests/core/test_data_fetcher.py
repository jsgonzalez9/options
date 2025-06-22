import unittest
from unittest.mock import patch, MagicMock
from src.core.data_fetcher import PriceFetcher
import datetime

class TestPriceFetcher(unittest.TestCase):

    @patch('src.core.data_fetcher.AlphaVantageAPI')
    def setUp(self, MockAlphaVantageAPI):
        self.mock_api_client = MagicMock()
        MockAlphaVantageAPI.return_value = self.mock_api_client
        self.fetcher = PriceFetcher(api_key="TEST_KEY") # API key passed but mock is used

    def test_get_live_stock_price_success(self):
        self.mock_api_client.get_stock_quote.return_value = {"05. price": "150.75"}
        price = self.fetcher.get_live_stock_price("AAPL")
        self.assertEqual(price, 150.75)
        self.mock_api_client.get_stock_quote.assert_called_once_with("AAPL")

    def test_get_live_stock_price_api_failure(self):
        self.mock_api_client.get_stock_quote.side_effect = Exception("API Error")
        price = self.fetcher.get_live_stock_price("AAPL")
        self.assertIsNone(price)

    def test_get_live_stock_price_no_price_in_quote(self):
        self.mock_api_client.get_stock_quote.return_value = {"01. symbol": "AAPL"} # Missing '05. price'
        price = self.fetcher.get_live_stock_price("AAPL")
        self.assertIsNone(price)

    @patch('src.core.data_fetcher.black_scholes')
    def test_calculate_option_greeks_custom_call_success(self, mock_bs_module):
        # Mock underlying price fetch
        self.mock_api_client.get_stock_quote.return_value = {"05. price": "100.00"}

        # Mock Black-Scholes calculations
        mock_bs_module.black_scholes_call_price.return_value = 10.50
        mock_bs_module.delta_call.return_value = 0.60
        mock_bs_module.gamma.return_value = 0.05
        mock_bs_module.vega.return_value = 0.20
        mock_bs_module.theta_call.return_value = -0.05
        mock_bs_module.rho_call.return_value = 0.15

        expiry_date = datetime.date.today() + datetime.timedelta(days=30)
        params = {
            "underlying_symbol": "XYZ",
            "strike_price": 100.0,
            "expiry_date": expiry_date,
            "risk_free_rate": 0.05,
            "volatility": 0.2,
            "option_type": "call"
        }

        expected_T = 30.0 / 365.0

        results = self.fetcher.calculate_option_greeks_custom(**params)

        self.assertIsNotNone(results)
        self.assertEqual(results["underlying_price"], 100.00)
        self.assertEqual(results["theoretical_price"], 10.50)
        self.assertEqual(results["delta"], 0.60)
        self.assertEqual(results["gamma"], 0.05)
        self.assertEqual(results["vega"], 0.20)
        self.assertEqual(results["theta"], -0.05)
        self.assertEqual(results["rho"], 0.15)

        self.mock_api_client.get_stock_quote.assert_called_once_with("XYZ")
        mock_bs_module.black_scholes_call_price.assert_called_once_with(100.0, 100.0, expected_T, 0.05, 0.2)
        mock_bs_module.delta_call.assert_called_once_with(100.0, 100.0, expected_T, 0.05, 0.2)
        mock_bs_module.gamma.assert_called_once_with(100.0, 100.0, expected_T, 0.05, 0.2)
        # ... and so on for other BS functions

    @patch('src.core.data_fetcher.black_scholes')
    def test_calculate_option_greeks_custom_put_success(self, mock_bs_module):
        self.mock_api_client.get_stock_quote.return_value = {"05. price": "95.00"}

        mock_bs_module.black_scholes_put_price.return_value = 8.20
        mock_bs_module.delta_put.return_value = -0.40
        mock_bs_module.gamma.return_value = 0.04 # Assuming gamma is same call/put
        mock_bs_module.vega.return_value = 0.18  # Assuming vega is same call/put
        mock_bs_module.theta_put.return_value = -0.03
        mock_bs_module.rho_put.return_value = -0.12

        expiry_str = (datetime.date.today() + datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        params = {
            "underlying_symbol": "ABC",
            "strike_price": 90.0,
            "expiry_date": expiry_str, # Test with string date
            "risk_free_rate": 0.03,
            "volatility": 0.25,
            "option_type": "put"
        }

        expected_T = 60.0 / 365.0

        results = self.fetcher.calculate_option_greeks_custom(**params)

        self.assertIsNotNone(results)
        self.assertEqual(results["underlying_price"], 95.00)
        self.assertEqual(results["theoretical_price"], 8.20)
        self.assertEqual(results["delta"], -0.40)
        # ... check other greeks

        self.mock_api_client.get_stock_quote.assert_called_once_with("ABC")
        mock_bs_module.black_scholes_put_price.assert_called_once_with(95.0, 90.0, expected_T, 0.03, 0.25)


    def test_calculate_option_greeks_underlying_price_fetch_fails(self):
        self.mock_api_client.get_stock_quote.return_value = None # Simulate failure

        expiry_date = datetime.date.today() + datetime.timedelta(days=30)
        results = self.fetcher.calculate_option_greeks_custom("FAIL", 100, expiry_date, 0.05, 0.2, "call")
        self.assertIsNone(results)

    def test_calculate_option_greeks_invalid_option_type(self):
        self.mock_api_client.get_stock_quote.return_value = {"05. price": "100.00"}
        expiry_date = datetime.date.today() + datetime.timedelta(days=30)
        results = self.fetcher.calculate_option_greeks_custom("XYZ", 100, expiry_date, 0.05, 0.2, "invalid_type")
        self.assertIsNone(results)

    def test_calculate_option_greeks_expired_option(self):
        self.mock_api_client.get_stock_quote.return_value = {"05. price": "100.00"}
        expiry_date = datetime.date.today() - datetime.timedelta(days=1) # Yesterday

        with patch('src.core.data_fetcher.black_scholes') as mock_bs_module:
            mock_bs_module.black_scholes_call_price.return_value = 0.0 # Expected for expired OTM
            # ... mock other greeks if necessary for T=0

            results = self.fetcher.calculate_option_greeks_custom("XYZ", 105, expiry_date, 0.05, 0.2, "call")
            self.assertIsNotNone(results)
            # Check that T was effectively 0 for BS calculations
            args, _ = mock_bs_module.black_scholes_call_price.call_args
            self.assertEqual(args[2], 0.0) # T (time_to_expiry) should be 0

    def test_calculate_option_greeks_invalid_expiry_date_string_format(self):
        self.mock_api_client.get_stock_quote.return_value = {"05. price": "100.00"}
        results = self.fetcher.calculate_option_greeks_custom("XYZ", 100, "01-01-2025", 0.05, 0.2, "call") # Wrong format
        self.assertIsNone(results)


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
