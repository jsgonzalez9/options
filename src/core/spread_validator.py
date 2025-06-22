from typing import List, Dict, Any
import datetime

# --- Spread Validation Functions ---

def _get_leg_details(leg_data: Dict[str, Any]):
    """Helper to extract common details for easier access."""
    return {
        "type": leg_data.get("option_type", "").upper(),
        "strike": leg_data.get("strike_price"),
        "expiry": leg_data.get("expiry_date"), # Expected as datetime.date
        "quantity": leg_data.get("quantity"), # int, positive for long, negative for short
    }

def validate_bull_call_spread(legs_data: List[Dict[str, Any]]) -> (bool, str):
    """
    Validates if the provided legs constitute a Bull Call Spread.
    Rules:
    1. Exactly two legs.
    2. Both legs must be CALLs.
    3. One leg must be long (quantity > 0), one leg must be short (quantity < 0).
    4. Both legs must have the same expiry date.
    5. The long call must have a lower strike price than the short call.
    """
    if not legs_data or len(legs_data) != 2:
        return False, "Bull Call Spread must have exactly two legs."

    leg1 = _get_leg_details(legs_data[0])
    leg2 = _get_leg_details(legs_data[1])

    # Rule 2: Both CALLs
    if not (leg1["type"] == "CALL" and leg2["type"] == "CALL"):
        return False, "Both legs of a Bull Call Spread must be CALL options."

    # Rule 3: One long, one short
    if not ((leg1["quantity"] > 0 and leg2["quantity"] < 0) or \
            (leg1["quantity"] < 0 and leg2["quantity"] > 0)):
        return False, "Bull Call Spread requires one long call and one short call."

    # Determine long and short leg
    long_leg = leg1 if leg1["quantity"] > 0 else leg2
    short_leg = leg2 if leg1["quantity"] > 0 else leg1

    # Rule 4: Same expiry
    if long_leg["expiry"] != short_leg["expiry"]:
        return False, "Both legs of a Bull Call Spread must have the same expiry date."

    # Rule 5: Long call strike < short call strike
    if not (long_leg["strike"] is not None and short_leg["strike"] is not None and \
            long_leg["strike"] < short_leg["strike"]):
        return False, "For a Bull Call Spread, the long call strike must be lower than the short call strike."

    return True, "Valid Bull Call Spread."


def validate_iron_condor(legs_data: List[Dict[str, Any]]) -> (bool, str):
    """
    Validates if the provided legs constitute an Iron Condor.
    Rules:
    1. Exactly four legs.
    2. All legs must have the same expiry date.
    3. Consists of:
        - One long PUT (lower strike)
        - One short PUT (higher strike, below current price)
        - One short CALL (higher strike, above current price)
        - One long CALL (highest strike)
    4. Strike prices must be in order: Long Put K < Short Put K < Short Call K < Long Call K.
       (Short Put K and Short Call K form the 'body' of the condor).
    5. All quantities must be for the same number of contracts (e.g., all 1 or all -1, etc., for their type).
       Standard condor has quantities like +1, -1, -1, +1 for (long P, short P, short C, long C).
    """
    if not legs_data or len(legs_data) != 4:
        return False, "Iron Condor must have exactly four legs."

    legs = [_get_leg_details(leg) for leg in legs_data]

    # Rule 2: Same expiry for all
    first_expiry = legs[0]["expiry"]
    if not all(leg["expiry"] == first_expiry for leg in legs):
        return False, "All legs of an Iron Condor must have the same expiry date."

    # Categorize legs
    puts = sorted([leg for leg in legs if leg["type"] == "PUT"], key=lambda x: x["strike"])
    calls = sorted([leg for leg in legs if leg["type"] == "CALL"], key=lambda x: x["strike"])

    if not (len(puts) == 2 and len(calls) == 2):
        return False, "Iron Condor must consist of two PUTs and two CALLs."

    long_put = puts[0] if puts[0]["quantity"] > 0 else None
    short_put = puts[1] if puts[1]["quantity"] < 0 else None
    if not long_put or not short_put: # Could be a reversed order in puts list if strikes are same but quantities differ
        long_put = puts[1] if puts[1]["quantity"] > 0 else None
        short_put = puts[0] if puts[0]["quantity"] < 0 else None

    short_call = calls[0] if calls[0]["quantity"] < 0 else None
    long_call = calls[1] if calls[1]["quantity"] > 0 else None
    if not short_call or not long_call:
        short_call = calls[1] if calls[1]["quantity"] < 0 else None
        long_call = calls[0] if calls[0]["quantity"] > 0 else None


    if not (long_put and short_put and short_call and long_call):
        return False, "Iron Condor structure incorrect: requires one long put, one short put, one short call, and one long call."

    # Rule 5: Quantities (absolute value should be consistent for a standard condor)
    # Example: +1 long P, -1 short P, -1 short C, +1 long C.
    # Or +5, -5, -5, +5.
    # The quantities provided are per leg, so abs(long_put['quantity']) should equal abs(short_put['quantity']) etc.
    abs_qty = abs(long_put["quantity"])
    if not (abs(short_put["quantity"]) == abs_qty and \
            abs(short_call["quantity"]) == abs_qty and \
            abs(long_call["quantity"]) == abs_qty):
        return False, "All legs of an Iron Condor should typically involve the same absolute number of contracts."


    # Rule 4: Strike prices order: Long Put K < Short Put K < Short Call K < Long Call K
    if not (long_put["strike"] < short_put["strike"] < \
            short_call["strike"] < long_call["strike"]):
        return False, ("Strike prices for Iron Condor are not in the correct order. "
                       "Expected: Long Put K < Short Put K < Short Call K < Long Call K.")

    return True, "Valid Iron Condor."


