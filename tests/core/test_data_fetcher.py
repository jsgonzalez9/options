import unittest
from unittest.mock import patch, MagicMock
from src.core.data_fetcher import PriceFetcher
import datetime

class TestPriceFetcher(unittest.TestCase):

    @patch('src.core.data_fetcher.AlphaVantageAPI')
    @patch('src.core.data_fetcher.LivePriceClient')
    def setUp(self, MockLivePriceClient, MockAlphaVantageAPI):
        self.mock_av_client = MagicMock()
        MockAlphaVantageAPI.return_value = self.mock_av_client

        self.mock_live_client = MagicMock()
        MockLivePriceClient.return_value = self.mock_live_client

        self.fetcher_with_live = PriceFetcher(alpha_vantage_api_key="AV_TEST_KEY", use_live_client=True)
        self.fetcher_av_only = PriceFetcher(alpha_vantage_api_key="AV_TEST_KEY", use_live_client=False)

    def test_get_live_stock_price_success_live_client(self):
        self.mock_live_client.get_current_price.return_value = 150.75
        price = self.fetcher_with_live.get_live_stock_price("AAPL")
        self.assertEqual(price, 150.75)
        self.mock_live_client.get_current_price.assert_called_once_with("AAPL")
        self.mock_av_client.get_stock_quote.assert_not_called()

    def test_get_live_stock_price_fallback_to_av_on_live_client_failure(self):
        self.mock_live_client.get_current_price.side_effect = Exception("Live Client Error")
        self.mock_av_client.get_stock_quote.return_value = {"05. price": "140.25"}
        price = self.fetcher_with_live.get_live_stock_price("MSFT")
        self.assertEqual(price, 140.25)
        self.mock_live_client.get_current_price.assert_called_once_with("MSFT")
        self.mock_av_client.get_stock_quote.assert_called_once_with("MSFT")

    def test_get_live_stock_price_fallback_to_av_if_live_client_returns_none(self):
        self.mock_live_client.get_current_price.return_value = None
        self.mock_av_client.get_stock_quote.return_value = {"05. price": "130.50"}
        price = self.fetcher_with_live.get_live_stock_price("GOOG")
        self.assertEqual(price, 130.50)
        self.mock_live_client.get_current_price.assert_called_once_with("GOOG")
        self.mock_av_client.get_stock_quote.assert_called_once_with("GOOG")

    def test_get_live_stock_price_av_only_client_success(self):
        self.mock_av_client.get_stock_quote.return_value = {"05. price": "120.00"}
        price = self.fetcher_av_only.get_live_stock_price("AMZN")
        self.assertEqual(price, 120.00)
        self.mock_live_client.get_current_price.assert_not_called() # The class-level mock for LivePriceClient should not be called
        self.mock_av_client.get_stock_quote.assert_called_once_with("AMZN")

    def test_get_live_stock_price_all_fail(self):
        self.mock_live_client.get_current_price.side_effect = Exception("Live Client Error")
        self.mock_av_client.get_stock_quote.side_effect = Exception("AV Client Error")
        price = self.fetcher_with_live.get_live_stock_price("FAIL")
        self.assertIsNone(price)

    def test_get_live_stock_price_av_no_price_in_quote(self):
        self.mock_live_client.get_current_price.return_value = None
        self.mock_av_client.get_stock_quote.return_value = {"01. symbol": "AAPL"}
        price = self.fetcher_with_live.get_live_stock_price("AAPL")
        self.assertIsNone(price)

    @patch('src.core.data_fetcher.black_scholes')
    def test_calculate_option_greeks_custom_call_success_uses_live_client_price(self, mock_bs_module):
        self.mock_live_client.get_current_price.return_value = 100.00
        self.mock_av_client.get_stock_quote.return_value = {"05. price": "999.99"} # Should not be used

        mock_bs_module.black_scholes_call_price.return_value = 10.50
        # ... (rest of bs mocks)
        expiry_date = datetime.date.today() + datetime.timedelta(days=30)
        params = {"underlying_symbol": "XYZ", "strike_price": 100.0, "expiry_date": expiry_date, "risk_free_rate": 0.05, "volatility": 0.2, "option_type": "call"}

        results = self.fetcher_with_live.calculate_option_greeks_custom(**params) # Use fetcher_with_live

        self.assertEqual(results["underlying_price"], 100.00)
        self.mock_live_client.get_current_price.assert_called_once_with("XYZ")
        self.mock_av_client.get_stock_quote.assert_not_called() # Ensure AV wasn't called for price

    @patch('src.core.data_fetcher.black_scholes')
    def test_calculate_option_greeks_custom_put_success_av_only(self, mock_bs_module):
        # Test with fetcher_av_only
        self.mock_av_client.get_stock_quote.return_value = {"05. price": "95.00"}
        # ... (bs mocks) ...
        mock_bs_module.black_scholes_put_price.return_value = 8.20
        mock_bs_module.delta_put.return_value = -0.40
        mock_bs_module.gamma.return_value = 0.04
        mock_bs_module.vega.return_value = 0.18
        mock_bs_module.theta_put.return_value = -0.03
        mock_bs_module.rho_put.return_value = -0.12

        expiry_str = (datetime.date.today() + datetime.timedelta(days=60)).strftime("%Y-%m-%d")
        params = {"underlying_symbol": "ABC", "strike_price": 90.0, "expiry_date": expiry_str, "risk_free_rate": 0.03, "volatility": 0.25, "option_type": "put"}
        expected_T = 60.0 / 365.0

        results = self.fetcher_av_only.calculate_option_greeks_custom(**params) # Use fetcher_av_only

        self.assertEqual(results["underlying_price"], 95.00)
        self.mock_live_client.get_current_price.assert_not_called() # The class-level mock for LivePriceClient
        self.mock_av_client.get_stock_quote.assert_called_once_with("ABC")
        mock_bs_module.black_scholes_put_price.assert_called_once_with(95.0, 90.0, expected_T, 0.03, 0.25)


    def test_calculate_option_greeks_underlying_price_fetch_fails_all_sources(self):
        self.mock_live_client.get_current_price.return_value = None
        self.mock_av_client.get_stock_quote.side_effect = Exception("AV Error") # Both sources fail

        expiry_date = datetime.date.today() + datetime.timedelta(days=30)
        results = self.fetcher_with_live.calculate_option_greeks_custom("FAIL", 100, expiry_date, 0.05, 0.2, "call")
        self.assertIsNone(results)

    def test_calculate_option_greeks_invalid_option_type(self):
        self.mock_live_client.get_current_price.return_value = 100.00 # Assume price fetch success
        expiry_date = datetime.date.today() + datetime.timedelta(days=30)
        results = self.fetcher_with_live.calculate_option_greeks_custom("XYZ", 100, expiry_date, 0.05, 0.2, "invalid_type")
        self.assertIsNone(results)

    @patch('src.core.data_fetcher.black_scholes')
    def test_calculate_option_greeks_expired_option(self, mock_bs_module):
        self.mock_live_client.get_current_price.return_value = 100.00
        expiry_date = datetime.date.today() - datetime.timedelta(days=1)

        mock_bs_module.black_scholes_call_price.return_value = 0.0
        results = self.fetcher_with_live.calculate_option_greeks_custom("XYZ", 105, expiry_date, 0.05, 0.2, "call")
        self.assertIsNotNone(results)
        args, _ = mock_bs_module.black_scholes_call_price.call_args
        self.assertEqual(args[2], 0.0)

    def test_calculate_option_greeks_invalid_expiry_date_string_format(self):
        self.mock_live_client.get_current_price.return_value = 100.00
        results = self.fetcher_with_live.calculate_option_greeks_custom("XYZ", 100, "01-01-2025", 0.05, 0.2, "call")
        self.assertIsNone(results)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
