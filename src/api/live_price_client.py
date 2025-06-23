import yfinance as yf
from typing import Optional, Dict, Any

class LivePriceClient:
    """
    A client to fetch live/current stock prices using yfinance (Yahoo Finance).
    """

    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Fetches the current market price for a given stock symbol.
        'currentPrice' is often available for stocks.
        'regularMarketPrice' or 'chartPreviousClose' can be fallbacks.
        yfinance Ticker object's .info dictionary contains various price points.
        We'll try to get the most relevant "current" price.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Prioritize keys that usually reflect recent trading price
            if 'currentPrice' in info and info['currentPrice'] is not None:
                return float(info['currentPrice'])
            elif 'regularMarketPrice' in info and info['regularMarketPrice'] is not None:
                return float(info['regularMarketPrice'])
            elif 'previousClose' in info and info['previousClose'] is not None: # Fallback to previous close
                # This is less "live" but better than nothing if others are missing
                return float(info['previousClose'])
            else:
                # Try to get the most recent closing price from history if info is sparse
                hist = ticker.history(period="1d")
                if not hist.empty:
                    return float(hist['Close'].iloc[-1])

                print(f"Warning: Could not determine current price for {symbol} from yfinance info/history. Info: {info}")
                return None
        except Exception as e:
            print(f"Error fetching current price for {symbol} using yfinance: {e}")
            return None

    def get_stock_quote_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetches a more detailed quote for a stock symbol, similar to AlphaVantage's GLOBAL_QUOTE.
        We will map yfinance's `ticker.info` to a similar structure if possible.
        """
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            if not info or info.get('quoteType') == "NONE" or info.get('regularMarketPrice') is None : # Check if symbol is valid / has data
                # yfinance sometimes returns an empty dict or minimal data for invalid symbols
                if info.get(' предыдущее закрытие') is not None : # Fix for russian symbols
                    return {
                        "01. symbol": info.get('symbol', symbol),
                        "02. open": info.get('regularMarketOpen'),
                        "03. high": info.get('regularMarketDayHigh'),
                        "04. low": info.get('regularMarketDayLow'),
                        "05. price": info.get('regularMarketPrice', info.get('currentPrice', info.get(' предыдущее закрытие'))),
                        "06. volume": info.get('regularMarketVolume'),
                        "07. latest trading day": info.get('regularMarketTime'), # This is often a timestamp
                        "08. previous close": info.get('regularMarketPreviousClose', info.get(' предыдущее закрытие')),
                        "09. change": None, # yfinance doesn't directly provide 'change' and 'change percent' in .info easily
                        "10. change percent": None, # These would need calculation: price - prev_close
                    }
                print(f"Warning: No sufficient data found for symbol {symbol} via yfinance. Info: {info}")
                return None

            price = info.get('regularMarketPrice', info.get('currentPrice'))
            prev_close = info.get('regularMarketPreviousClose', info.get('chartPreviousClose'))

            change = None
            change_percent = None
            if price is not None and prev_close is not None:
                change = price - prev_close
                change_percent = (change / prev_close) * 100 if prev_close else 0.0

            # Map to AlphaVantage-like structure
            quote = {
                "01. symbol": info.get('symbol', symbol),
                "02. open": info.get('regularMarketOpen'),
                "03. high": info.get('regularMarketDayHigh'),
                "04. low": info.get('regularMarketDayLow'),
                "05. price": price,
                "06. volume": info.get('regularMarketVolume'),
                # 'regularMarketTime' is often an epoch timestamp, convert or note
                "07. latest trading day": datetime.datetime.fromtimestamp(info['regularMarketTime']).strftime('%Y-%m-%d') if 'regularMarketTime' in info else None,
                "08. previous close": prev_close,
                "09. change": change,
                "10. change percent": f"{change_percent:.4f}%" if change_percent is not None else None,
            }
            return quote
        except Exception as e:
            print(f"Error fetching detailed quote for {symbol} using yfinance: {e}")
            return None

if __name__ == '__main__':
    client = LivePriceClient()

    symbols_to_test = ["AAPL", "MSFT", "GOOGL", "NONEXISTENT_SYMBOL_XYZ", "GAZP.ME"] # Added a .ME symbol

    for sym in symbols_to_test:
        print(f"\n--- Testing Symbol: {sym} ---")

        current_price = client.get_current_price(sym)
        if current_price is not None:
            print(f"  Current Price for {sym}: {current_price}")
        else:
            print(f"  Could not fetch current price for {sym}.")

        detailed_quote = client.get_stock_quote_details(sym)
        if detailed_quote:
            print(f"  Detailed Quote for {sym}:")
            for key, value in detailed_quote.items():
                print(f"    {key}: {value}")
        else:
            print(f"  Could not fetch detailed quote for {sym}.")

    print("\nNote: yfinance data can be delayed (typically 15-20 mins for free sources like Yahoo Finance).")
    print("For true real-time, licensed data feeds are usually required.")