# --- Main Validator Dispatcher ---
# This will be used by CRUD operations.

SPREAD_VALIDATORS = {
    "BULL CALL SPREAD": validate_bull_call_spread,
    "IRON CONDOR": validate_iron_condor,
    # Add other spread types and their validators here
    # "BEAR PUT SPREAD": validate_bear_put_spread,
    # "BUTTERFLY SPREAD": validate_butterfly_spread,
}

def validate_spread_legs(spread_type: str, legs_data: List[Dict[str, Any]]) -> (bool, str):
    """
    Validates legs for a given spread type.

    Args:
        spread_type: The type of spread (e.g., "BULL CALL SPREAD").
        legs_data: A list of dictionaries, where each dict contains details for an option leg.
                   Required keys in leg_data dicts: "option_type", "strike_price",
                                                   "expiry_date", "quantity".

    Returns:
        A tuple (bool, str): (isValid, message).
    """
    validator = SPREAD_VALIDATORS.get(spread_type.upper())
    if not validator:
        # If no specific validator, consider it valid or return a specific message.
        # For now, if it's not a known spread type for validation, we'll say it's "unchecked".
        # Or, one could default to False if strict validation for listed types is required.
        return True, f"No specific validator for spread type '{spread_type}'. Allowed by default."
        # return False, f"Unknown or unsupported spread type for validation: {spread_type}"


    # Ensure necessary keys are in legs_data for the validators
    for i, leg_d in enumerate(legs_data):
        if not all(k in leg_d for k in ["option_type", "strike_price", "expiry_date", "quantity"]):
            return False, f"Leg {i+1} data is missing one or more required keys (option_type, strike_price, expiry_date, quantity)."
        if not isinstance(leg_d["expiry_date"], datetime.date):
             return False, f"Leg {i+1} expiry_date must be a datetime.date object."


    return validator(legs_data)


if __name__ == '__main__':
    print("Testing Spread Validators...")

    # Test Bull Call Spread
    print("\n--- Bull Call Spread Tests ---")
    valid_bcs_legs = [
        {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1}, # Long
        {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1} # Short
    ]
    is_valid, msg = validate_spread_legs("BULL CALL SPREAD", valid_bcs_legs)
    print(f"Valid BCS: {is_valid}, {msg}")
    assert is_valid

    invalid_bcs_legs1 = [ # Wrong number of legs
        {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1}
    ]
    is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs1)
    print(f"Invalid BCS (1 leg): {is_valid}, {msg}")
    assert not is_valid

    invalid_bcs_legs2 = [ # Not both calls
        {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1},
        {"option_type": "PUT", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1}
    ]
    is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs2)
    print(f"Invalid BCS (1 put): {is_valid}, {msg}")
    assert not is_valid

    invalid_bcs_legs3 = [ # Wrong strike order
        {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1},
        {"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1}
    ]
    is_valid, msg = validate_spread_legs("BULL CALL SPREAD", invalid_bcs_legs3)
    print(f"Invalid BCS (strike order): {is_valid}, {msg}")
    assert not is_valid

    # Test Iron Condor
    print("\n--- Iron Condor Tests ---")
    valid_ic_legs = [
        {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1},  # Long Put
        {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1}, # Short Put
        {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1},# Short Call
        {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1}  # Long Call
    ]
    is_valid, msg = validate_spread_legs("IRON CONDOR", valid_ic_legs)
    print(f"Valid IC: {is_valid}, {msg}")
    assert is_valid

    invalid_ic_legs1 = [ # Wrong number of legs
        {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1}
    ]
    is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs1)
    print(f"Invalid IC (1 leg): {is_valid}, {msg}")
    assert not is_valid

    invalid_ic_legs2 = [ # Incorrect strike order for IC
        {"option_type": "PUT", "strike_price": 95.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1},  # Long Put (strike too high for this structure)
        {"option_type": "PUT", "strike_price": 90.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1}, # Short Put
        {"option_type": "CALL", "strike_price": 105.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": -1},
        {"option_type": "CALL", "strike_price": 110.0, "expiry_date": datetime.date(2025, 1, 17), "quantity": 1}
    ]
    is_valid, msg = validate_spread_legs("IRON CONDOR", invalid_ic_legs2)
    print(f"Invalid IC (strike order): {is_valid}, {msg}")
    assert not is_valid

    # Test unknown spread type
    print("\n--- Unknown Spread Type Test ---")
    unknown_legs = [{"option_type": "CALL", "strike_price": 100.0, "expiry_date": datetime.date(2025,1,17), "quantity": 1}]
    is_valid, msg = validate_spread_legs("MY CUSTOM SPREAD", unknown_legs)
    print(f"Unknown Spread Type: {is_valid}, {msg}") # Should be True, "No specific validator..."
    assert is_valid

    print("\nAll validator example tests finished.")
