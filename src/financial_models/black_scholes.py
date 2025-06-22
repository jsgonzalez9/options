import math
from scipy.stats import norm # Using scipy for the cumulative distribution function (CDF) of the standard normal distribution

# N(x) is the cumulative distribution function (CDF) for the standard normal distribution
def N(x):
    """
    Cumulative distribution function for the standard normal distribution.
    """
    return norm.cdf(x)

# n(x) is the probability density function (PDF) for the standard normal distribution
def n_pdf(x):
    """
    Probability density function for the standard normal distribution.
    """
    return norm.pdf(x)

def d1(S, K, T, r, sigma):
    """
    Calculate d1 for Black-Scholes.
    S: Current stock price
    K: Option strike price
    T: Time to expiration (in years)
    r: Risk-free interest rate (annualized)
    sigma: Volatility of the underlying stock (annualized)
    """
    if T <= 0: # Avoid division by zero or log of non-positive if T is 0 or negative
        return float('inf') if S > K else float('-inf') if S < K else 0 # Simplified handling for expired options
    return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

def d2(S, K, T, r, sigma):
    """
    Calculate d2 for Black-Scholes.
    Uses d1 internally.
    """
    if T <= 0: # Consistent handling with d1
        return float('inf') if S > K else float('-inf') if S < K else 0
    return d1(S, K, T, r, sigma) - sigma * math.sqrt(T)

def black_scholes_call_price(S, K, T, r, sigma):
    """
    Calculate Black-Scholes Call option price.
    """
    if T <= 0: # Option has expired
        return max(0, S - K)
    if sigma <= 0: # Volatility must be positive
        return max(0, S * math.exp(-r * T) - K * math.exp(-r * T)) # Simplified: effectively price if sigma is near zero

    val_d1 = d1(S, K, T, r, sigma)
    val_d2 = d2(S, K, T, r, sigma)

    call_price = S * N(val_d1) - K * math.exp(-r * T) * N(val_d2)
    return call_price

def black_scholes_put_price(S, K, T, r, sigma):
    """
    Calculate Black-Scholes Put option price.
    """
    if T <= 0: # Option has expired
        return max(0, K - S)
    if sigma <= 0: # Volatility must be positive
        return max(0, K * math.exp(-r * T) - S * math.exp(-r * T)) # Simplified

    val_d1 = d1(S, K, T, r, sigma)
    val_d2 = d2(S, K, T, r, sigma)

    put_price = K * math.exp(-r * T) * N(-val_d2) - S * N(-val_d1)
    return put_price

# --- Greeks ---

def delta_call(S, K, T, r, sigma):
    """
    Calculate Delta for a Call option.
    """
    if T <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0 if S < K else 0.5 # Simplified for expired or zero vol
    val_d1 = d1(S, K, T, r, sigma)
    return N(val_d1)

def delta_put(S, K, T, r, sigma):
    """
    Calculate Delta for a Put option.
    """
    if T <= 0 or sigma <= 0:
        return -1.0 if S < K else 0.0 if S > K else -0.5 # Simplified
    val_d1 = d1(S, K, T, r, sigma)
    return N(val_d1) - 1

def gamma(S, K, T, r, sigma):
    """
    Calculate Gamma for both Call and Put options.
    """
    if T <= 0 or sigma <= 0 or S <= 0: # Also check S to avoid issues in n_pdf if S is part of d1 calculation
        return 0.0
    val_d1 = d1(S, K, T, r, sigma)
    return n_pdf(val_d1) / (S * sigma * math.sqrt(T))

def vega(S, K, T, r, sigma):
    """
    Calculate Vega for both Call and Put options.
    (Typically expressed as change per 1% change in vol, so sometimes divided by 100)
    This implementation returns the raw Vega.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    val_d1 = d1(S, K, T, r, sigma)
    # Vega = S * n_pdf(d1) * math.sqrt(T)
    # To express as change per 1% change in vol, often result is divided by 100
    return S * n_pdf(val_d1) * math.sqrt(T) / 100 # Standard practice to show Vega per 1% change

def theta_call(S, K, T, r, sigma):
    """
    Calculate Theta for a Call option.
    (Typically expressed as change per day, so sometimes divided by 365)
    This implementation returns the raw annual Theta. Divide by 365 for daily.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0 # Or r * K * math.exp(-r * T) if S > K and T is just at expiry for call

    val_d1 = d1(S, K, T, r, sigma)
    val_d2 = d2(S, K, T, r, sigma)

    term1 = - (S * n_pdf(val_d1) * sigma) / (2 * math.sqrt(T))
    term2 = - r * K * math.exp(-r * T) * N(val_d2)
    # Theta is typically annualized. To get daily theta, divide by 365.
    return (term1 + term2) / 365 # Per day

