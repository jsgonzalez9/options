from sqlalchemy.orm import Session
from src.database import models, crud
from src.financial_models import black_scholes
from src.api.alpha_vantage import AlphaVantageAPI # For fetching live prices
from typing import Optional, Dict
import datetime

# Default values if not provided or found
DEFAULT_VOLATILITY = 0.20 # 20%
DEFAULT_RISK_FREE_RATE = 0.01 # 1%
# OPTION_MULTIPLIER is not typically used for summing deltas to get position delta,
# as delta itself is per share. Position delta is sum of (leg_delta * leg_quantity).

def calculate_time_to_expiry_years(expiry_date: datetime.date) -> float:
    """Calculates time to expiry in years from today."""
    if expiry_date < datetime.date.today():
        return 0.0 # Option expired
    return (expiry_date - datetime.date.today()).days / 365.0

def calculate_leg_delta(
    option_type: str,
    underlying_price: float,
    strike_price: float,
    time_to_expiry_years: float,
    volatility: float,
    risk_free_rate: float
) -> float:
    """
    Calculates the Black-Scholes Delta for a single option leg.
    """
    if time_to_expiry_years <= 0: # Option expired or at expiry
        if option_type.upper() == "CALL":
            return 1.0 if underlying_price > strike_price else 0.0 if underlying_price < strike_price else 0.5
        elif option_type.upper() == "PUT":
            return -1.0 if underlying_price < strike_price else 0.0 if underlying_price > strike_price else -0.5
        return 0.0

    if option_type.upper() == "CALL":
        return black_scholes.delta_call(underlying_price, strike_price, time_to_expiry_years, risk_free_rate, volatility)
    elif option_type.upper() == "PUT":
        return black_scholes.delta_put(underlying_price, strike_price, time_to_expiry_years, risk_free_rate, volatility)
    else:
        raise ValueError(f"Unknown option type: {option_type}")


def calculate_position_delta(
    db: Session,
    position: models.Position,
    price_fetcher: AlphaVantageAPI, # For live underlying prices
    # Allow overrides for vol and rfr, otherwise use defaults or future per-leg stored values
    volatility_override: Optional[float] = None,
    risk_free_rate_override: Optional[float] = None,
    underlying_prices_override: Optional[Dict[str, float]] = None # {symbol: price}
) -> float:
    """
    Calculates the total delta for a position by summing the deltas of its legs.
    This requires fetching the current underlying price for each unique symbol in the position's legs.
    Volatility and risk-free rate can be overridden or default values will be used.

    Args:
        db: SQLAlchemy session.
        position: The Position object (must have legs loaded).
        price_fetcher: Instance of AlphaVantageAPI to get live stock prices.
        volatility_override: Optional global volatility to use for all legs.
        risk_free_rate_override: Optional global risk-free rate for all legs.
        underlying_prices_override: Optional dict of {symbol: price} to use instead of fetching.

    Returns:
        Total position delta.
    """
    if not position.legs:
        return 0.0

    total_position_delta = 0.0

    # Determine unique underlying symbols for the position's legs
    # This assumes each leg somehow relates to an underlying symbol.
    # Our current OptionLeg model doesn't store the underlying symbol directly.
    # This is a gap. We need to associate legs with an underlying symbol.
    # For now, let's assume the position's `spread_type` might hint at the symbol,
    # or we'd need to add `underlying_symbol` to `OptionLeg` or `Position`.

    # TEMPORARY ASSUMPTION: Position.spread_type is the symbol (e.g. "AAPL Iron Condor")
    # This is a simplification and needs refinement.
    # A better way: add `underlying_symbol` to Position or OptionLeg model.

    # Let's assume for now that all legs in a position share the same underlying.
    # We'd need to get this symbol. If Position.spread_type is "SPY Iron Condor", symbol is "SPY".
    # This is highly dependent on how symbols are associated with positions.

    # For this example, we'll require an underlying_symbol to be inferable or passed.
    # Let's assume a function `get_underlying_symbol_for_position(position)` exists.
    # For now, we will mock this by trying to parse from spread_type or requiring it.

    # This function needs to be more robust. What if legs are on different underlyings?
    # For now, assume a single underlying for the position for simplicity of fetching.
    # A real system would need `underlying_symbol` on each `OptionLeg`.

    # ---- This section needs a robust way to get underlying symbols for legs ----
    # For demonstration, let's assume we can get a common symbol.
    # If `position.spread_type` is "XYZ Call Spread", we might infer "XYZ".
    # This is not robust.

    # A better approach (if not changing model): Group legs by (strike, expiry, type) and assume they share underlying.
    # Still need a way to get that underlying.

    # For now, this function will be limited if underlying_symbol isn't clear.
    # Let's assume we have a way to get a dictionary of {leg_id: underlying_symbol}.
    # Or, more simply, if all legs share one underlying for the position.

    # Simplification: Assume all legs in the position refer to ONE underlying.
    # The caller of this function should provide the symbol or it should be on Position model.
    # Let's say we try to infer it from spread_type, e.g. "AAPL Bull Call" -> "AAPL"
    # This is a placeholder for a better symbol resolution mechanism.
    inferred_symbol = position.spread_type.split(" ")[0] if position.spread_type else None # Very naive

    if not inferred_symbol and not underlying_prices_override:
        # Cannot proceed without a symbol to fetch prices or an override.
        # In a real API, the symbol might come from the Position model or be a parameter.
        print(f"Warning: Could not determine underlying symbol for position {position.id} to calculate delta.")
        return 0.0 # Or raise error

    current_underlying_price = None
    if underlying_prices_override and inferred_symbol in underlying_prices_override:
        current_underlying_price = underlying_prices_override[inferred_symbol]
    elif inferred_symbol:
        try:
            # This is a live API call. Consider caching or rate limits.
            quote = price_fetcher.get_stock_quote(inferred_symbol)
            current_underlying_price = float(quote["05. price"])
        except Exception as e:
            print(f"Could not fetch live price for {inferred_symbol} for delta calc: {e}")
            # Fallback or error. For now, can't calculate delta accurately.
            return 0.0 # Or raise an error indicating price fetch failure.

    if current_underlying_price is None:
        print(f"Failed to obtain underlying price for {inferred_symbol} for position {position.id}.")
        return 0.0

    # Use provided overrides or defaults for vol and rfr
    vol = volatility_override if volatility_override is not None else DEFAULT_VOLATILITY
    rfr = risk_free_rate_override if risk_free_rate_override is not None else DEFAULT_RISK_FREE_RATE

    for leg in position.legs:
        time_to_expiry = calculate_time_to_expiry_years(leg.expiry_date)

        leg_delta_value = calculate_leg_delta(
            option_type=leg.option_type,
            underlying_price=current_underlying_price, # Assuming same underlying for all legs
            strike_price=leg.strike_price,
            time_to_expiry_years=time_to_expiry,
            volatility=vol, # Using global/default vol for now
            risk_free_rate=rfr # Using global/default rfr for now
        )

        # Position delta = sum (leg_delta * leg_quantity)
        # Note: leg_quantity is +ve for long, -ve for short.
        # Black-Scholes delta for call is [0,1], for put is [-1,0].
        # Example: Long 1 Call (Delta 0.6) -> +0.6 * 1 = +0.6
        # Example: Short 1 Call (Delta 0.6) -> +0.6 * -1 = -0.6
        # Example: Long 1 Put (Delta -0.4) -> -0.4 * 1 = -0.4
        # Example: Short 1 Put (Delta -0.4) -> -0.4 * -1 = +0.4
        total_position_delta += leg_delta_value * leg.quantity

    return total_position_delta


