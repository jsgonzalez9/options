import unittest
from unittest.mock import patch, MagicMock
from src.api.alpha_vantage import AlphaVantageAPI, ALPHA_VANTAGE_API_KEY
import requests

class TestAlphaVantageAPI(unittest.TestCase):

    def setUp(self):
        # Using a test key, though the actual key is hardcoded in the module for now
        self.api = AlphaVantageAPI(api_key="TEST_API_KEY")

    def test_initialization_with_key(self):
        api = AlphaVantageAPI(api_key="CUSTOM_KEY")
        self.assertEqual(api.api_key, "CUSTOM_KEY")

    def test_initialization_without_key_uses_default(self):
        # This test relies on the hardcoded ALPHA_VANTAGE_API_KEY in the module
        # If that default changes, this test might need adjustment or the module's default handling.
        api = AlphaVantageAPI() # Relies on default key in module
        self.assertEqual(api.api_key, ALPHA_VANTAGE_API_KEY)


    def test_initialization_empty_key_raises_value_error(self):
        with self.assertRaises(ValueError):
            AlphaVantageAPI(api_key="")

    @patch('src.api.alpha_vantage.requests.get')
    def test_get_stock_quote_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Global Quote": {
                "01. symbol": "MSFT",
                "02. open": "400.0000",
                "03. high": "401.0000",
                "04. low": "399.0000",
                "05. price": "400.5000",
                "06. volume": "1000000",
                "07. latest trading day": "2024-03-15",
                "08. previous close": "399.0000",
                "09. change": "1.5000",
                "10. change percent": "0.3759%"
            }
        }
        mock_get.return_value = mock_response

        quote = self.api.get_stock_quote("MSFT")
        self.assertIsNotNone(quote)
        self.assertEqual(quote["01. symbol"], "MSFT")
        self.assertEqual(quote["05. price"], "400.5000")

        expected_url = "https://www.alphavantage.co/query"
        mock_get.assert_called_once_with(expected_url, params={
            "function": "GLOBAL_QUOTE",
            "symbol": "MSFT",
            "apikey": "TEST_API_KEY"
        })

    @patch('src.api.alpha_vantage.requests.get')
    def test_get_stock_quote_api_error_message(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200 # API errors often come with 200 OK but JSON content error
        mock_response.json.return_value = {"Error Message": "Invalid API call."}
        mock_get.return_value = mock_response

        with self.assertRaisesRegex(ValueError, "Alpha Vantage API Error: Invalid API call."):
            self.api.get_stock_quote("MSFT")

    @patch('src.api.alpha_vantage.requests.get')
    def test_get_stock_quote_empty_global_quote(self, mock_get):
        # This simulates when a symbol might be invalid or data isn't available
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Global Quote": {}} # Empty global quote
        mock_get.return_value = mock_response

        with self.assertRaisesRegex(ValueError, "No data found for symbol: INVALID"):
            self.api.get_stock_quote("INVALID")

    @patch('src.api.alpha_vantage.requests.get')
    def test_get_stock_quote_no_global_quote_key(self, mock_get):
        # This simulates an unexpected API response structure
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Unexpected": "data"}
        mock_get.return_value = mock_response

        with self.assertRaisesRegex(ValueError, "No data found for symbol: UNKNOWN"):
            self.api.get_stock_quote("UNKNOWN")


    @patch('src.api.alpha_vantage.requests.get')
    def test_get_stock_quote_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_get.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            self.api.get_stock_quote("MSFT")

    @patch('src.api.alpha_vantage.requests.get')
    def test_get_stock_quote_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network Error")

        with self.assertRaises(requests.exceptions.RequestException):
            self.api.get_stock_quote("MSFT")

    @patch('src.api.alpha_vantage.requests.get')
    def test_api_rate_limit_information_message(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        # This message should not raise an error but allow data processing if other data is present
        mock_response.json.return_value = {
            "Information": "Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute and 100 calls per day.",
            "Global Quote": { # Assume valid data is still returned alongside information
                "01. symbol": "IBM", "05. price": "150.00"
            }
        }
        mock_get.return_value = mock_response

        quote = self.api.get_stock_quote("IBM")
        self.assertIsNotNone(quote)
        self.assertEqual(quote["01. symbol"], "IBM")
        # No error should be raised due to the "Information" message.

    def test_get_option_chain_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.api.get_option_chain("MSFT")

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