def theta_put(S, K, T, r, sigma):
    """
    Calculate Theta for a Put option.
    (Typically expressed as change per day, so sometimes divided by 365)
    This implementation returns the raw annual Theta. Divide by 365 for daily.
    """
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0 # Or r * K * math.exp(-r * T) if S < K and T is just at expiry for put

    val_d1 = d1(S, K, T, r, sigma)
    val_d2 = d2(S, K, T, r, sigma)

    term1 = - (S * n_pdf(val_d1) * sigma) / (2 * math.sqrt(T))
    term2 = + r * K * math.exp(-r * T) * N(-val_d2)
    # Theta is typically annualized. To get daily theta, divide by 365.
    return (term1 + term2) / 365 # Per day

def rho_call(S, K, T, r, sigma):
    """
    Calculate Rho for a Call option.
    (Typically expressed as change per 1% change in r, so sometimes divided by 100)
    This implementation returns the raw Rho.
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    val_d2 = d2(S, K, T, r, sigma)
    # Rho = K * T * math.exp(-r * T) * N(d2)
    # To express as change per 1% change in interest rate, often result is divided by 100
    return K * T * math.exp(-r * T) * N(val_d2) / 100 # Per 1% change in r

def rho_put(S, K, T, r, sigma):
    """
    Calculate Rho for a Put option.
    (Typically expressed as change per 1% change in r, so sometimes divided by 100)
    This implementation returns the raw Rho.
    """
    if T <= 0 or sigma <= 0:
        return 0.0

    val_d2 = d2(S, K, T, r, sigma)
    # Rho = -K * T * math.exp(-r * T) * N(-d2)
    # To express as change per 1% change in interest rate, often result is divided by 100
    return -K * T * math.exp(-r * T) * N(-val_d2) / 100 # Per 1% change in r


if __name__ == '__main__':
    # Example Parameters
    S_val = 100  # Current stock price
    K_val = 100  # Option strike price
    T_val = 1.0  # Time to expiration (1 year)
    r_val = 0.05 # Risk-free rate (5%)
    sigma_val = 0.2 # Volatility (20%)

    print(f"Black-Scholes Model Calculations with S={S_val}, K={K_val}, T={T_val}, r={r_val}, sigma={sigma_val}:\n")

    # Calculate d1 and d2
    d1_val = d1(S_val, K_val, T_val, r_val, sigma_val)
    d2_val = d2(S_val, K_val, T_val, r_val, sigma_val)
    print(f"d1: {d1_val:.4f}")
    print(f"d2: {d2_val:.4f}\n")

    # Calculate Call and Put prices
    call_p = black_scholes_call_price(S_val, K_val, T_val, r_val, sigma_val)
    put_p = black_scholes_put_price(S_val, K_val, T_val, r_val, sigma_val)
    print(f"Call Price: {call_p:.4f}")
    print(f"Put Price: {put_p:.4f}\n")

    # Calculate Greeks
    print("Greeks:")
    print(f"  Call Delta: {delta_call(S_val, K_val, T_val, r_val, sigma_val):.4f}")
    print(f"  Put Delta: {delta_put(S_val, K_val, T_val, r_val, sigma_val):.4f}")
    print(f"  Gamma: {gamma(S_val, K_val, T_val, r_val, sigma_val):.4f}")
    print(f"  Vega (per 1% vol change): {vega(S_val, K_val, T_val, r_val, sigma_val):.4f}") # Vega is for 1% change in vol
    print(f"  Call Theta (per day): {theta_call(S_val, K_val, T_val, r_val, sigma_val):.4f}") # Theta is per day
    print(f"  Put Theta (per day): {theta_put(S_val, K_val, T_val, r_val, sigma_val):.4f}")   # Theta is per day
    print(f"  Call Rho (per 1% rate change): {rho_call(S_val, K_val, T_val, r_val, sigma_val):.4f}") # Rho is for 1% change in rate
    print(f"  Put Rho (per 1% rate change): {rho_put(S_val, K_val, T_val, r_val, sigma_val):.4f}")   # Rho is for 1% change in rate

    print("\nEdge case: T=0 (at expiration)")
    S_val_exp = 105
    K_val_exp = 100
    T_val_exp = 0
    call_p_exp = black_scholes_call_price(S_val_exp, K_val_exp, T_val_exp, r_val, sigma_val)
    put_p_exp = black_scholes_put_price(S_val_exp, K_val_exp, T_val_exp, r_val, sigma_val)
    print(f"  Call Price (S=105, K=100, T=0): {call_p_exp:.4f} (Expected: 5)")
    print(f"  Put Price (S=105, K=100, T=0): {put_p_exp:.4f} (Expected: 0)")

    S_val_exp2 = 95
    call_p_exp2 = black_scholes_call_price(S_val_exp2, K_val_exp, T_val_exp, r_val, sigma_val)
    put_p_exp2 = black_scholes_put_price(S_val_exp2, K_val_exp, T_val_exp, r_val, sigma_val)
    print(f"  Call Price (S=95, K=100, T=0): {call_p_exp2:.4f} (Expected: 0)")
    print(f"  Put Price (S=95, K=100, T=0): {put_p_exp2:.4f} (Expected: 5)")

    print("\nNote: Theta is per day. Vega and Rho are scaled for 1% changes in vol and r respectively.")
    print("This model requires `scipy` for `norm.cdf` and `norm.pdf`.")
    print("Ensure you have it installed: pip install scipy")
