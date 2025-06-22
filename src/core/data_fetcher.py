from src.api.alpha_vantage import AlphaVantageAPI
from src.financial_models import black_scholes
import datetime

class PriceFetcher:
    def __init__(self, api_key: str = None):
        """
        Initializes the PriceFetcher.

        Args:
            api_key: Optional Alpha Vantage API key. If None, AlphaVantageAPI will use its default.
        """
        self.api_client = AlphaVantageAPI(api_key=api_key if api_key else "SS1101G6BC9AHU38") # Ensure API key is passed

    def get_live_stock_price(self, symbol: str) -> float | None:
        """
        Fetches the live price of a stock.

        Args:
            symbol: The stock symbol (e.g., "AAPL").

        Returns:
            The current price as a float, or None if an error occurs or price isn't found.
        """
        try:
            quote = self.api_client.get_stock_quote(symbol)
            price_str = quote.get("05. price")
            if price_str:
                return float(price_str)
            else:
                print(f"Could not find price for {symbol} in quote: {quote}")
                return None
        except Exception as e:
            print(f"Error fetching stock price for {symbol}: {e}")
            return None

    def calculate_option_greeks_custom(self,
                                       underlying_symbol: str,
                                       strike_price: float,
                                       # Expiry can be a date object or string YYYY-MM-DD
                                       expiry_date: datetime.date | str,
                                       risk_free_rate: float,
                                       volatility: float,
                                       option_type: str = "call") -> dict | None:
        """
        Calculates theoretical option price and Greeks for a custom-defined option contract.
        This method is used when direct option market data (like current option price or implied volatility)
        is not available from the API for a specific contract. The user must provide all parameters,
        including volatility.

        Args:
            underlying_symbol: The symbol of the underlying stock.
            strike_price: The strike price of the option.
            expiry_date: The expiration date of the option (datetime.date object or "YYYY-MM-DD" string).
            risk_free_rate: The annualized risk-free interest rate (e.g., 0.05 for 5%).
            volatility: The annualized volatility of the underlying stock (e.g., 0.20 for 20%).
            option_type: Type of option, "call" or "put". Default is "call".

        Returns:
            A dictionary containing the calculated theoretical price and Greeks,
            or None if fetching the underlying price fails.
            Example:
            {
                "underlying_price": 150.00,
                "theoretical_price": 10.50,
                "delta": 0.65,
                "gamma": 0.05,
                "vega": 0.20,
                "theta": -0.05,
                "rho": 0.10
            }
        """
        S = self.get_live_stock_price(underlying_symbol)
        if S is None:
            print(f"Could not calculate Greeks for option on {underlying_symbol} due to failed underlying price fetch.")
            return None

        K = strike_price
        r = risk_free_rate
        sigma = volatility

        if isinstance(expiry_date, str):
            try:
                expiry_date = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
            except ValueError:
                print("Invalid expiry_date string format. Please use YYYY-MM-DD.")
                return None

        time_to_expiry_days = (expiry_date - datetime.date.today()).days
        if time_to_expiry_days < 0:
            print("Warning: Option appears to have already expired.")
            T = 0.0
        else:
            T = time_to_expiry_days / 365.0 # Convert days to years


        results = {"underlying_price": S}

        if option_type.lower() == "call":
            results["theoretical_price"] = black_scholes.black_scholes_call_price(S, K, T, r, sigma)
            results["delta"] = black_scholes.delta_call(S, K, T, r, sigma)
            results["theta"] = black_scholes.theta_call(S, K, T, r, sigma)
            results["rho"] = black_scholes.rho_call(S, K, T, r, sigma)
        elif option_type.lower() == "put":
            results["theoretical_price"] = black_scholes.black_scholes_put_price(S, K, T, r, sigma)
            results["delta"] = black_scholes.delta_put(S, K, T, r, sigma)
            results["theta"] = black_scholes.theta_put(S, K, T, r, sigma)
            results["rho"] = black_scholes.rho_put(S, K, T, r, sigma)
        else:
            print(f"Invalid option type: {option_type}. Choose 'call' or 'put'.")
            return None

        # Gamma and Vega are the same for calls and puts
        results["gamma"] = black_scholes.gamma(S, K, T, r, sigma)
        results["vega"] = black_scholes.vega(S, K, T, r, sigma)

        return results

