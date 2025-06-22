# Configuration settings for the application

# Standard multiplier for options contracts (e.g., 100 shares per contract)
OPTION_MULTIPLIER: int = 100

# Potentially other settings in the future:
# API_KEYS = {"alpha_vantage": "YOUR_KEY_HERE"} # Example
# DEFAULT_RISK_FREE_RATE = 0.01
# DEFAULT_VOLATILITY = 0.20
# DATABASE_URL = "sqlite:///./trading_journal.db" # Though this is in setup.py now

# Logging configuration could also go here or be a separate module.

if __name__ == '__main__':
    print(f"Option Multiplier from config: {OPTION_MULTIPLIER}")