if __name__ == '__main__':
    print("--- Derivatives Calculator Examples ---")

    # 1. Time to Expiry
    date_in_30_days = datetime.date.today() + datetime.timedelta(days=30)
    T_30 = calculate_time_to_expiry_years(date_in_30_days)
    print(f"Time to expiry for 30 days: {T_30:.4f} years (approx {30/365:.4f})")
    # self.assertAlmostEqual(T_30, 30/365, places=4) # This is for unittest, remove from main block

    # 2. Leg Delta
    # Call option: S=100, K=100, T=0.25 (3 months), r=0.01, sigma=0.20
    # d1 = (ln(100/100) + (0.01 + 0.5*0.2^2)*0.25) / (0.2*sqrt(0.25))
    # d1 = (0 + (0.01 + 0.02)*0.25) / (0.2*0.5) = (0.03*0.25) / 0.1 = 0.0075 / 0.1 = 0.075
    # N(0.075) is approx 0.5299 for call delta
    delta_c = calculate_leg_delta("CALL", 100, 100, 0.25, 0.20, 0.01)
    print(f"Call Delta (ATM-ish): {delta_c:.4f}") # Expected around 0.5299

    # Put option: S=100, K=100, T=0.25, r=0.01, sigma=0.20
    # Delta Put = N(d1) - 1 = 0.5299 - 1 = -0.4701
    delta_p = calculate_leg_delta("PUT", 100, 100, 0.25, 0.20, 0.01)
    print(f"Put Delta (ATM-ish): {delta_p:.4f}") # Expected around -0.4701

    # Expired options
    delta_c_exp_itm = calculate_leg_delta("CALL", 105, 100, 0, 0.20, 0.01)
    print(f"Expired ITM Call Delta: {delta_c_exp_itm}") # Expected 1.0
    delta_p_exp_itm = calculate_leg_delta("PUT", 95, 100, 0, 0.20, 0.01)
    print(f"Expired ITM Put Delta: {delta_p_exp_itm}") # Expected -1.0


    # 3. Position Delta (Conceptual - requires DB, Position object, PriceFetcher)
    # This part is harder to unit test without more mocking or a live setup.
    # The logic relies on iterating legs and summing (leg_delta * leg_quantity).
    print("\nPosition Delta calculation would require a mock DB and PriceFetcher setup.")
    # Example: Bull Call Spread: Long 1 100C (Delta ~0.53), Short 1 105C (Delta ~0.30 for ITM-ness if S=100)
    # If S=100, K_short=105, T=0.25, r=0.01, sigma=0.20
    # d1_short = (ln(100/105) + (0.01 + 0.5*0.2^2)*0.25) / (0.2*0.5)
    # d1_short = (-0.04879 + 0.0075) / 0.1 = -0.04129 / 0.1 = -0.4129
    # N(-0.4129) ~ 0.34 (Delta of the short call)
    # Position Delta = (0.5299 * 1) + (0.34 * -1) = 0.5299 - 0.34 = ~0.1899 (Net long delta)

    # This example assumes you have a way to run an AlphaVantageAPI instance for price_fetcher
    # and a database session for db.
    # For true unit tests, these would be mocked.
    # class MockPriceFetcher:
    #     def get_stock_quote(self, symbol):
    #         if symbol == "XYZ": return {"05. price": "100.00"}
    #         raise ValueError("Unknown symbol for mock fetcher")
    #
    # mock_fetcher = MockPriceFetcher()
    # # db_session = ... (mocked or real test session)
    # # position_obj = ... (a Position with legs on "XYZ")
    # # total_delta = calculate_position_delta(db_session, position_obj, mock_fetcher)
    # # print(f"Example Position Delta: {total_delta}")

    print("\nDerivatives Calculator examples finished.")