if __name__ == '__main__':
    # IMPORTANT: Running this directly will make actual API calls via AlphaVantageAPI.
    # Be mindful of API rate limits.
    # python -m src.core.data_fetcher

    fetcher = PriceFetcher() # Uses the default API key SS1101G6BC9AHU38

    # 1. Test fetching stock price
    stock_symbol = "MSFT" # Microsoft
    print(f"\nFetching live stock price for {stock_symbol}...")
    live_price = fetcher.get_live_stock_price(stock_symbol)
    if live_price is not None:
        print(f"Current price of {stock_symbol}: {live_price}")
    else:
        print(f"Failed to fetch price for {stock_symbol}.")

    stock_symbol_invalid = "INVALIDXYZ"
    print(f"\nFetching live stock price for {stock_symbol_invalid}...")
    live_price_invalid = fetcher.get_live_stock_price(stock_symbol_invalid)
    if live_price_invalid is not None:
        print(f"Current price of {stock_symbol_invalid}: {live_price_invalid}")
    else:
        print(f"Correctly failed to fetch price for {stock_symbol_invalid}.")


    # 2. Test calculating option greeks with user-provided parameters
    # These are hypothetical parameters for an MSFT call option
    # For real use, volatility (sigma) would ideally be implied volatility if available,
    # or a carefully chosen historical/forecasted volatility.
    print(f"\nCalculating Greeks for a hypothetical {stock_symbol} call option...")
    if live_price: # Proceed only if we got a live price for MSFT
        strike = live_price + 10 # Hypothetical strike price slightly OTM
        expiry = (datetime.date.today() + datetime.timedelta(days=90)) # 90 days to expiry
        rfr = 0.05  # 5% risk-free rate
        vol = 0.25  # 25% annualized volatility (example)

        call_greeks = fetcher.calculate_option_greeks_custom(
            underlying_symbol=stock_symbol,
            strike_price=strike,
            expiry_date=expiry,
            risk_free_rate=rfr,
            volatility=vol,
            option_type="call"
        )

        if call_greeks:
            print(f"Calculated Call Option Greeks for {stock_symbol} (K={strike}, Exp={expiry.strftime('%Y-%m-%d')}):")
            for greek, value in call_greeks.items():
                print(f"  {greek}: {value:.4f}" if isinstance(value, float) else f"  {greek}: {value}")
        else:
            print(f"Failed to calculate call option Greeks for {stock_symbol}.")

        # Example for a Put option
        put_greeks = fetcher.calculate_option_greeks_custom(
            underlying_symbol=stock_symbol,
            strike_price=live_price - 10, # Hypothetical ITM put
            expiry_date=expiry.strftime("%Y-%m-%d"), # Test with string date
            risk_free_rate=rfr,
            volatility=vol,
            option_type="put"
        )
        if put_greeks:
            print(f"\nCalculated Put Option Greeks for {stock_symbol} (K={live_price-10}, Exp={expiry.strftime('%Y-%m-%d')}):")
            for greek, value in put_greeks.items():
                print(f"  {greek}: {value:.4f}" if isinstance(value, float) else f"  {greek}: {value}")
        else:
            print(f"Failed to calculate put option Greeks for {stock_symbol}.")

    else:
        print(f"\nSkipping option Greek calculation example because base price for {stock_symbol} was not fetched.")

    print("\nNote: Ensure `requests` and `scipy` are installed (`pip install requests scipy`).")
    print("Be mindful of Alpha Vantage API rate limits if running this example frequently.")
