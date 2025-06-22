import requests
import os

# TODO: Move API Key to environment variables or a secure configuration manager.
# For now, using the provided key directly.
ALPHA_VANTAGE_API_KEY = "SS1101G6BC9AHU38"
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

class AlphaVantageAPI:
    def __init__(self, api_key: str = ALPHA_VANTAGE_API_KEY):
        """
        Initializes the AlphaVantageAPI client.

        Args:
            api_key: The API key for Alpha Vantage.
        """
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key

    def _request(self, params: dict) -> dict:
        """
        Helper function to make requests to the Alpha Vantage API.

        Args:
            params: A dictionary of parameters to include in the API request.

        Returns:
            A dictionary containing the JSON response from the API.

        Raises:
            requests.exceptions.RequestException: If the request fails.
            ValueError: If the API response indicates an error or contains no data.
        """
        params['apikey'] = self.api_key
        response = requests.get(ALPHA_VANTAGE_BASE_URL, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

        data = response.json()

        # Check for API error messages
        if "Error Message" in data:
            raise ValueError(f"Alpha Vantage API Error: {data['Error Message']}")
        if "Information" in data and "the standard API call frequency is 5 calls per minute and 100 calls per day" in data["Information"]:
             # This is a rate limit information message, not necessarily an error for a single call
             # but can indicate that we might be rate limited soon.
             # For now, we will proceed but this could be logged.
             pass # Or log a warning: print(f"Alpha Vantage API Info: {data['Information']}")
        if not data:
            raise ValueError("API returned no data.")

        return data

    def get_stock_quote(self, symbol: str) -> dict:
        """
        Fetches a real-time stock quote for a given symbol.
        Uses the GLOBAL_QUOTE function from Alpha Vantage.

        Args:
            symbol: The stock symbol (e.g., "AAPL").

        Returns:
            A dictionary containing the stock quote data.
            Example:
            {
                "01. symbol": "IBM",
                "02. open": "143.0000",
                "03. high": "143.2100",
                "04. low": "141.7900",
                "05. price": "142.0900",
                "06. volume": "2906767",
                "07. latest trading day": "2023-10-27",
                "08. previous close": "142.7900",
                "09. change": "-0.7000",
                "10. change percent": "-0.4902%"
            }

        Raises:
            requests.exceptions.RequestException: If the request fails.
            ValueError: If the API response indicates an error or the symbol is not found.
        """
        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": symbol
        }
        data = self._request(params)

        quote_data = data.get("Global Quote")
        if not quote_data or not quote_data.get("01. symbol"): # Check if symbol exists in response
            raise ValueError(f"No data found for symbol: {symbol}. It might be an invalid symbol or delisted.")

        # Ensure all expected fields are present, even if empty, to maintain a consistent structure.
        # Alpha Vantage sometimes returns an empty object for "Global Quote" if the symbol is invalid.
        expected_keys = [
            "01. symbol", "02. open", "03. high", "04. low", "05. price",
            "06. volume", "07. latest trading day", "08. previous close",
            "09. change", "10. change percent"
        ]
        for key in expected_keys:
            if key not in quote_data:
                quote_data[key] = None # Or some other default like 'N/A' or 0

        return quote_data

    def get_option_chain(self, symbol: str):
        """
        Placeholder for fetching option chain data.
        Alpha Vantage's free plan does not directly support full option chain data.
        This method will need to be implemented if an alternative source or
        a premium Alpha Vantage plan is used.

        Args:
            symbol: The underlying stock symbol.

        Raises:
            NotImplementedError: As this feature is not currently supported.
        """
        # Alpha Vantage's standard API does not provide comprehensive option chain data.
        # Some FX and Crypto options are available, but not for general stocks.
        # For example, function=CRYPTO_OPTIONS_CHAIN or FX_OPTIONS_CHAIN might exist for premium users.
        # This is a known limitation.
        # If developing further, would need to investigate:
        # 1. Premium Alpha Vantage endpoints (if they exist for stock options).
        # 2. Other APIs (e.g., IEX Cloud, Tradier, Polygon.io)
        # 3. Web scraping (less reliable, more complex).
        print(f"Fetching option chain for {symbol} is not supported with the free Alpha Vantage plan for stocks.")
        raise NotImplementedError("Option chain data is not available through the free Alpha Vantage API for stocks.")

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    # IMPORTANT: Running this directly will make actual API calls.
    # Be mindful of API rate limits (5 calls per minute, 100 per day for free tier).

    # To run this example, you would typically do it from the project root:
    # python -m src.api.alpha_vantage

    api = AlphaVantageAPI()

    # Test with a valid symbol
    try:
        print("\nFetching quote for IBM...")
        ibm_quote = api.get_stock_quote("IBM")
        print("IBM Quote:")
        for key, value in ibm_quote.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error fetching IBM: {e}")

    # Test with a known invalid symbol (to check error handling)
    try:
        print("\nFetching quote for INVALID_SYMBOL...")
        invalid_quote = api.get_stock_quote("INVALID_SYMBOL_XYZ")
        print("INVALID_SYMBOL_XYZ Quote:", invalid_quote)
    except ValueError as e:
        print(f"Correctly handled error for INVALID_SYMBOL_XYZ: {e}")
    except Exception as e:
        print(f"An unexpected error occurred for INVALID_SYMBOL_XYZ: {e}")

    # Test option chain (will raise NotImplementedError)
    try:
        print("\nAttempting to fetch option chain for AAPL (expecting NotImplementedError)...")
        api.get_option_chain("AAPL")
    except NotImplementedError as e:
        print(f"Correctly caught: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while testing option chain: {e}")

    # Example of how to check rate limit info (if it occurs)
    # This is harder to reliably trigger without making many calls.
    # If you make >5 calls in a minute, subsequent calls might return something like:
    # {'Information': 'Thank you for using Alpha Vantage! Our standard API call frequency is 5 calls per minute and 100 calls per day. Please visit https://www.alphavantage.co/premium/ if you would like to target a higher API call frequency.'}
    # The current _request method handles "Error Message" but only passes on "Information".
    # For a production system, you'd want to log "Information" messages or handle them more gracefully.
    print("\nNote: Be mindful of API rate limits when running tests like these.")
